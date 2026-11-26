"""
Razorpay payments poller.

Pulls recent payments (``GET /v1/payments``) so settlement anomalies and
payment-rail abuse surface alongside identity/cloud telemetry. Auth is HTTP
Basic with ``key_id:key_secret``. Credentials come from the connector's
``credentials`` dict, falling back to ``settings.RAZORPAY_KEY_ID`` /
``RAZORPAY_KEY_SECRET``.

Missing creds → ``is_configured`` False and ``poll`` returns 0.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings

from connectors.normalize import normalize_razorpay
from connectors.providers import get_cursor, ingest_record, set_cursor

logger = logging.getLogger(__name__)

API_BASE = "https://api.razorpay.com/v1"
DEFAULT_BACKFILL_DAYS = 7
CURSOR_KEY = "payments_since"
PAGE_SIZE = 25


def _creds(connector) -> dict:
    creds = getattr(connector, "credentials", None) or {}
    return creds if isinstance(creds, dict) else {}


def _key_id(connector) -> str:
    return _creds(connector).get("key_id") or getattr(settings, "RAZORPAY_KEY_ID", "") or ""


def _key_secret(connector) -> str:
    return (
        _creds(connector).get("key_secret")
        or getattr(settings, "RAZORPAY_KEY_SECRET", "")
        or ""
    )


def is_configured(connector=None) -> bool:
    """True only when both key id and secret are available."""
    if connector is None:
        return False
    return bool(_key_id(connector) and _key_secret(connector))


def _epoch(value: str, default_days: int) -> int:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (TypeError, ValueError):
        return int((datetime.now(tz=timezone.utc) - timedelta(days=default_days)).timestamp())


def _fetch(connector, since_epoch: int) -> tuple[int, int | None]:
    """Page payments created after ``since_epoch``; return (ingested, newest_epoch)."""
    key_id, key_secret = _key_id(connector), _key_secret(connector)
    tenant = connector.tenant
    ingested = 0
    newest: int | None = None
    skip = 0
    pages = 0
    while pages < 20:
        try:
            resp = requests.get(
                f"{API_BASE}/payments",
                auth=(key_id, key_secret),
                params={"count": PAGE_SIZE, "skip": skip, "from": since_epoch},
                timeout=15,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Razorpay payments poll error: %s", exc)
            break
        if resp.status_code != 200:
            logger.warning(
                "Razorpay payments poll failed (%s): %s", resp.status_code, resp.text[:200]
            )
            break
        try:
            data = resp.json()
        except ValueError:
            break
        items = data.get("items") if isinstance(data, dict) else None
        if not items:
            break
        for item in items:
            try:
                envelope = normalize_razorpay(item)
                ingested += ingest_record(tenant, "razorpay", envelope)
                created = item.get("created_at")
                if created is not None:
                    created = int(created)
                    if newest is None or created > newest:
                        newest = created
            except Exception as exc:  # noqa: BLE001
                logger.debug("skipping malformed Razorpay payment: %s", exc)
        pages += 1
        if len(items) < PAGE_SIZE:
            break
        skip += PAGE_SIZE

    return ingested, newest


def poll(connector, tenant) -> int:
    """Incrementally fetch recent payments. Returns count ingested."""
    if not is_configured(connector):
        return 0
    default_days = DEFAULT_BACKFILL_DAYS
    since = _epoch(get_cursor(connector, CURSOR_KEY, default=""), default_days)
    ingested, newest = _fetch(connector, since)
    set_cursor(
        connector,
        CURSOR_KEY,
        (newest if newest is not None else int(datetime.now(tz=timezone.utc).timestamp())),
    )
    return ingested


def backfill(connector, tenant, days: int = DEFAULT_BACKFILL_DAYS) -> int:
    """Re-pull a wider window (default 7 days) regardless of the stored cursor."""
    if not is_configured(connector):
        return 0
    since = int((datetime.now(tz=timezone.utc) - timedelta(days=days)).timestamp())
    ingested, newest = _fetch(connector, since)
    if newest is not None:
        set_cursor(connector, CURSOR_KEY, newest)
    return ingested
