"""
Provider-agnostic event normalizers (P1).

Every connector — GitHub audit log, Google Workspace Admin SDK, AWS CloudTrail,
Slack audit logs, Razorpay — produces a different record shape. This module
turns each vendor record into the single ``RawEvent`` envelope the rest of the
pipeline understands:

    {source, event_type, principal, target, ip, geo, occurred_at, payload,
     external_id}

``external_id`` is the provider's own stable id. It is what ``IngestedEvent``
dedupes on, so a poller can re-fetch overlapping windows without creating
duplicate ``RawEvent`` rows.

All functions are pure (no DB, no network) and timezone-aware; any field the
vendor omits degrades to a safe default rather than raising.
"""

from __future__ import annotations

import logging
from datetime import datetime
from datetime import timezone as dt_timezone

logger = logging.getLogger(__name__)


def _parse_iso(value) -> datetime:
    """Parse an ISO-8601 string (``Z`` or offset) into an aware datetime.

    Falls back to ``now`` so a malformed timestamp never drops the whole event.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt_timezone.utc)
    if not value:
        return datetime.now(tz=dt_timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=dt_timezone.utc)
    except (TypeError, ValueError):
        logger.debug("unparseable timestamp %r — defaulting to now", value)
        return datetime.now(tz=dt_timezone.utc)


def _parse_epoch(value) -> datetime:
    """Parse epoch seconds (Slack/Razorpay) into an aware datetime."""
    try:
        return datetime.fromtimestamp(float(value), tz=dt_timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(tz=dt_timezone.utc)


def _str(value, default: str = "") -> str:
    return default if value is None else str(value)


def normalize_github_audit(rec: dict) -> dict:
    """GitHub org audit-log record → envelope.

    This is where ``personal_access_token.create`` and other security-relevant
    admin actions live — events a standard webhook never delivers.
    """
    rec = rec or {}
    actor = _str(rec.get("actor"))
    action = _str(rec.get("action"), "unknown")
    org = _str(rec.get("org"))
    repo = _str(rec.get("repo"))
    event_id = rec.get("@timestamp") or rec.get("_document_id") or rec.get("created_at")
    return {
        "source": "github",
        "event_type": action,
        "principal": actor,
        "target": repo or org or "github",
        "ip": rec.get("actor_ip") or rec.get("actor_ip_address") or None,
        "geo": _str(rec.get("actor_location", {}).get("country_code")
                    if isinstance(rec.get("actor_location"), dict) else ""),
        "occurred_at": _parse_iso(rec.get("created_at")),
        "payload": {
            "org": org,
            "repo": repo,
            "action": action,
            "user_agent": rec.get("user_agent"),
            "token_id": (rec.get("personal_access_token") or {}).get("id"),
            "scopes": rec.get("scopes") or (rec.get("personal_access_token") or {}).get("scopes"),
        },
        "external_id": _str(event_id) or f"{action}:{actor}:{rec.get('created_at', '')}",
    }


def normalize_google_workspace(rec: dict) -> dict:
    """Admin SDK Reports ``activities.list`` record → envelope."""
    rec = rec or {}
    actor = rec.get("actor") or {}
    events = rec.get("events") or [{}]
    first = events[0] or {}
    params = {
        p.get("name"): p.get("value", p.get("intValue", p.get("boolValue")))
        for p in (first.get("parameters") or [])
        if isinstance(p, dict)
    }
    ident = rec.get("id") or {}
    return {
        "source": "workspace",
        "event_type": _str(first.get("name"), "unknown"),
        "principal": _str(actor.get("email") or actor.get("profileId")),
        "target": "google-workspace",
        "ip": rec.get("ipAddress") or None,
        "geo": _str(params.get("geo") or params.get("login_geo") or ""),
        "occurred_at": _parse_iso(ident.get("time")),
        "payload": {
            "mfa": params.get("login_challenge_method"),
            "attempt": params.get("challenge_attempt"),
            "event": _str(first.get("type")),
            "application": ident.get("applicationName"),
        },
        "external_id": _str(ident.get("uniqueQualifier"))
        or _str(ident.get("time")) + ":" + _str(first.get("name")),
    }


def normalize_aws_cloudtrail(rec: dict) -> dict:
    """CloudTrail ``lookup_events`` record → envelope."""
    rec = rec or {}
    user = rec.get("userIdentity") or {}
    req = rec.get("requestParameters") or {}
    principal = (
        user.get("userName")
        or user.get("arn")
        or user.get("type")
        or "unknown"
    )
    return {
        "source": "cloudtrail",
        "event_type": _str(rec.get("eventName"), "unknown"),
        "principal": _str(principal),
        "target": _str(req.get("bucketName") or req.get("resourceName") or "aws"),
        "ip": rec.get("sourceIPAddress") or None,
        "geo": "",
        "occurred_at": _parse_iso(rec.get("eventTime")),
        "payload": {
            "key": req.get("key"),
            "accessKeyId": user.get("accessKeyId"),
            "region": rec.get("awsRegion"),
            "errorCode": rec.get("errorCode"),
            "eventSource": rec.get("eventSource"),
        },
        "external_id": _str(rec.get("eventID"))
        or f"{rec.get('eventName')}:{rec.get('eventTime', '')}",
    }


def normalize_slack(rec: dict) -> dict:
    """Slack audit-logs entry → envelope."""
    rec = rec or {}
    actor = rec.get("actor") or {}
    context = rec.get("context") or {}
    return {
        "source": "slack",
        "event_type": _str(rec.get("action"), "unknown"),
        "principal": _str(actor.get("email") or actor.get("user") or actor.get("type")),
        "target": _str(rec.get("entity") or "slack"),
        "ip": context.get("ip_address") or None,
        "geo": _str(context.get("location", {}).get("country")
                    if isinstance(context.get("location"), dict) else ""),
        "occurred_at": _parse_epoch(rec.get("date_create")),
        "payload": {
            "entity": rec.get("entity"),
            "action": rec.get("action"),
            "details": rec.get("details"),
            "app": (rec.get("details") or {}).get("app_name")
            if isinstance(rec.get("details"), dict) else None,
        },
        "external_id": _str(rec.get("id") or context.get("session_id"))
        or f"{rec.get('action')}:{rec.get('date_create', '')}",
    }


def normalize_razorpay(rec: dict) -> dict:
    """Razorpay webhook / payment entity → envelope."""
    rec = rec or {}
    payload = rec.get("payload") or {}
    entity = (payload.get("payment") or {}).get("entity") or payload.get("entity") or rec
    event_name = _str(rec.get("event"), "payment.event")
    entity_id = _str(entity.get("id") or rec.get("id") or "")
    created = entity.get("created_at") or rec.get("created_at")
    return {
        "source": "razorpay",
        "event_type": event_name,
        "principal": "razorpay",
        "target": _str(entity.get("email") or entity.get("contact") or "razorpay"),
        "ip": entity.get("ip") or None,
        "geo": "",
        "occurred_at": _parse_epoch(created),
        "payload": {
            "amount": entity.get("amount"),
            "currency": entity.get("currency"),
            "status": entity.get("status"),
            "method": entity.get("method"),
            "order_id": entity.get("order_id"),
            "entity_id": entity_id,
        },
        "external_id": entity_id or f"{event_name}:{created}",
    }


NORMALIZERS = {
    "github": normalize_github_audit,
    "workspace": normalize_google_workspace,
    "cloudtrail": normalize_aws_cloudtrail,
    "slack": normalize_slack,
    "razorpay": normalize_razorpay,
}


def normalize(source: str, rec: dict) -> dict:
    """Dispatch to the right normalizer by source key. Falls back to a minimal
    envelope for unknown sources so ingestion never crashes on a new provider."""
    fn = NORMALIZERS.get(source)
    if fn is not None:
        return fn(rec)
    return {
        "source": source or "unknown",
        "event_type": _str((rec or {}).get("event_type"), "unknown"),
        "principal": _str((rec or {}).get("principal")),
        "target": "",
        "ip": (rec or {}).get("ip") or None,
        "geo": "",
        "occurred_at": _parse_iso((rec or {}).get("occurred_at")),
        "payload": rec or {},
        "external_id": _str((rec or {}).get("id")) or None,
    }
