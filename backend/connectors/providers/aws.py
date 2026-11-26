"""
AWS CloudTrail poller.

Uses ``cloudtrail.lookup_events`` for management events across configured
regions (or behaviours) — the S3 / IAM activity that drives exfiltration and
privilege-escalation detection. Authentication is whatever boto3's default
chain resolves (instance role, env vars, ``~/.aws``, or an explicit
``AWS_ROLE_ARN`` to assume).

boto3 and credentials are both optional; when either is absent
``is_configured`` is False and ``poll`` returns 0 so the platform degrades
gracefully instead of crashing.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from django.conf import settings

from connectors.normalize import normalize_aws_cloudtrail
from connectors.providers import get_cursor, ingest_record, set_cursor

logger = logging.getLogger(__name__)

DEFAULT_BACKFILL_DAYS = 7
CURSOR_KEY = "cloudtrail_since"
DEFAULT_REGIONS = ["ap-south-1"]


def _regions() -> list[str]:
    raw = getattr(settings, "AWS_REGIONS", "") or ""
    if raw:
        return [r.strip() for r in raw.split(",") if r.strip()]
    return DEFAULT_REGIONS


def _session():
    """Return a boto3 Session, optionally assuming ``AWS_ROLE_ARN``."""
    import boto3

    role_arn = getattr(settings, "AWS_ROLE_ARN", "") or ""
    if not role_arn:
        return boto3.session.Session()

    sts = boto3.client("sts")
    assumed = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName="viltrumx-cloudtrail-poller",
    )
    creds = assumed["Credentials"]
    return boto3.session.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )


def is_configured(connector=None) -> bool:
    """True only when boto3 imports and some AWS credentials / role are available."""
    try:
        import boto3
    except ImportError:
        return False
    if getattr(settings, "AWS_ROLE_ARN", ""):
        return True
    try:
        session = boto3.session.Session()
        creds = session.get_credentials()
        return creds is not None
    except Exception:  # noqa: BLE001
        return False


def _default_cursor() -> str:
    return (datetime.now(tz=timezone.utc) - timedelta(days=DEFAULT_BACKFILL_DAYS)).isoformat()


def _parse_since(since: str) -> datetime:
    try:
        dt = datetime.fromisoformat(str(since).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(tz=timezone.utc) - timedelta(days=DEFAULT_BACKFILL_DAYS)


def _event_to_rec(item: dict) -> dict:
    """Flatten a ``lookup_events`` item into the shape the normalizer expects.

    ``lookup_events`` returns ``CloudTrailEvent`` as a JSON *string*; the shared
    normalizer works on the parsed record. Top-level fields (EventId/EventName/
    EventTime) are merged in as a fallback for anything the blob omits.
    """
    blob = item.get("CloudTrailEvent")
    rec: dict = {}
    if isinstance(blob, str) and blob:
        try:
            parsed = json.loads(blob)
            if isinstance(parsed, dict):
                rec = parsed
        except ValueError:
            rec = {}
    elif isinstance(blob, dict):
        rec = dict(blob)
    rec.setdefault("eventID", item.get("EventId"))
    rec.setdefault("eventName", item.get("EventName"))
    et = item.get("EventTime")
    if et is not None:
        rec.setdefault("eventTime", et.isoformat() if hasattr(et, "isoformat") else et)
    if not rec.get("userIdentity"):
        rec["userIdentity"] = {"userName": item.get("Username")}
    return rec


def _fetch(connector, since: datetime) -> tuple[int, datetime | None]:
    """Pull CloudTrail events since ``since`` across regions; return (n, newest)."""
    session = _session()
    tenant = connector.tenant
    ingested = 0
    newest: datetime | None = None
    for region in _regions():
        try:
            client = session.client("cloudtrail", region_name=region)
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not build CloudTrail client for %s: %s", region, exc)
            continue

        next_token = None
        pages = 0
        while pages < 20:
            kwargs = {"StartTime": since, "MaxResults": 50}
            if next_token:
                kwargs["NextToken"] = next_token
            try:
                resp = client.lookup_events(**kwargs)
            except Exception as exc:  # noqa: BLE001
                logger.warning("CloudTrail lookup_events failed in %s: %s", region, exc)
                break

            for item in resp.get("Events", []):
                try:
                    envelope = normalize_aws_cloudtrail(_event_to_rec(item))
                    ingested += ingest_record(tenant, "cloudtrail", envelope)
                    ts = envelope.get("occurred_at")
                    if ts is not None and (newest is None or ts > newest):
                        newest = ts
                except Exception as exc:  # noqa: BLE001
                    logger.debug("skipping malformed CloudTrail event: %s", exc)

            next_token = resp.get("NextToken")
            pages += 1
            if not next_token:
                break

    return ingested, newest


def poll(connector, tenant) -> int:
    """Incrementally fetch new CloudTrail events. Returns count ingested."""
    if not is_configured(connector):
        return 0
    since = _parse_since(get_cursor(connector, CURSOR_KEY, default=_default_cursor()))
    ingested, newest = _fetch(connector, since)
    set_cursor(
        connector,
        CURSOR_KEY,
        (newest or datetime.now(tz=timezone.utc)).isoformat(),
    )
    return ingested


def backfill(connector, tenant, days: int = DEFAULT_BACKFILL_DAYS) -> int:
    """Re-pull a wider window (default 7 days) regardless of the stored cursor."""
    if not is_configured(connector):
        return 0
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    ingested, newest = _fetch(connector, since)
    if newest:
        set_cursor(connector, CURSOR_KEY, newest.isoformat())
    return ingested
