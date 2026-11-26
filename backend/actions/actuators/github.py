"""GitHub actuators — disable identity, revoke a session (OAuth token)."""

from __future__ import annotations

import logging

import requests

from actions.actuators.base import ActuationResult, failed, manual, real

logger = logging.getLogger(__name__)

API = "https://api.github.com"
_TIMEOUT = 10


def _token(tenant) -> str:
    from connectors.models import Connector

    c = Connector.objects.filter(tenant=tenant, connector_id="gh").first()
    if not c:
        return ""
    creds = c.credentials if isinstance(c.credentials, dict) else {}
    return creds.get("access_token") or c.github_access_token or ""


def _org(tenant) -> str:
    from connectors.models import Connector

    c = Connector.objects.filter(tenant=tenant, connector_id="gh").first()
    if not c:
        return ""
    creds = c.credentials if isinstance(c.credentials, dict) else {}
    return c.github_org_login or creds.get("org") or ""


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def disable_identity(tenant, action) -> ActuationResult:
    """Remove a user from the GitHub org (reversible: re-invite on revert).

    ``action.target`` is the GitHub username (or email local-part).
    """
    token, org = _token(tenant), _org(tenant)
    if not (token and org):
        return manual("GitHub is not connected; remove the user from the org manually.")
    login = (action.target or "").split("@")[0].strip()
    if not login:
        return manual("No GitHub username on the action target.")

    url = f"{API}/orgs/{org}/memberships/{login}"
    try:
        r = requests.delete(url, headers=_headers(token), timeout=_TIMEOUT)
    except requests.RequestException as exc:
        return failed(f"GitHub remove-member failed: {exc}")
    if r.status_code in (204, 200):
        # Receipt: role, if any, so revert can restore a matching invitation.
        return real(
            {"provider": "github", "org": org, "login": login},
            f"Removed {login} from {org}",
        )
    if r.status_code == 404:
        return manual(f"{login} is not a member of {org}; nothing to remove.")
    return failed(f"GitHub {r.status_code}: {r.text[:160]}")


def revert_disable_identity(tenant, action) -> ActuationResult:
    token, org = _token(tenant), _org(tenant)
    receipt = action.execution_receipt or {}
    login = receipt.get("login") or (action.target or "").split("@")[0]
    if not (token and org and login):
        return manual("GitHub not connected; re-invite the user manually.")
    url = f"{API}/orgs/{org}/memberships/{login}"
    try:
        r = requests.put(url, headers=_headers(token), json={"role": "member"}, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        return failed(f"GitHub re-invite failed: {exc}")
    if r.status_code in (200, 201):
        return real({}, f"Re-invited {login} to {org}")
    return failed(f"GitHub {r.status_code}: {r.text[:160]}")


def revoke_session(tenant, action) -> ActuationResult:
    """Revoke a GitHub OAuth grant / session.

    Works on a provider OAuth token id stored on the action target, e.g.
    ``token:<id>``; a plain username cannot be session-killed via the API.
    """
    token = _token(tenant)
    if not token:
        return manual("GitHub is not connected; revoke the session manually.")
    target = (action.target or "").strip()
    if target.startswith("token:") or target.startswith("oauth:"):
        grant_id = target.split(":", 1)[1]
        url = f"{API}/applications/grants/{grant_id}"
        try:
            r = requests.delete(url, headers=_headers(token), timeout=_TIMEOUT)
        except requests.RequestException as exc:
            return failed(f"GitHub grant revoke failed: {exc}")
        if r.status_code in (204, 200):
            return real(
                {"provider": "github", "revoked_grant": grant_id},
                f"Revoked OAuth grant {grant_id}",
            )
        return failed(f"GitHub {r.status_code}: {r.text[:160]}")
    return manual(
        "No revocable GitHub session id on the target (expected 'token:<id>'). "
        "Ask the user to re-authenticate or revoke the grant manually."
    )


def revert_revoke_session(tenant, action) -> ActuationResult:
    # A revoked OAuth grant cannot be un-revoked; the user must re-authorize.
    return manual("Revoked OAuth grants cannot be restored; the user must re-authorize.")
