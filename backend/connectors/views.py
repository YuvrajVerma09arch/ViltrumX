"""
GitHub webhook receiver + audit-log poller (the one real connector).
"""

import hashlib
import hmac
import logging

from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from connectors.tasks import ingest_event

logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, header: str | None) -> bool:
    secret = getattr(settings, "GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        return True  # dev: no secret configured → accept all
    if not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)


class GitHubWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        sig = request.headers.get("X-Hub-Signature-256")
        if not _verify_signature(request.body, sig):
            return Response({"detail": "Invalid signature."}, status=401)

        event_type = request.headers.get("X-GitHub-Event", "unknown")
        payload = request.data

        # Resolve tenant from the org name in the payload
        org = (payload.get("organization") or {}).get("login") or (
            payload.get("repository") or {}
        ).get("owner", {}).get("login", "")
        tenant = _tenant_for_org(org)
        if tenant is None:
            return Response({"detail": "Unknown org."}, status=404)

        raw = {
            "source": "github",
            "@timestamp": int(timezone.now().timestamp() * 1000),
            "action": f"{event_type}.{payload.get('action', 'event')}",
            "actor": (payload.get("sender") or {}).get("login", "unknown"),
            "actor_email": (payload.get("sender") or {}).get("email", ""),
            "org": org,
            **_extract_fields(event_type, payload),
        }
        ingest_event.delay(tenant.id, raw)
        return Response({"queued": True})


def _tenant_for_org(org: str):
    from core.models import Tenant

    slug = org.lower().replace("-", "")
    return Tenant.objects.filter(slug__icontains=slug).first()


def _extract_fields(event_type: str, payload: dict) -> dict:
    if event_type == "personal_access_token":
        return {
            "token_id": payload.get("personal_access_token", {}).get("id"),
            "scopes": payload.get("personal_access_token", {}).get("scopes", []),
        }
    if event_type in ("push", "create"):
        repo = (payload.get("repository") or {}).get("full_name", "")
        return {"repo": repo}
    return {}
