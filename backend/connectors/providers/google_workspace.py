"""
Google Workspace Admin SDK Reports poller.

Pulls the login audit stream (``activities.list`` with
``applicationName="login"``) — the signal behind impossible-travel and MFA-fatigue
detection. Requires a service account with domain-wide delegation:

* ``GOOGLE_SERVICE_ACCOUNT_JSON`` — the service-account key (JSON string or path)
* ``GOOGLE_WORKSPACE_ADMIN`` — the admin email to impersonate

Both the Google client libraries and the credentials are optional; when either
is missing ``is_configured`` is False and ``poll`` returns 0 (graceful degrade),
so the rest of the platform runs without this connector.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from django.conf import settings

from connectors.normalize import normalize_google_workspace
from connectors.providers import get_cursor, ingest_record, set_cursor

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/admin.reports.audit.readonly"]
DEFAULT_BACKFILL_DAYS = 7
CURSOR_KEY = "login_activities_since"


def _service_account_info():
    """Load the service-account key from a JSON string or a file path, or None."""
    raw = getattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", "") or ""
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except ValueError:
            logger.warning("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON")
            return None
    # Treat as a file path.
    try:
        with open(raw) as fh:  # noqa: PTH123 — explicit path from env
            return json.load(fh)
    except (OSError, ValueError) as exc:
        logger.warning("could not read GOOGLE_SERVICE_ACCOUNT_JSON path: %s", exc)
        return None


def _build_service():
    """Return an authenticated Admin SDK reports service, or None if unavailable."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = _service_account_info()
    admin = getattr(settings, "GOOGLE_WORKSPACE_ADMIN", "") or ""
    if not info or not admin:
        return None
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=SCOPES
    ).with_subject(admin)
    return build("admin", "reports_v1", credentials=creds, cache_discovery=False)


def is_configured(connector=None) -> bool:
    """True only when the Google client libs import and creds + admin are present."""
    if not getattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", ""):
        return False
    if not getattr(settings, "GOOGLE_WORKSPACE_ADMIN", ""):
        return False
    try:
        import google.oauth2.service_account  # noqa: F401
        import googleapiclient.discovery  # noqa: F401
    except ImportError:
        return False
    return True


def _default_cursor() -> str:
    return (
        datetime.now(tz=timezone.utc) - timedelta(days=DEFAULT_BACKFILL_DAYS)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch(connector, since: str) -> tuple[int, str | None]:
    """Page through login activities from ``since``; return (ingested, newest_ts)."""
    service = _build_service()
    if service is None:
        return 0, None

    tenant = connector.tenant
    ingested = 0
    newest = None
    page_token = None
    pages = 0
    while pages < 20:
        resp = (
            service.activities()
            .list(
                userKey="all",
                applicationName="login",
                maxResults=100,
                startTime=since,
                pageToken=page_token,
            )
            .execute()
        )
        for item in resp.get("items", []):
            try:
                envelope = normalize_google_workspace(item)
                ingested += ingest_record(tenant, "workspace", envelope)
                ts = envelope.get("occurred_at")
                if ts is not None and (newest is None or ts > newest):
                    newest = ts
            except Exception as exc:  # noqa: BLE001
                logger.debug("skipping malformed Workspace activity: %s", exc)
        page_token = resp.get("nextPageToken")
        pages += 1
        if not page_token:
            break

    return ingested, (newest.isoformat() if newest else None)


def poll(connector, tenant) -> int:
    """Incrementally fetch new login activities. Returns count ingested."""
    if not is_configured(connector):
        return 0
    since = get_cursor(connector, CURSOR_KEY, default=_default_cursor())
    ingested, newest = _fetch(connector, since)
    set_cursor(
        connector,
        CURSOR_KEY,
        newest or datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    return ingested


def backfill(connector, tenant, days: int = DEFAULT_BACKFILL_DAYS) -> int:
    """Re-pull a wider window (default 7 days) regardless of the stored cursor."""
    if not is_configured(connector):
        return 0
    since = (datetime.now(tz=timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    ingested, newest = _fetch(connector, since)
    if newest:
        set_cursor(connector, CURSOR_KEY, newest)
    return ingested
