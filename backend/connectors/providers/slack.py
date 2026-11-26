"""
Slack connector.

Slack serves two purposes in ViltrumX:

1. **Alert delivery** — :func:`send_alert` posts a message to the tenant's
   incoming-webhook URL so a founder who lives in Slack (not the dashboard) is
   notified of an incident.
2. **Audit-log polling** — optional and best-effort: only works when a *user*
   token with the ``auditlogs:read`` scope is configured. Without such a token
   :func:`poll` is a no-op returning 0.

``send_alert`` is import-guarded on ``requests`` and never raises into callers.
"""

from __future__ import annotations

import logging

from connectors.normalize import normalize_slack
from connectors.providers import get_cursor, ingest_record, set_cursor

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api"
DEFAULT_BACKFILL_DAYS = 7
CURSOR_KEY = "audit_logs_since"


def _creds(connector) -> dict:
    creds = getattr(connector, "credentials", None) or {}
    return creds if isinstance(creds, dict) else {}


def _webhook_url(connector) -> str:
    return _creds(connector).get("webhook_url") or ""


def _user_token(connector) -> str:
    return _creds(connector).get("user_token") or ""


def is_configured(connector=None) -> bool:
    """Configured when an incoming webhook URL is present."""
    if connector is None:
        return False
    return bool(_webhook_url(connector))


def send_alert(connector, text: str) -> bool:
    """POST ``text`` to the connector's incoming webhook. Returns success."""
    url = _webhook_url(connector)
    if not url:
        return False
    try:
        import requests

        resp = requests.post(url, json={"text": text}, timeout=10)
        if resp.status_code != 200:
            logger.warning("Slack alert post failed (%s): %s", resp.status_code, resp.text[:200])
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Slack alert post error: %s", exc)
        return False


def poll(connector, tenant) -> int:
    """Poll the Slack audit log — only possible with a user token + auditlogs scope.

    Slack's audit-log API is Enterprise-Grid only and needs a user token. We do
    not attempt it without one, so most tenants get a clean 0 here.
    """
    token = _user_token(connector)
    if not token:
        return 0
    try:
        import requests
    except ImportError:
        return 0

    since = get_cursor(connector, CURSOR_KEY, default="")
    params = {"limit": 100}
    if since:
        params["oldest"] = since
    try:
        resp = requests.get(
            f"{SLACK_API}/auditlogs.get",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=15,
        )
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Slack audit-log poll error: %s", exc)
        return 0

    if not data.get("ok"):
        logger.debug("Slack audit-log unavailable: %s", data.get("error"))
        return 0

    ingested = 0
    newest = None
    for entry in data.get("entries", []):
        try:
            envelope = normalize_slack(entry)
            ingested += ingest_record(tenant, "slack", envelope)
            ts = envelope.get("occurred_at")
            if ts is not None and (newest is None or ts > newest):
                newest = ts
        except Exception as exc:  # noqa: BLE001
            logger.debug("skipping malformed Slack audit entry: %s", exc)
    if newest is not None:
        set_cursor(connector, CURSOR_KEY, str(newest))
    return ingested


def backfill(connector, tenant, days: int = DEFAULT_BACKFILL_DAYS) -> int:
    """Slack audit logs are not windowed client-side; a plain poll is the backfill."""
    return poll(connector, tenant)
