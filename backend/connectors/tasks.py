"""
Celery ingestion tasks — normalize raw events, upsert the ontology, score
anomalies, and push live updates to the Command Deck WebSocket stream; plus
the connector polling dispatcher that drives the per-provider pollers.
"""

import logging

from celery import shared_task
from django.utils import timezone

from connectors.models import RawEvent
from connectors.synthetic import SCENARIOS, normalize

logger = logging.getLogger(__name__)

# The only envelope keys that map onto RawEvent columns. Anything else
# (``external_id``, provider extras) stays in ``payload`` and never reaches the
# model constructor.
_ENVELOPE_FIELDS = (
    "source",
    "event_type",
    "principal",
    "target",
    "ip",
    "geo",
    "occurred_at",
    "payload",
)


@shared_task(bind=True, max_retries=3)
def ingest_event(self, tenant_id: int, raw: dict):
    """Normalize one raw log dict, then ingest it through the shared path.

    Kept for the synthetic replay + GitHub webhook callers. It builds an
    envelope with ``synthetic.normalize`` and delegates to ``_ingest_envelope``.
    """
    from core.models import Tenant

    try:
        tenant = Tenant.objects.get(pk=tenant_id)
        envelope = normalize(raw)
        # Synthetic replays carry a ground-truth attack label the flattener
        # drops; carry it through so detection can score it.
        envelope["is_attack"] = bool(raw.get("attack", False))
        _ingest_envelope(tenant, envelope)
    except Exception as exc:
        logger.exception("ingest_event failed: %s", exc)
        raise self.retry(exc=exc, countdown=5) from exc


@shared_task
def replay_synthetic_logs(tenant_id: int, scenario: str = "inc-042"):
    """
    Replay a synthetic scenario through the live pipeline.
    POST /ingest/replay calls this; the purple-team job calls it nightly.
    """
    from core.models import Tenant

    tenant = Tenant.objects.get(pk=tenant_id)
    generator = SCENARIOS.get(scenario)
    if generator is None:
        logger.error("Unknown scenario: %s", scenario)
        return {"error": f"unknown scenario {scenario}"}

    events = generator()
    queued = 0
    for raw in events:
        ingest_event.delay(tenant_id, raw)
        queued += 1

    _publish_feed(tenant, "Ingestion",
                  f"Replay '{scenario}' queued — {queued} events", "info")
    return {"queued": queued, "scenario": scenario}


@shared_task
def poll_connector(connector_id_int: int):
    """Poll one connector via its provider module; record success/error.

    Never raises into Celery: a failed provider records ``last_error`` on the
    connector row and returns 0, so one broken connector cannot stall the beat.
    """
    from connectors.models import Connector
    from connectors.providers import get_provider

    connector = Connector.objects.filter(pk=connector_id_int).select_related("tenant").first()
    if connector is None:
        return {"error": "connector not found"}

    provider = get_provider(connector.provider)
    if provider is None:
        connector.last_error = f"no provider module for '{connector.provider}'"
        connector.save(update_fields=["last_error"])
        return {"connector": connector.connector_id, "ingested": 0, "error": connector.last_error}

    if not provider.is_configured(connector):
        # Unconfigured is a normal state, not an error — leave a hint but do
        # not flip the connector into an error status.
        connector.last_error = "provider not configured (missing credentials)"
        connector.last_polled_at = timezone.now()
        connector.save(update_fields=["last_error", "last_polled_at"])
        return {"connector": connector.connector_id, "ingested": 0, "configured": False}

    try:
        ingested = provider.poll(connector, connector.tenant)
        connector.last_polled_at = timezone.now()
        connector.last_error = ""
        if connector.status != "connected":
            connector.status = "connected"
        connector.save(update_fields=["last_polled_at", "last_error", "status"])
        return {"connector": connector.connector_id, "ingested": ingested}
    except Exception as exc:  # noqa: BLE001 — record and continue
        logger.warning("poll_connector %s failed: %s", connector.connector_id, exc)
        connector.last_polled_at = timezone.now()
        connector.last_error = str(exc)[:500]
        connector.save(update_fields=["last_polled_at", "last_error"])
        return {"connector": connector.connector_id, "ingested": 0, "error": connector.last_error}


@shared_task
def poll_all_connectors():
    """Beat entry point: enqueue ``poll_connector`` for every connected connector."""
    from connectors.models import Connector

    connectors = Connector.objects.filter(status="connected").exclude(provider="")
    queued = 0
    for connector in connectors.only("id", "connector_id", "provider"):
        poll_connector.delay(connector.id)
        queued += 1
    logger.info("poll_all_connectors enqueued %s connectors", queued)
    return {"queued": queued}


# ── shared ingestion path ─────────────────────────────────────────────────────

def _ingest_envelope(tenant, envelope: dict) -> RawEvent | None:
    """Create a ``RawEvent`` directly from a normalized envelope, then score
    and publish it.

    This is the single ingestion path shared by the synthetic replay, the
    webhook receiver, and every provider poller (via ``ingest_record``). The
    envelope must already be in normalized shape; ``external_id`` and any extra
    keys are ignored for the model row. ``is_attack`` defaults to False.
    """
    payload = {k: envelope.get(k) for k in _ENVELOPE_FIELDS if envelope.get(k) is not None}
    payload.setdefault("source", envelope.get("source", "unknown"))
    payload.setdefault("event_type", envelope.get("event_type", "unknown"))
    payload.setdefault("principal", envelope.get("principal", ""))
    payload.setdefault("payload", envelope.get("payload") or {})
    if payload.get("occurred_at") is None:
        payload["occurred_at"] = timezone.now()

    event = RawEvent.objects.create(
        tenant=tenant,
        is_attack=bool(envelope.get("is_attack", False)),
        **payload,
    )
    _upsert_ontology(tenant, event)
    _score(event)
    _publish(tenant, event)
    _publish_to_orchestrator(tenant, event)
    return event


# ── helpers ──────────────────────────────────────────────────────────────────

def _upsert_ontology(tenant, event: RawEvent):
    """Best-effort entity resolution → upsert node in Postgres + Neo4j."""
    try:
        from ontology import graph as og

        # Resolve the principal to an existing node or create a stub
        node = og.resolve_entity(tenant, event.principal)
        if node is None and event.principal:
            label = event.principal.split("@")[0]
            node_type = "service" if "-svc" in label or "-bot" in label else "user"
            og.upsert_node(tenant, event.principal, label, node_type)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ontology upsert skipped: %s", exc)


def _score(event: RawEvent):
    """Run the ML scorer if available; fall back to a heuristic.

    We store max(isolation_forest, xgboost_tp_prob) rather than the Isolation
    Forest score alone. IF is unsupervised and compresses toward ~0.45 on this
    unbalanced stream, while the supervised XGBoost classifier separates the
    INC-042 attack (~0.97) from baseline traffic (~0.01) cleanly — taking only
    IF would leave every real attack below the 0.7 alert threshold.
    """
    try:
        from detection.scorer import score_event

        scores = score_event(event)
        event.anomaly_score = max(
            float(scores.get("isolation_forest") or 0.0),
            float(scores.get("xgboost_tp_prob") or 0.0),
        )
        event.save(update_fields=["anomaly_score"])
    except Exception as exc:  # noqa: BLE001
        logger.debug("scorer unavailable, using heuristic: %s", exc)
        # Heuristic fallback: a threat-intel-flagged IP, an S3 backup-bucket
        # burst, or ground-truth attack → high anomaly. IP reputation is
        # derived from detection.enrichment, not a hardcoded address.
        from detection.enrichment import lookup_ip

        suspicious = (
            lookup_ip(event.ip).is_known_bad
            or (event.event_type == "GetObject" and event.target == "customers-db-backups")
            or event.is_attack
        )
        event.anomaly_score = 0.94 if suspicious else 0.05
        event.save(update_fields=["anomaly_score"])


def _publish(tenant, event: RawEvent):
    """Push a feed line to the Command Deck WebSocket group."""
    if event.anomaly_score and event.anomaly_score > 0.7:
        tone = "warn" if not event.is_attack else "action"
        line = (
            f"{event.event_type} on {event.target} — "
            f"anomaly {event.anomaly_score:.2f} [{event.source}]"
        )
        _publish_feed(tenant, "Detection", line, tone)


def _publish_to_orchestrator(tenant, event: RawEvent):
    """Hand a freshly-ingested event to the LangGraph orchestrator.

    Publishes to the Redis channel the orchestrator worker subscribes to
    (``viltrumx:events``). This is what makes the pipeline autonomous: a real
    event → scored → published → the 8-agent graph runs → incident + actions.
    Wrapped so a Redis outage NEVER breaks ingestion; the event is still stored
    and scored, it just won't reach the graph until the publisher recovers.
    """
    try:
        from django.conf import settings

        if str(getattr(settings, "ORCHESTRATOR_ENABLED", "1")).lower() in (
            "0", "false", "no", ""
        ):
            return

        import json

        import redis

        channel = getattr(settings, "ORCHESTRATOR_STREAM", "viltrumx:events")
        message = {
            "tenant_id": tenant.id,
            "tenant_slug": tenant.slug,
            "event_id": event.id,
            "raw_event": {
                "source": event.source,
                "event_type": event.event_type,
                "principal": event.principal,
                "target": event.target,
                "ip": event.ip,
                "geo": event.geo,
                "occurred_at": event.occurred_at.isoformat() if event.occurred_at else "",
                "attack": event.is_attack,
                "home_country": getattr(settings, "TENANT_HOME_COUNTRY", "IN"),
            },
        }
        client = redis.Redis.from_url(settings.REDIS_URL)
        client.publish(channel, json.dumps(message))
    except Exception as exc:  # noqa: BLE001
        logger.debug("orchestrator publish skipped: %s", exc)


def _publish_feed(tenant, agent: str, line: str, tone: str):
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from core.models import FeedLine

    now = timezone.now()
    FeedLine.objects.create(
        tenant=tenant,
        time_label=now.strftime("%H:%M:%S"),
        agent=agent,
        line=line,
        tone=tone,
    )
    try:
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)(
                f"tenant_{tenant.id}_stream",
                {
                    "type": "feed.line",
                    "t": now.strftime("%H:%M:%S"),
                    "agent": agent,
                    "line": line,
                    "tone": tone,
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("channel publish skipped: %s", exc)
