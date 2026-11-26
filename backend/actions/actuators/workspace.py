"""Google Workspace actuators — suspend/reactivate a user, revoke tokens."""

from __future__ import annotations

import logging

from actions.actuators.base import ActuationResult, failed, manual, real

logger = logging.getLogger(__name__)


def _admin_service():
    """Return an Admin SDK Directory service (users), or None if unconfigured."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        from connectors.providers.google_workspace import _service_account_info

        info = _service_account_info()
        if not info:
            return None
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/admin.directory.user"]
        ).with_subject(_admin_subject())
        if not _admin_subject():
            return None
        return build("admin", "directory_v1", credentials=creds, cache_discovery=False)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Workspace actuator unavailable: %s", exc)
        return None


def _admin_subject() -> str:
    from django.conf import settings

    return getattr(settings, "GOOGLE_WORKSPACE_ADMIN", "") or ""


def disable_identity(tenant, action) -> ActuationResult:
    """Suspend a Workspace user (reversible: un-suspend)."""
    svc = _admin_service()
    email = (action.target or "").strip()
    if svc is None:
        return manual("Google Workspace not configured; suspend the user in the admin console.")
    if not email or "@" not in email:
        return manual("Action target is not a Workspace email.")
    try:
        svc.users().update(userKey=email, body={"suspended": True}).execute()
    except Exception as exc:  # noqa: BLE001
        return failed(f"Workspace suspend failed: {exc}")
    return real({"provider": "workspace", "email": email}, f"Suspended {email}")


def revert_disable_identity(tenant, action) -> ActuationResult:
    svc = _admin_service()
    email = (action.execution_receipt or {}).get("email") or (action.target or "")
    if svc is None or not email:
        return manual("Google Workspace not configured; un-suspend the user manually.")
    try:
        svc.users().update(userKey=email, body={"suspended": False}).execute()
    except Exception as exc:  # noqa: BLE001
        return failed(f"Workspace un-suspend failed: {exc}")
    return real({}, f"Re-activated {email}")


def revoke_session(tenant, action) -> ActuationResult:
    """Sign a user out everywhere and revoke their OAuth tokens."""
    svc = _admin_service()
    email = (action.target or "").strip()
    if svc is None:
        return manual("Google Workspace not configured; sign the user out manually.")
    if not email or "@" not in email:
        return manual("Action target is not a Workspace email.")
    try:
        svc.users().signOut(userKey=email).execute()
        svc.users().tokens().delete(userKey=email).execute()
    except Exception as exc:  # noqa: BLE001
        return failed(f"Workspace sign-out failed: {exc}")
    return real({"provider": "workspace", "email": email}, f"Signed out {email} and revoked tokens")


def revert_revoke_session(tenant, action) -> ActuationResult:
    # A sign-out cannot be undone; the user simply signs in again.
    return manual("Sign-out cannot be reverted; the user re-authenticates.")
