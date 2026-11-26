"""
Startup verification (P4): prove the signup is a real company.

Layers (each optional, gated so a local dev environment still works):
  1. Signup gate — reject free/disposable email providers so an org can't be
     created from gmail. (Enforced in RegisterSerializer.validate_email.)
  2. DNS TXT ownership — the tenant publishes a token at ``_viltrumx.<domain>``;
     we resolve it and mark the domain verified. Free, the real proof.
  3. GSTIN — format + checksum locally (free), then an optional vendor check
     (Surepass/Karza) when configured; needed for GST invoices anyway.

Until domain-verified, a tenant is an unactivated trial: it can browse but
cannot ingest live data (enforced in ConnectorConnectView).
"""

from __future__ import annotations

import logging
import re
import secrets

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenancy import role_for, tenant_for

logger = logging.getLogger(__name__)

FREE_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.in", "outlook.com",
    "hotmail.com", "live.com", "proton.me", "protonmail.com", "icloud.com",
    "aol.com", "gmx.com", "mail.com", "yandex.com", "zoho.com",
}


def is_free_email(email: str) -> bool:
    domain = (email or "").rsplit("@", 1)[-1].lower()
    return domain in FREE_EMAIL_DOMAINS


# GSTIN: 2-digit state + 10-char PAN + entity + 'Z' + checksum (mod 36).
_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_checksum_valid(gstin: str) -> bool:
    """Validate the GSTIN mod-36 checksum (the 15th char)."""
    gstin = (gstin or "").strip().upper()
    if not _GSTIN_RE.match(gstin):
        return False
    total = 0
    for i, ch in enumerate(gstin[:14]):
        value = _GSTIN_CHARS.index(ch)
        factor = 2 if i % 2 else 1
        product = value * factor
        total += product // 36 + product % 36
    check = (36 - (total % 36)) % 36
    return _GSTIN_CHARS[check] == gstin[14]


class _TenantView(APIView):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.tenant = tenant_for(request)

    def require_admin(self, request):
        if role_for(request, self.tenant) not in ("Owner", "Admin"):
            return Response({"detail": "Only an admin can manage verification."}, status=403)
        return None


class VerificationStatusView(_TenantView):
    def get(self, request):
        t = self.tenant
        return Response(
            {
                "domain": t.domain,
                "domain_verified": t.domain_verified,
                "verification_status": t.verification_status,
                "gstin": t.gstin,
                "gstin_verified": t.gstin_verified_at is not None,
                "instructions": (
                    f'Add a DNS TXT record at _viltrumx.{t.domain} with value "{t.domain_token}"'
                    if t.domain and not t.domain_verified else ""
                ),
            }
        )


class DomainStartView(_TenantView):
    """Generate a DNS TXT token for the tenant's company domain."""

    def post(self, request):
        denied = self.require_admin(request)
        if denied:
            return denied
        domain = (request.data.get("domain") or "").strip().lower()
        domain = re.sub(r"^https?://", "", domain).split("/")[0]
        if not domain or "." not in domain:
            return Response({"detail": "A company domain like 'acme.in' is required."}, status=400)
        if domain.rsplit(".", 1)[-1] in {".local", "localhost"}:
            return Response({"detail": "That is not a public domain."}, status=400)
        self.tenant.domain = domain
        self.tenant.domain_token = f"viltrumx-verify={secrets.token_hex(16)}"
        self.tenant.verification_status = "pending_domain"
        self.tenant.save(update_fields=["domain", "domain_token", "verification_status"])
        return Response(
            {
                "domain": domain,
                "record_type": "TXT",
                "record_name": f"_viltrumx.{domain}",
                "record_value": self.tenant.domain_token,
                "instructions": (
                    f'Create a TXT record "_viltrumx.{domain}" = "{self.tenant.domain_token}", '
                    "then call /verify/domain/check."
                ),
            }
        )


class DomainCheckView(_TenantView):
    """Resolve the TXT record and mark the domain verified if it matches."""

    def post(self, request):
        denied = self.require_admin(request)
        if denied:
            return denied
        t = self.tenant
        if not (t.domain and t.domain_token):
            return Response({"detail": "Start verification first."}, status=400)
        if getattr(settings, "VERIFICATION_DNS_ENABLED", True):
            if not self._txt_matches(t.domain, t.domain_token):
                return Response(
                    {
                        "verified": False,
                        "detail": f'TXT record not found/matched yet at _viltrumx.{t.domain}. '
                                  "DNS can take a few minutes to propagate.",
                    },
                    status=status.HTTP_409_CONFLICT,
                )
        t.domain_verified_at = timezone.now()
        t.verification_status = "domain_verified"
        t.save(update_fields=["domain_verified_at", "verification_status"])
        return Response({"verified": True, "domain": t.domain})

    @staticmethod
    def _txt_matches(domain: str, token: str) -> bool:
        try:
            import dns.resolver

            answers = dns.resolver.resolve(f"_viltrumx.{domain}", "TXT")
            for rdata in answers:
                value = b"".join(rdata.strings).decode() if hasattr(rdata, "strings") \
                    else rdata.to_text().strip('"')
                if hmac_eq(value, token):
                    return True
        except Exception as exc:  # noqa: BLE001
            logger.info("DNS TXT lookup failed for %s: %s", domain, exc)
        return False


class GstinVerifyView(_TenantView):
    """Validate the tenant's GSTIN (checksum always; vendor lookup if configured)."""

    def post(self, request):
        denied = self.require_admin(request)
        if denied:
            return denied
        gstin = (request.data.get("gstin") or "").strip().upper()
        if not gstin_checksum_valid(gstin):
            return Response(
                {"verified": False, "detail": "GSTIN format/checksum is invalid."}, status=400
            )
        # Optional vendor lookup (Surepass/Karza) when a key is configured.
        legal_name = self._vendor_lookup(gstin)
        t = self.tenant
        t.gstin = gstin
        t.gstin_legal_name = legal_name or ""
        t.gstin_verified_at = timezone.now()
        if t.domain_verified:
            t.verification_status = "fully_verified"
        t.save(update_fields=[
            "gstin", "gstin_legal_name", "gstin_verified_at", "verification_status",
        ])
        return Response({"verified": True, "gstin": gstin, "legal_name": t.gstin_legal_name})

    @staticmethod
    def _vendor_lookup(gstin: str) -> str:
        key = getattr(settings, "GSTIN_API_KEY", "") or ""
        url = getattr(settings, "GSTIN_API_URL", "") or ""
        if not (key and url):
            return ""  # checksum-only mode
        try:
            import requests

            r = requests.get(url, params={"gstin": gstin},
                             headers={"Authorization": f"Bearer {key}"}, timeout=8)
            if r.status_code == 200:
                data = r.json()
                return (data.get("legal_name") or data.get("lgnm") or "")[:200]
        except Exception as exc:  # noqa: BLE001
            logger.warning("GSTIN vendor lookup failed: %s", exc)
        return ""


def hmac_eq(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a.encode(), b.encode())
