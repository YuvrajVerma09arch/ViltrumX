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
from core.tenancy import tenant_for

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
