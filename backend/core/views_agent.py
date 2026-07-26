"""
Orchestrator-facing endpoints — the agent runtime's view of the backend.

Most user-facing endpoints live in core/views.py (JWT-authenticated). This
module is the smaller, service-token-friendly surface that the orchestrator
needs. Both JWT users (analysts on the frontend) and the service token (the
orchestrator) can hit these; authentication is enforced by DRF.

Endpoints exposed:
  Detection:
    GET  /api/v1/detection/event/<id>            — raw event envelope
    GET  /api/v1/detection/score?event_id=<id>   — score one event
    POST /api/v1/detection/noisegate             — cluster lookup for an event
    GET  /api/v1/detection/correlate             — correlate same-principal events
    GET  /api/v1/detection/peer-score?principal=<> — UEBA z-score for principal
  Ontology:
    GET  /api/v1/ontology/blast-radius?target=<id>   — crown-jewel-proximity score
    PUT  /api/v1/ontology/criticality              — onboarding crown-jewel tagging
  Incidents (orchestrator-created) + recall:
    POST /api/v1/incidents                         — create or update incident
    GET  /api/v1/incidents/recall                  — Qdrant similarity lookup
    POST /api/v1/incidents/recall/remember        — Qdrant upsert (training)
  Risk:
    POST /api/v1/risk/forecast                     — scheduled Threat-Prediction job
  Feed:
    POST /api/v1/tenants/<id>/feed                 — write a Command-Deck feed line
"""

from __future__ import annotations

import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from actions import executor
from actions.models import Action
from connectors.models import RawEvent
from core.models import FeedLine, Incident
from core.serializers import ActionSerializer
from core.tenancy import tenant_for

logger = logging.getLogger(__name__)


class _OrchAPIView(APIView):
    """Base for orchestrator-facing endpoints. Same auth rules as Tenanted views:
    JWT (human) or service token (orchestrator). Both yield request.user."""
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.tenant = tenant_for(request)


# ── Detection ────────────────────────────────────────────────────────────────
class RawEventDetailView(_OrchAPIView):
    def get(self, request, event_id: int):
        ev = RawEvent.objects.filter(pk=event_id).first()
        if ev is None:
            return Response({"detail": "Not found."}, status=404)
        return Response({
            "id": ev.id, "source": ev.source, "event_type": ev.event_type,
            "principal": ev.principal, "target": ev.target, "ip": ev.ip,
            "geo": ev.geo, "occurred_at": ev.occurred_at.isoformat(),
            "payload": ev.payload, "anomaly_score": ev.anomaly_score,
            "is_attack": ev.is_attack,
        })


class DetectionScoreView(_OrchAPIView):
    def get(self, request):
        eid = request.query_params.get("event_id")
        if not eid:
            return Response({"detail": "event_id required"}, status=400)
        from detection.scorer import score_event
        ev = RawEvent.objects.filter(pk=eid).first()
        if ev is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(score_event(ev))


class NoiseGateView(_OrchAPIView):
    """The orchestrator posts one event fingerprint; we look up the cluster
    + suppression state via detection.noisegate (trained HDBSCAN)."""
    def post(self, request):
        eid = request.data.get("event_id")
        if not eid:
            # Fall back to the fingerprint the orchestrator already carries
            return Response({"cluster_id": None, "suppressed": False})
        ev = RawEvent.objects.filter(pk=eid).first()
        if ev is None:
            ev = RawEvent.objects.filter(
                principal=request.data.get("principal", ""),
                event_type=request.data.get("eventType", "") or "",
                target=request.data.get("target", "") or "",
            ).first()
        from detection.noisegate import should_suppress
        if ev is None:
            return Response({"cluster_id": None, "suppressed": False})
        return Response({
            "cluster_id": None,
            "suppressed": should_suppress(ev),
        })


class CorrelateView(_OrchAPIView):
    """Pull RawEvents for the same *identity* within a time window — the
    Investigation agent uses these to construct an attack chain.

    Entity resolution matters here (CLAUDE.md §4 Agent 1): the same human
    appears under different principal strings per source — Google Workspace
    and GitHub emit `priya.sharma@paykraft.in`, CloudTrail emits bare
    `priya.sharma`. Matching on the exact string would split one attack into
    two half-chains and the Critic would veto both as "too short", so we
    correlate on the local-part alias set instead.
    """

    def get(self, request):
        principal = request.query_params.get("principal")
        try:
            window_minutes = int(request.query_params.get("window_minutes", 120))
        except ValueError:
            window_minutes = 120
        if not principal:
            return Response({"detail": "principal required"}, status=400)

        from datetime import timedelta

        from django.db.models import Q

        # All principal spellings that resolve to this identity.
        local_part = principal.split("@")[0]
        alias_filter = Q(principal=principal) | Q(principal=local_part) | Q(
            principal__startswith=f"{local_part}@"
        )

        scoped = RawEvent.objects.filter(alias_filter, tenant=self.tenant)
        latest = scoped.order_by("-occurred_at").first()
        if latest is None:
            return Response([])
        start = latest.occurred_at - timedelta(minutes=window_minutes)
        events = scoped.filter(occurred_at__gte=start).order_by("occurred_at")
        return Response([_serialize_correlated(e) for e in events])


class PeerScoreView(_OrchAPIView):
    """UEBA per-principal peer-cohort z-score from a recent window."""
    def get(self, request):
        principal = request.query_params.get("q") or request.query_params.get("principal")
        if not principal:
            return Response({"detail": "q required"}, status=400)
        from datetime import timedelta

        from django.utils import timezone

        from detection.peer_cohort import compute_peer_context

        qs = RawEvent.objects.filter(
            occurred_at__gte=timezone.now() - timedelta(days=7),
        ).order_by("occurred_at")
        ctx = compute_peer_context(qs)
        return Response({
            "principal": principal,
            "peer_z": ctx.get("peer_z_map", {}).get(principal, 0.0),
            "cohort_mean": ctx.get("cohort_mean", 0.0),
            "cohort_std": ctx.get("cohort_std", 1.0),
            "baseline_rate": ctx.get("baseline_rate", {}).get(principal, 0.0),
        })


# ── Ontology ─────────────────────────────────────────────────────────────────
class BlastRadiusView(_OrchAPIView):
    def get(self, request):
        target = request.query_params.get("target")
        if not target:
            return Response({"detail": "target required"}, status=400)
        from ontology.graph import blast_radius, resolve_entity
        result = blast_radius(self.tenant, target) or {}
        result.setdefault("target", target)
        # The Investigation agent reads `criticality` off this response to feed
        # the policy gate, so resolve the node's own tag here too.
        node = resolve_entity(self.tenant, target)
        result["criticality"] = node.criticality if node else "medium"
        return Response(result)


class CriticalityView(_OrchAPIView):
    """Onboarding: founder tags entities as crown-jewel / high / etc."""
    def put(self, request):
        target = request.data.get("target")
        criticality = request.data.get("criticality")
        if not target or criticality not in ("low", "medium", "high", "crown-jewel"):
            return Response({"detail": "target + valid criticality required"}, status=400)
        from ontology.models import OntologyNode
        updated = 0
        # Accept either one id or a list of ids
        targets = target if isinstance(target, list) else [target]
        for t in targets:
            n = OntologyNode.objects.filter(tenant=self.tenant, external_id=t).first()
            if n is None:
                # try by label too
                n = OntologyNode.objects.filter(tenant=self.tenant, label=t).first()
            if n is not None:
                n.criticality = criticality
                n.save(update_fields=["criticality"])
                from ontology import neo
                if neo.is_available():
                    neo.upsert_node(
                        self.tenant.id, n.external_id, n.label, n.node_type,
                        criticality=criticality, compromised=n.compromised, meta=n.meta,
                    )
                updated += 1
        return Response({"updated": updated})


# ── Incidents created by orchestrator + recall ──────────────────────────────
class IncidentCreateView(_OrchAPIView):
    """Upsert an Incident + AttackStep chain authored by the orchestrator.
    Idempotent on (tenant, external_id)."""

    def post(self, request):
        incident_id = request.data.get("incidentId")
        if not incident_id:
            return Response({"detail": "incidentId required"}, status=400)

        incident, _ = Incident.objects.update_or_create(
            tenant=self.tenant, external_id=incident_id,
            defaults={
                "title": request.data.get("title", f"Incident {incident_id}"),
                "entity": request.data.get("entity", ""),
                "severity": request.data.get("severity", "high"),
                "mitre": request.data.get("mitre", []),
            },
        )
        # Replace the attack chain rows atomically
        from core.models import AttackStep
        incident.attack_steps.all().delete()
        for i, step in enumerate(request.data.get("attackChain") or []):
            AttackStep.objects.create(
                incident=incident, order=i,
                time_label=str(step.get("time", "") or "")[:20],
                title=step.get("step", ""),
                detail=step.get("detail", ""),
                mitre=step.get("mitre", ""),
                mitre_name=step.get("mitre_name", ""),
                severity=step.get("severity") or "medium",
            )
        # Confidence: written by Critic
        if request.data.get("critic_confidence") is not None:
            incident.confidence = float(request.data["critic_confidence"])
            incident.save(update_fields=["confidence"])
        return Response({"incidentId": incident.external_id, "id": incident.id})


class RecallView(_OrchAPIView):
    """Qdrant incident-recall via reports.recall."""
    def get(self, request):
        text = request.query_params.get("q")
        if not text:
            return Response({"matches": []})
        k = int(request.query_params.get("k", 5))
        from reports.recall import recall
        return Response({"matches": recall(text, k=k)})


class RememberView(_OrchAPIView):
    def post(self, request):
        from reports.recall import remember
        ok = remember(
            request.data.get("incidentId", ""), request.data.get("text", ""),
            tenant_id=self.tenant.id,
        )
        return Response({"ok": ok})


# ── Risk forecast (Threat-Prediction scheduled job) ────────────────────────
class RiskForecastView(_OrchAPIView):
    def post(self, request):
        from datetime import timedelta

        from django.utils import timezone

        # RiskSnapshot/EntityRisk live in detection (ML-owned), not reports.
        from detection.models import EntityRisk, RiskSnapshot

        window_days = int(request.data.get("window_days", 7))
        from detection.peer_cohort import compute_peer_context, flag_outliers
        qs = RawEvent.objects.filter(
            occurred_at__gte=timezone.now() - timedelta(days=window_days)
        ).order_by("occurred_at")
        ctx = compute_peer_context(qs)
        outliers = flag_outliers(ctx)
        # Write an EntityRisk row per principal — toArray for the dashboard
        for entry in outliers:
            EntityRisk.objects.update_or_create(
                tenant=self.tenant, entity=entry["principal"],
                defaults={
                    "entity_type": "user", "score": min(100, int(abs(entry["z"]) * 25)),
                    "trend": "up", "reason": f"peer-cohort z={entry['z']}",
                },
            )
        # Daily snapshot
        today = timezone.now().strftime("%Y-%m-%d")
        risk_score = min(100, int(sum(out["score"] for out in outliers) or 20))
        RiskSnapshot.objects.update_or_create(
            tenant=self.tenant, day_label=today,
            defaults={"org_score": risk_score, "forecast": max(0, risk_score - 10)},
        )
        return Response({"outliers": outliers, "day": today, "score": risk_score})


# ── Feed ─────────────────────────────────────────────────────────────────────
class FeedEntryView(_OrchAPIView):
    """Orchestrator posts a feed line for the Command Deck."""
    def post(self, request, tenant_id: int):
        from django.utils import timezone
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
        except ImportError:  # Channels not installed — feed still persists
            async_to_sync = None

            def get_channel_layer():
                return None
        agent = request.data.get("agent", "Orchestrator")
        line = request.data.get("line", "")
        tone = request.data.get("tone", "info")
        if not line:
            return Response({"detail": "line required"}, status=400)
        FeedLine.objects.create(
            tenant=self.tenant, time_label=timezone.now().strftime("%H:%M:%S"),
            agent=agent, line=line, tone=tone,
        )
        if async_to_sync is not None:
            try:
                layer = get_channel_layer()
                if layer:
                    async_to_sync(layer.group_send)(
                        f"tenant_{self.tenant.id}_stream",
                        {"type": "feed.line", "t": timezone.now().strftime("%H:%M:%S"),
                         "agent": agent, "line": line, "tone": tone},
                    )
            except Exception as exc:  # noqa: BLE001
                logger.debug("channel publish skipped: %s", exc)
        return Response({"ok": True})


class IncidentCollectionView(APIView):
    """`/incidents` serves two callers on one path:
      GET  — the frontend's incident list (core.views.IncidentListView)
      POST — the Investigation agent upserting an incident it just authored

    DRF routes by path, not verb, so this thin dispatcher keeps the URL the
    orchestrator already posts to (`POST /api/v1/incidents`) without breaking
    the list endpoint the frontend reads.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from core.views import IncidentListView

        return IncidentListView.as_view()(request._request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return IncidentCreateView.as_view()(request._request, *args, **kwargs)


class ScenarioEventsView(_OrchAPIView):
    """Serve a synthetic scenario's events so the orchestrator can replay them.

    The orchestrator is HTTP-only (ARCH §6) — it never imports Django — so the
    demo driver (`python main.py replay`) fetches the scenario through this
    endpoint rather than importing `connectors.synthetic` directly.

    Events are PERSISTED as RawEvent rows before being returned, because the
    Detection agent scores by `event_id`: an event that isn't in the database
    can't be scored, correlated, or attached to an incident.

    Query params:
      persist=false  — return the events without writing them (inspection)
      keep=true      — append instead of replacing this scenario's prior rows

    By default a replay REPLACES the scenario's previous events, so running the
    demo repeatedly doesn't stack duplicate bursts that skew correlation and
    the ML baselines.
    """

    def get(self, request, scenario: str):
        from connectors.models import RawEvent
        from connectors.synthetic import SCENARIOS, normalize

        generator = SCENARIOS.get(scenario)
        if generator is None:
            return Response(
                {"detail": f"unknown scenario; try {sorted(SCENARIOS)}"}, status=404
            )
        persist = request.query_params.get("persist", "true").lower() != "false"
        keep = request.query_params.get("keep", "false").lower() == "true"

        rows = [(raw, normalize(raw)) for raw in generator()]

        if persist and not keep:
            # Replace prior rows for exactly this scenario's event window.
            stamps = [env["occurred_at"] for _, env in rows if env.get("occurred_at")]
            if stamps:
                RawEvent.objects.filter(
                    tenant=self.tenant,
                    occurred_at__gte=min(stamps),
                    occurred_at__lte=max(stamps),
                ).delete()

        events = []
        for raw, envelope in rows:
            is_attack = raw.get("attack", False)
            event_id = None
            if persist:
                row = RawEvent.objects.create(
                    tenant=self.tenant, is_attack=is_attack, **envelope
                )
                event_id = row.id
            occurred = envelope.get("occurred_at")
            events.append(
                {
                    "id": event_id,
                    "raw": {
                        **{k: v for k, v in envelope.items() if k != "occurred_at"},
                        "occurred_at": occurred.isoformat() if occurred else None,
                        "attack": is_attack,
                    },
                }
            )
        return Response({"scenario": scenario, "count": len(events), "events": events})


# ── Governed actions (Response Commander's only door) ───────────────────────
class ActionCreateView(_OrchAPIView):
    """Propose a governed Action — the Response Commander's single entry point.

    The agent does NOT get to choose the autonomy level. It states what it
    wants to do and to whom; the backend resolves the level from this tenant's
    dial via `actions.policy.resolve_level`, then auto-executes L1–L3 or parks
    L4 for a human (CLAUDE.md §5). That inversion is the whole trust model —
    an agent can never talk itself into a higher privilege.

    Criticality and blast radius are re-derived from the ontology here rather
    than trusted from the request, so a buggy or compromised agent cannot
    understate blast radius to dodge the L4 gate.
    """

    def post(self, request):
        action_type = request.data.get("actionType")
        target = request.data.get("target")
        if not action_type or not target:
            return Response({"detail": "actionType + target required"}, status=400)

        known_types = set(executor.ROLLBACK_NOTES) | {"page_human", "open_incident"}
        if action_type not in known_types:
            # Unknown types are not rejected — resolve_level fails them safe to
            # L4 — but we record the surprise for the audit trail.
            logger.warning("unknown actionType from agent: %s", action_type)

        incident = None
        incident_id = request.data.get("incidentId")
        if incident_id:
            incident = Incident.objects.filter(
                tenant=self.tenant, external_id=incident_id
            ).first()

        criticality, blast, cj_near = self._ground_in_ontology(target, request.data)

        # Idempotency: a 12-request S3 burst runs the graph 12 times and each
        # run re-proposes the same containment. One (incident, type, target)
        # gets ONE action — otherwise Provenance fills with duplicates and the
        # demo shows 60 actions for a 5-step chain. Re-proposing returns the
        # existing action unchanged (200, not 201).
        if incident is not None:
            existing = Action.objects.filter(
                tenant=self.tenant,
                incident=incident,
                action_type=action_type,
                target=target,
            ).first()
            if existing is not None:
                return Response(ActionSerializer(existing).data)

        action = executor.propose_action(
            self.tenant,
            action_type=action_type,
            target=target,
            target_criticality=criticality,
            incident=incident,
            blast_radius=blast,
            crown_jewel_within_2_hops=cj_near,
            trigger_detail=request.data.get("triggerDetail", ""),
            actor=request.user.username or "system:response-commander",
        )
        return Response(ActionSerializer(action).data, status=201)

    def _ground_in_ontology(self, target: str, payload: dict):
        """Resolve the target to an ontology node and read its real criticality
        + blast radius. Falls back to the agent's claim only when the target
        isn't in the graph (e.g. a raw IP for block_ip)."""
        from ontology.graph import blast_radius, resolve_entity

        claimed_crit = payload.get("targetCriticality", "medium")
        try:
            claimed_blast = float(payload.get("blastRadius", 0.0) or 0.0)
        except (TypeError, ValueError):
            claimed_blast = 0.0
        claimed_cj = bool(payload.get("crownJewelWithin2Hops"))

        node = resolve_entity(self.tenant, target)
        if node is None:
            return claimed_crit, claimed_blast, claimed_cj

        result = blast_radius(self.tenant, node.external_id) or {}
        return (
            node.criticality,
            float(result.get("score", claimed_blast)),
            bool(result.get("crown_jewel_within_2_hops", claimed_cj)),
        )


class ActionCollectionView(APIView):
    """`/actions` — GET lists (frontend), POST proposes (Response Commander)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from core.views import ActionListView

        return ActionListView.as_view()(request._request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return ActionCreateView.as_view()(request._request, *args, **kwargs)


# ── helpers ──────────────────────────────────────────────────────────────────
def _serialize_correlated(event: RawEvent) -> dict:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "eventType": event.event_type,  # camelCase alias — matches the API contract
        "principal": event.principal,
        "target": event.target,
        "ip": event.ip,
        "geo": event.geo,
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        "time_label": (event.occurred_at.strftime("%H:%M") if event.occurred_at else ""),
        "anomaly_score": event.anomaly_score,
        "is_attack": event.is_attack,
        "payload": event.payload or {},
        "event_signature": _classify(event),
    }


def _classify(event: RawEvent) -> str | None:
    etype = event.event_type or ""
    elow = etype.lower()
    payload = event.payload or {}
    attempt = payload.get("attempt") or payload.get("challenge_attempt") or 1

    if "login_failure" in elow:
        try:
            if int(attempt) >= 3:
                return "mfa_fatigue"
        except (TypeError, ValueError):
            pass
    if "login" in elow and ("RU" in (event.geo or "") or "185.220" in (event.ip or "")):
        return "impossible_travel"
    if "personal_access_token" in elow or "personal_access_token.create" == elow:
        return "token_creation"
    if "clone" in elow:
        return "secret_discovery"
    if elow == "getobject" and "backup" in (event.target or "").lower():
        # Burst heuristic: ≥4 GetObject in last 60 seconds → exfil
        from datetime import timedelta

        recently = RawEvent.objects.filter(
            principal=event.principal, event_type="GetObject",
            target=event.target, occurred_at__gte=event.occurred_at - timedelta(seconds=60),
            occurred_at__lte=event.occurred_at,
        ).count()
        if recently >= 4:
            return "s3_exfil_burst"
        return "insider_export" if event.ip and "49." in event.ip else None
    return None
