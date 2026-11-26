"""
GitHub webhook receiver + audit-log poller (the one real connector).
"""

import hashlib
import hmac
import logging
import os
import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from connectors.models import Connector, OAuthState
from connectors.tasks import ingest_event
from core.models import Tenant
from core.tenancy import require_role, tenant_for

logger = logging.getLogger(__name__)

# Narrow, explicitly documented fallback for the viva walkthrough only — see
# _demo_tenant_for_org(). Nothing here is ever matched as a substring.
DEMO_TENANT_SLUG = "paykraft"
DEMO_GITHUB_ORG_LOGIN = "paykraft"


def _webhook_secret() -> str:
    return getattr(settings, "GITHUB_WEBHOOK_SECRET", "") or ""


def _webhook_secret_missing() -> bool:
    """A production deployment must never accept unsigned webhooks (fail closed)."""
    return not settings.DEBUG and not _webhook_secret()


def _verify_signature(body: bytes, header: str | None) -> bool:
    """Validate GitHub's HMAC-SHA256 signature.

    With no secret configured the only path that still accepts a request is the
    DEBUG dev mock. Production callers are rejected with 503 by
    ``_webhook_secret_missing`` before this is called; returning DEBUG here
    keeps that guarantee in one place and preserves local dev behaviour.
    """
    secret = _webhook_secret()
    if not secret:
        return bool(settings.DEBUG)
    if not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)


def _get_github_oauth_config():
    """Returns (client_id, client_secret, redirect_uri) from settings/env."""
    client_id = getattr(settings, "GITHUB_CLIENT_ID", os.environ.get("GITHUB_CLIENT_ID", ""))
    client_secret = getattr(
        settings, "GITHUB_CLIENT_SECRET", os.environ.get("GITHUB_CLIENT_SECRET", "")
    )
    redirect_uri = getattr(
        settings, "GITHUB_REDIRECT_URI", os.environ.get("GITHUB_REDIRECT_URI", "")
    )
    return client_id, client_secret, redirect_uri


def _is_github_configured():
    """Check if GitHub OAuth is fully configured."""
    client_id, client_secret, redirect_uri = _get_github_oauth_config()
    return bool(client_id and client_secret and redirect_uri)


def _store_oauth_state(state: str, tenant_id: int):
    """Persist OAuth state to DB (not session) so it survives the GitHub redirect."""
    from datetime import timedelta

    from django.utils import timezone

    OAuthState.objects.create(
        state=state,
        tenant_id=tenant_id,
        expires_at=timezone.now() + timedelta(minutes=10),
    )


def _consume_oauth_state(state: str) -> int | None:
    """Look up and delete an OAuth state token; returns tenant_id or None."""
    from django.utils import timezone

    row = OAuthState.objects.filter(
        state=state, expires_at__gt=timezone.now()
    ).first()
    if row is None:
        OAuthState.objects.filter(expires_at__lte=timezone.now()).delete()
        return None
    tenant_id = row.tenant_id
    row.delete()
    return tenant_id


class GitHubWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Never accept unsigned webhooks in production: an unconfigured secret
        # is a server misconfiguration, not permission to trust the payload.
        if _webhook_secret_missing():
            logger.error("GitHub webhook rejected: GITHUB_WEBHOOK_SECRET is not configured.")
            return Response(
                {"detail": "GitHub webhook secret is not configured."}, status=503
            )
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


class GitHubOAuthStartView(APIView):
    """Step 1: Redirect user to GitHub to authorize the app."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = tenant_for(request)
        state = secrets.token_urlsafe(32)
        _store_oauth_state(state, tenant.id)

        # Development mode: if GitHub OAuth not configured, return a mock auth_url.
        # Production must fail closed rather than hand out a mock flow that mints
        # a fake "connected" connector.
        if not _is_github_configured():
            if not settings.DEBUG:
                return Response({"detail": "GitHub OAuth is not configured."}, status=503)
            default_redirect = "http://localhost:8000/api/v1/connectors/gh/oauth/callback"
            redirect_uri = getattr(
                settings,
                "GITHUB_REDIRECT_URI",
                os.environ.get("GITHUB_REDIRECT_URI", default_redirect),
            )
            mock_auth_url = f"{redirect_uri}?code=demo-code-{state}&state={state}"
            return Response({"auth_url": mock_auth_url, "mock": True})

        client_id, _, redirect_uri = _get_github_oauth_config()
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:org,repo,workflow,admin:org_hook",
            "state": state,
        }
        github_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
        return Response({"auth_url": github_url})


class GitHubOAuthCallbackView(APIView):
    """Step 2: GitHub redirects here with code — exchange for token & create Connector."""

    permission_classes = [AllowAny]

    def get(self, request):
        state = request.query_params.get("state", "")
        code = request.query_params.get("code", "")

        if not state or not code:
            return Response({"detail": "Missing state or code."}, status=400)

        tenant_id = _consume_oauth_state(state)
        if tenant_id is None:
            return Response({"detail": "Invalid or expired OAuth state."}, status=400)

        # Mock codes are a DEBUG-only dev affordance. Outside DEBUG they must
        # never mint a "connected" GitHub connector — reject them outright.
        if code.startswith("demo-code-") and not settings.DEBUG:
            return Response(
                {"detail": "Mock OAuth codes are not accepted outside DEBUG."}, status=400
            )
        is_mock = code.startswith("demo-code-")

        access_token = "mock-token"
        org_login = "demo-org"
        installation_id = None

        if not is_mock:
            client_id, client_secret, redirect_uri = _get_github_oauth_config()
            if not all([client_id, client_secret, redirect_uri]):
                return Response(
                    {"detail": "GitHub OAuth not fully configured."}, status=503
                )

            # Exchange code for access token
            token_resp = requests.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                timeout=10,
            )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                logger.error("GitHub token exchange failed: %s", token_data)
                return Response({"detail": "Failed to exchange code for token."}, status=400)

            # Fetch org info to identify the GitHub org
            org_resp = requests.get(
                "https://api.github.com/user/orgs",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=10,
            )
            orgs = org_resp.json()
            if not orgs:
                user_resp = requests.get(
                    "https://api.github.com/user",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                    },
                    timeout=10,
                )
                user = user_resp.json()
                org_login = user.get("login", "")
            else:
                org_login = orgs[0].get("login", "")

            if org_login:
                inst_resp = requests.get(
                    f"https://api.github.com/orgs/{org_login}/installation",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                    },
                    timeout=10,
                )
                if inst_resp.status_code == 200:
                    installation_id = inst_resp.json().get("id")

        # Create/update the Connector record
        tenant = Tenant.objects.filter(id=tenant_id).first()
        if not tenant:
            return Response({"detail": "Tenant not found."}, status=404)

        connector, _ = Connector.objects.update_or_create(
            tenant=tenant,
            connector_id="gh",
            defaults={
                "name": "GitHub",
                "status": "connected",
                "github_installation_id": installation_id,
                "github_access_token": access_token,
                "github_org_login": org_login,
            },
        )

        # Sync GitHub into ontology graph so Ontology Explorer shows repos, PATs, users
        try:
            from ontology import graph as og
            og.upsert_node(tenant, "sa-gh", "GitHub", "saas", criticality="high",
                          meta=f"Org: {org_login or 'connected'}", x=560, y=200)
            og.upsert_node(tenant, "k-pat", "GitHub PAT", "apikey", criticality="high",
                          meta="Personal Access Token", x=300, y=200)
            og.upsert_edge(tenant, "e-gh-pat", "sa-gh", "k-pat", "issues_token")
        except Exception:
            pass  # non-blocking

        # Redirect to frontend onboarding page with success indicator
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
        return HttpResponseRedirect(f"{frontend_url}/app/onboarding?connected=github")


class GitHubOAuthDisconnectView(APIView):
    """Disconnect GitHub connector for the tenant."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        tenant = tenant_for(request)
        require_role(request, tenant, "Admin")
        Connector.objects.filter(tenant=tenant, connector_id="gh").delete()
        return Response({"disconnected": True})


def _tenant_for_org(org: str):
    """Resolve the tenant from an *installed* GitHub connector, exactly.

    The previous implementation guessed the tenant with ``slug__icontains`` on
    a dash-stripped org name. That could route one organization's webhook into
    an unrelated tenant whose slug merely contained the org as a substring.
    We now require an exact (case-insensitive) match against the
    ``github_org_login`` recorded on a ``gh`` Connector.
    """
    if not org:
        return None
    connector = (
        Connector.objects.filter(connector_id="gh", github_org_login__iexact=org)
        .select_related("tenant")
        .first()
    )
    if connector is not None:
        return connector.tenant
    return _demo_tenant_for_org(org)


def _demo_tenant_for_org(org: str):
    """Demo-only fallback for the viva walkthrough.

    The seeded viva demo tenant's ``gh`` connector has no ``github_org_login``
    (seed_demo sets only name/status), so replayed demo webhooks for the demo
    org would not resolve through the connector lookup. This fallback is
    deliberately tight: an EXACT org-login match against a single hardcoded
    demo slug, never a substring, so no other tenant can be picked by accident.
    """
    if org.casefold() != DEMO_GITHUB_ORG_LOGIN.casefold():
        return None
    return Tenant.objects.filter(slug=DEMO_TENANT_SLUG).first()


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


# ── Generic multi-provider credentials surface ───────────────────────────────
# Required keys per provider slug. Empty dict means "no user-supplied secrets
# needed — configuration is via server settings / IAM role" (google, aws).
REQUIRED_CREDENTIAL_KEYS = {
    "github": {"access_token", "org"},
    "google": set(),
    "google_workspace": set(),
    "aws": set(),
    "slack": {"webhook_url"},
    "razorpay": {"key_id", "key_secret"},
}

# Keys we accept + persist per provider even when not required (e.g. slack's
# optional user token for audit-log polling). Anything else in the body is
# dropped so a caller can never smuggle arbitrary JSON into the model.
ALLOWED_CREDENTIAL_KEYS = {
    "github": {"access_token", "org"},
    "google": {"service_account_json", "admin_email"},
    "google_workspace": {"service_account_json", "admin_email"},
    "aws": {"role_arn", "region"},
    "slack": {"webhook_url", "user_token"},
    "razorpay": {"key_id", "key_secret"},
    "m365": {"tenant_id", "client_id", "client_secret"},
}


def _resolve_provider(connector_id: str, body_provider: str) -> str:
    from connectors.providers import provider_for_connector_id

    return provider_for_connector_id(connector_id, override=body_provider)


def _known_connector_name(connector_id: str) -> str | None:
    from core import demo_data

    for fixture in demo_data.CONNECTORS:
        if fixture["id"] == connector_id:
            return fixture["name"]
    return None


class ConnectorCredentialsView(APIView):
    """Store per-provider credentials for a connector (secrets never echoed).

    POST body may carry ``provider`` plus the provider's keys, e.g.::

        github   -> {access_token, org}
        slack    -> {webhook_url}
        razorpay -> {key_id, key_secret}
        google   -> {} (configured server-side via GOOGLE_SERVICE_ACCOUNT_JSON)
        aws      -> {} (configured via AWS_ROLE_ARN / instance role)

    On success the connector is marked ``provider=<slug>`` and
    ``status=connected``; the response returns only the provider slug, status,
    and the *names* of stored keys — never their values.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, connector_id: str):
        tenant = tenant_for(request)
        require_role(request, tenant, "Admin")
        # Startup verification gate (P4) — same rule as ConnectorConnectView.
        # This is the real credential path, so it must enforce it too.
        if tenant.slug != "paykraft" and not tenant.domain_verified:
            return Response(
                {"detail": "Verify your company domain before connecting live sources.",
                 "verify": "/api/v1/verify/domain/start"},
                status=403,
            )
        if not tenant.connector_enabled(connector_id):
            return Response(
                {"detail": "This connector is not included in your plan."},
                status=403,
            )

        body = request.data if isinstance(request.data, dict) else {}
        provider = _resolve_provider(connector_id, str(body.get("provider", "")))
        if not provider or provider not in REQUIRED_CREDENTIAL_KEYS:
            return Response(
                {"detail": f"Unknown or unsupported provider for '{connector_id}'."},
                status=400,
            )

        required = REQUIRED_CREDENTIAL_KEYS[provider]
        allowed = ALLOWED_CREDENTIAL_KEYS.get(provider, set())
        provided = {k: v for k, v in body.items() if k in allowed}
        missing = sorted(k for k in required if not provided.get(k))
        if missing:
            return Response(
                {"detail": f"Missing required credential keys: {', '.join(missing)}."},
                status=400,
            )

        name = _known_connector_name(connector_id) or provider.title()
        defaults = {"name": name, "provider": provider, "status": "connected"}
        if provider == "github":
            # Mirror the OAuth columns so the GitHub poller + webhook tenant
            # resolution work whether creds arrive via OAuth or this endpoint.
            defaults["github_org_login"] = str(provided.get("org", ""))

        connector, _ = Connector.objects.update_or_create(
            tenant=tenant, connector_id=connector_id, defaults=defaults
        )
        if provider == "github" and provided.get("access_token"):
            connector.github_access_token = str(provided["access_token"])
            connector.save(update_fields=["github_access_token"])

        # Merge into the existing credentials dict — never blow away keys from
        # a prior call (e.g. an OAuth token already present).
        merged = dict(connector.credentials or {})
        merged.update({k: v for k, v in provided.items() if v not in (None, "")})
        connector.credentials = merged
        connector.last_error = ""
        connector.save(update_fields=["credentials", "last_error"])

        logger.info(
            "connector credentials stored: tenant=%s connector=%s provider=%s keys=%s",
            tenant.id,
            connector_id,
            provider,
            sorted(provided),
        )
        return Response(
            {
                "connectorId": connector_id,
                "provider": provider,
                "status": connector.status,
                "storedKeys": sorted(merged),
            }
        )


class ConnectorDisconnectView(APIView):
    """Disconnect a connector: wipe secrets, keep the row as ``available``.

    Deleting the row would lose the audit linkage and let a stale UI show the
    connector as available-but-with-history. Instead we clear credentials and
    demote the status, so re-connecting is a clean upsert.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, connector_id: str):
        tenant = tenant_for(request)
        require_role(request, tenant, "Admin")
        updated = Connector.objects.filter(
            tenant=tenant, connector_id=connector_id
        ).update(
            status="available",
            credentials={},
            last_error="",
            provider="",
            github_access_token="",
            github_org_login="",
            github_installation_id=None,
        )
        if not updated:
            return Response({"detail": "Connector not found."}, status=404)
        return Response({"disconnected": True, "connectorId": connector_id})
