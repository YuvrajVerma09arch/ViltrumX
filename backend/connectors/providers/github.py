"""
GitHub organization audit-log poller.

The audit log is where security-relevant admin actions live —
``personal_access_token.create``, ``org.add_member``, deploy-key additions —
events a standard webhook never delivers. We page through
``GET /orgs/{org}/audit-log`` and normalize each record.

Credentials resolution order (so both the OAuth flow and the generic
credentials endpoint work):
  token: ``connector.credentials['access_token']`` or ``connector.github_access_token``
  org:   ``connector.github_org_login`` or ``connector.credentials['org']``
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests

from connectors.normalize import normalize_github_audit
from connectors.providers import get_cursor, ingest_record, set_cursor

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"
PAGE_CAP = 10  # hard ceiling on pages per poll — a bad cursor must never loop forever
DEFAULT_BACKFILL_DAYS = 7
CURSOR_KEY = "audit_log_since"


def _creds(connector) -> dict:
    creds = getattr(connector, "credentials", None) or {}
    return creds if isinstance(creds, dict) else {}


def _token(connector) -> str:
    return (
        _creds(connector).get("access_token")
        or getattr(connector, "github_access_token", "")
        or ""
    )


def _org(connector) -> str:
    return (
        getattr(connector, "github_org_login", "")
        or _creds(connector).get("org")
        or ""
    )


def is_configured(connector=None) -> bool:
    """True only when both a token and an org login are available."""
    if connector is None:
        return False
    return bool(_token(connector) and _org(connector))


def _default_cursor() -> str:
    return (
        datetime.now(tz=timezone.utc) - timedelta(days=DEFAULT_BACKFILL_DAYS)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def _next_link(resp) -> str | None:
    """Extract the ``rel="next"`` URL from GitHub's Link header, if any."""
    link = resp.headers.get("Link", "")
    if not link:
        return None
    for part in link.split(","):
        segments = part.split(";")
        if len(segments) < 2:
            continue
        url = segments[0].strip().strip("<>")
        if 'rel="next"' in part:
            return url
    return None


def _fetch(connector, since: str) -> tuple[int, str | None]:
    """Page through the audit log from ``since``; return (ingested, newest_ts)."""
    token, org = _token(connector), _org(connector)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    tenant = connector.tenant
    url: str | None = f"{API_BASE}/orgs/{org}/audit-log"
    params = {"per_page": 100, "phrase": f"created:>={since}"}

    ingested = 0
    newest = None
    pages = 0
    while url and pages < PAGE_CAP:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code != 200:
            logger.warning(
                "GitHub audit-log poll failed (%s) for org %s: %s",
                resp.status_code,
                org,
                resp.text[:200],
            )
            break
        try:
            records = resp.json()
        except ValueError:
            break
        if not isinstance(records, list):
            break
        for rec in records:
            try:
                envelope = normalize_github_audit(rec)
                ingested += ingest_record(tenant, "github", envelope)
                ts = envelope.get("occurred_at")
                if ts is not None and (newest is None or ts > newest):
                    newest = ts
            except Exception as exc:  # noqa: BLE001 — one bad record never aborts a page
                logger.debug("skipping malformed GitHub audit record: %s", exc)

        next_url = _next_link(resp)
        if next_url:
            # The next-link already carries the cursor param; drop our params.
            url, params = next_url, None
        else:
            url = None
        pages += 1

    return ingested, (newest.isoformat() if newest else None)


def poll(connector, tenant) -> int:
    """Incrementally fetch new audit-log records. Returns count ingested."""
    if not is_configured(connector):
        return 0
    since = get_cursor(connector, CURSOR_KEY, default=_default_cursor())
    ingested, newest = _fetch(connector, since)
    # Advance the cursor to the newest event seen; fall back to now so the next
    # poll does not re-scan the same window when the org had no new activity.
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
