"""
Per-provider connector pollers (P2).

Every module in this package implements the same tiny contract::

    is_configured(connector=None) -> bool   # are credentials present?
    poll(connector, tenant)        -> int   # incremental fetch, return ingested count
    backfill(connector, tenant, days=7) -> int

They all share two helpers defined here:

* :func:`ingest_record` — dedupe a normalized envelope through
  ``IngestedEvent`` then hand it to the one ingestion path in
  ``connectors.tasks._ingest_envelope``.
* :func:`get_cursor` / :func:`set_cursor` — per-connector incremental
  polling position backed by ``PollCursor``.

Providers never crash the caller: network / dependency failures are caught by
``connectors.tasks.poll_connector`` which records ``last_error`` on the
connector row; unconfigured providers short-circuit to ``0``.
"""

from __future__ import annotations

import hashlib
import logging

from connectors.models import IngestedEvent, PollCursor

logger = logging.getLogger(__name__)


def get_cursor(connector, key: str, default: str = "") -> str:
    """Return the stored polling cursor for ``(connector, key)`` or ``default``."""
    row = PollCursor.objects.filter(
        tenant_id=connector.tenant_id,
        connector_id=connector.connector_id,
        cursor_key=key,
    ).first()
    if row is not None and row.cursor_value:
        return row.cursor_value
    return default


def set_cursor(connector, key: str, value) -> None:
    """Persist the polling cursor for ``(connector, key)``. Never raises on empty."""
    if value is None:
        return
    PollCursor.objects.update_or_create(
        tenant_id=connector.tenant_id,
        connector_id=connector.connector_id,
        cursor_key=key,
        defaults={"cursor_value": str(value)},
    )


def _fallback_external_id(source: str, envelope: dict) -> str:
    """Stable synthetic id when a vendor record carries no id of its own."""
    raw = "|".join(
        str(envelope.get(k, ""))
        for k in ("source", "event_type", "principal", "target", "occurred_at")
    )
    digest = hashlib.sha256(raw.encode()).hexdigest()[:40]
    return f"{source}:{digest}"


def ingest_record(tenant, source: str, envelope: dict) -> int:
    """Dedupe + ingest one normalized envelope.

    Returns ``1`` when a new ``RawEvent`` was created, ``0`` when the record was
    a duplicate (already seen) or malformed. Dedupe is keyed on
    ``(tenant, source, external_id)`` via ``IngestedEvent.get_or_create``.
    """
    if not isinstance(envelope, dict):
        return 0

    external_id = str(envelope.get("external_id") or "").strip()
    if not external_id:
        external_id = _fallback_external_id(source, envelope)
    external_id = external_id[:200]

    _, created = IngestedEvent.objects.get_or_create(
        tenant=tenant, source=source, external_id=external_id
    )
    if not created:
        return 0

    # Imported lazily so the providers package can be imported during app
    # loading without pulling in the Celery task module's own imports.
    from connectors.tasks import _ingest_envelope

    env = dict(envelope)
    env.setdefault("source", source)
    _ingest_envelope(tenant, env)
    return 1


def get_provider(name: str):
    """Return the provider module for a connector's ``provider`` slug, or None."""
    name = (name or "").strip().lower()
    if not name:
        return None
    if name in ("github", "gh"):
        from connectors.providers import github

        return github
    if name in ("google", "google_workspace", "google-workspace", "workspace", "gw", "gws"):
        from connectors.providers import google_workspace

        return google_workspace
    if name in ("aws", "cloudtrail"):
        from connectors.providers import aws

        return aws
    if name == "slack":
        from connectors.providers import slack

        return slack
    if name in ("razorpay", "rzp"):
        from connectors.providers import razorpay

        return razorpay
    return None


# Map an incoming connector_id (UI slug) to the canonical provider slug.
CONNECTOR_ID_TO_PROVIDER = {
    "gh": "github",
    "gw": "google",
    "gws": "google",
    "aws": "aws",
    "slack": "slack",
    "rzp": "razorpay",
}


def provider_for_connector_id(connector_id: str, override: str = "") -> str:
    """Resolve a provider slug from a UI connector id, honouring an explicit override."""
    if override:
        return override.strip().lower()
    return CONNECTOR_ID_TO_PROVIDER.get((connector_id or "").lower(), "")


__all__ = [
    "CONNECTOR_ID_TO_PROVIDER",
    "get_cursor",
    "get_provider",
    "ingest_record",
    "provider_for_connector_id",
    "set_cursor",
]
