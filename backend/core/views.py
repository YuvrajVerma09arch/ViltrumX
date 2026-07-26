"""
API v1 — real implementations over the Week-1 ledger (Postgres), the Week-2
ontology (Neo4j with a Postgres-mirror fallback), Week-3 detection scores,
and Week-4 reports. Response shapes match frontend/src/data/mock.ts exactly
(camelCase — the built frontend depends on them).
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from actions import executor
from actions.models import Action, AutonomyPolicy
from core import demo_data
from core.models import AgentState, FeedLine, Incident, Membership
from core.serializers import (
    ActionSerializer,
    AgentStateSerializer,
    AttackStepSerializer,
    EvidenceSerializer,
    FeedLineSerializer,
    IncidentSerializer,
    MemberSerializer,
    ProvenanceStepSerializer,
)
from core.tenancy import tenant_for


class TenantAPIView(APIView):
    """Base: resolves the caller's tenant once per request."""

    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.tenant = tenant_for(request)


# ── Command Deck ─────────────────────────────────────────────────────────────
class AgentStatusView(TenantAPIView):
    def get(self, request):
        states = AgentState.objects.filter(tenant=self.tenant)
        return Response(AgentStateSerializer(states, many=True).data)


class ActivityFeedView(TenantAPIView):
    def get(self, request):
        lines = FeedLine.objects.filter(tenant=self.tenant)[:40]
        return Response(FeedLineSerializer(lines, many=True).data)


class IncidentListView(TenantAPIView):
    def get(self, request):
        incidents = Incident.objects.filter(tenant=self.tenant)
        return Response(IncidentSerializer(incidents, many=True).data)


class IncidentDetailView(TenantAPIView):
    def get(self, request, incident_id: str):
        incident = Incident.objects.filter(
            tenant=self.tenant, external_id=incident_id
        ).first()
        if incident is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(
            {
                **IncidentSerializer(incident).data,
                "attackChain": AttackStepSerializer(
                    incident.attack_steps.all(), many=True
                ).data,
                "evidence": EvidenceSerializer(incident.evidence_items.all(), many=True).data,
            }
        )


class IncidentNarrativeView(TenantAPIView):
    def get(self, request, incident_id: str):
        from reports.narratives import get_narrative

        lang = request.query_params.get("lang", "en")
        narrative = get_narrative(self.tenant, incident_id, lang)
        if narrative is None:
            return Response({"detail": "lang must be one of ['en', 'gu', 'hi']"}, status=400)
        return Response(narrative)


# ── Ontology / inventory / onboarding ────────────────────────────────────────
class OntologyGraphView(TenantAPIView):
    def get(self, request):
        from ontology.graph import get_graph

        return Response(get_graph(self.tenant))


class InventoryView(TenantAPIView):
    def get(self, request):
        from ontology.graph import get_inventory

        category = request.query_params.get("category", "identities")
        rows = get_inventory(self.tenant, category)
        if rows is None:
            valid = ["cloud", "identities", "repos", "saas"]
            return Response({"detail": f"category must be one of {valid}"}, status=400)
        return Response(rows)


class ConnectorListView(TenantAPIView):
    def get(self, request):
        from connectors.models import Connector

        rows = []
        states = {c.connector_id: c for c in Connector.objects.filter(tenant=self.tenant)}
        for fixture in demo_data.CONNECTORS:
            state = states.get(fixture["id"])
            rows.append({**fixture, "status": state.status if state else fixture["status"]})
        return Response(rows)


class ConnectorConnectView(TenantAPIView):
    def post(self, request, connector_id: str):
        from connectors.models import Connector

        known = {c["id"]: c for c in demo_data.CONNECTORS}
        if connector_id not in known:
            return Response({"detail": "Unknown connector."}, status=404)
        connector, _ = Connector.objects.update_or_create(
            tenant=self.tenant, connector_id=connector_id,
            defaults={"name": known[connector_id]["name"], "status": "connected"},
        )
        return Response({**known[connector_id], "status": connector.status})


class IngestReplayView(TenantAPIView):
    def post(self, request):
        from connectors.tasks import replay_synthetic_logs

        scenario = request.data.get("scenario", "inc-042")
        result = replay_synthetic_logs.delay(self.tenant.id, scenario)
        return Response({"queued": True, "taskId": str(result.id), "scenario": scenario})


# ── Risk / purple team / compliance ──────────────────────────────────────────
class RiskTrendView(TenantAPIView):
    def get(self, request):
        from detection.models import RiskSnapshot

        # order_by the real column ("day" is the JSON key, day_label is the field)
        rows = RiskSnapshot.objects.filter(tenant=self.tenant).order_by("day_label")
        if not rows.exists():
            return Response(demo_data.RISK_TREND)
        return Response(
            [{"day": r.day_label, "org": r.org_score, "forecast": r.forecast} for r in rows]
        )


class EntityRiskView(TenantAPIView):
    def get(self, request):
        from detection.models import EntityRisk

        rows = EntityRisk.objects.filter(tenant=self.tenant).order_by("-score")[:5]
        if not rows.exists():
            return Response(demo_data.ENTITY_RISK)
        return Response(
            [
                {
                    "entity": r.entity, "type": r.entity_type, "score": r.score,
                    "trend": r.trend, "reason": r.reason,
                }
                for r in rows
            ]
        )


class ReadinessView(TenantAPIView):
    def get(self, request):
        from reports.models import ReadinessScore

        rows = ReadinessScore.objects.filter(tenant=self.tenant).order_by("id")
        if not rows.exists():
            return Response(demo_data.READINESS_HISTORY)
        return Response([{"week": r.week_label, "score": r.score} for r in rows])


class PurpleScenariosView(TenantAPIView):
    def get(self, request):
        from reports.models import PurpleScenario

        rows = PurpleScenario.objects.filter(tenant=self.tenant).order_by("external_id")
        if not rows.exists():
            return Response(demo_data.PT_SCENARIOS)
        return Response(
            [
                {
                    "id": r.external_id, "name": r.name, "desc": r.desc,
                    "lastRun": r.last_run_label, "result": r.result,
                    "detection": r.detection_label, "containment": r.containment_label,
                }
                for r in rows
            ]
        )


class PurpleRunView(TenantAPIView):
    def post(self, request, scenario_id: str):
        from reports.purple import run_scenario

        row = run_scenario(self.tenant, scenario_id)
        if row is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(row)


class FrameworksView(TenantAPIView):
    def get(self, request):
        return Response(demo_data.FRAMEWORKS)


class RecentExportsView(TenantAPIView):
    def get(self, request):
        from reports.models import ComplianceExport

        rows = ComplianceExport.objects.filter(tenant=self.tenant).order_by("-created_at")[:10]
        if not rows.exists():
            return Response(demo_data.RECENT_EXPORTS)
        return Response([{"name": r.name, "kind": r.kind, "when": r.when_label} for r in rows])


class ComplianceExportView(TenantAPIView):
    def post(self, request, framework_id: str):
        from reports.compliance import generate_export

        row = generate_export(self.tenant, framework_id, actor=request.user.username)
        if row is None:
            return Response({"detail": "Unknown framework."}, status=404)
        return Response(row, status=201)


# ── Settings ─────────────────────────────────────────────────────────────────
class MemberListView(TenantAPIView):
    def get(self, request):
        members = Membership.objects.filter(tenant=self.tenant).select_related("user")
        return Response(MemberSerializer(members, many=True).data)


class InvoiceListView(TenantAPIView):
    # stub-tier for viva (BUILD-PLAN: billing stays fixture-backed)
    def get(self, request):
        return Response(demo_data.INVOICES)


# ── Actions / policies (governed lifecycle) ──────────────────────────────────
class ActionListView(TenantAPIView):
    def get(self, request):
        actions = Action.objects.filter(tenant=self.tenant)
        return Response(ActionSerializer(actions, many=True).data)


class ActionTraceView(TenantAPIView):
    def get(self, request, action_id: str):
        action = Action.objects.filter(tenant=self.tenant, external_id=action_id).first()
        if action is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(ProvenanceStepSerializer(action.trace.all(), many=True).data)


class ActionRollbackView(TenantAPIView):
    def post(self, request, action_id: str):
        action = Action.objects.filter(tenant=self.tenant, external_id=action_id).first()
        if action is None or executor.rollback_action(action, request.user.username) is None:
            return Response({"detail": "Not found or not rollbackable."}, status=409)
        return Response(ActionSerializer(action).data)


class ActionDecisionView(TenantAPIView):
    def post(self, request, action_id: str):
        decision = request.data.get("decision")
        if decision not in ("approve", "reject"):
            return Response({"detail": "decision must be 'approve' or 'reject'"}, status=400)
        action = Action.objects.filter(tenant=self.tenant, external_id=action_id).first()
        decided = (
            executor.decide_action(action, decision, request.user.username)
            if action is not None
            else None
        )
        if decided is None:
            return Response({"detail": "Not found or not pending."}, status=409)
        return Response(ActionSerializer(action).data)


class PolicyView(TenantAPIView):
    def get(self, request):
        policy = AutonomyPolicy.current_for(self.tenant)
        return Response(policy.as_rows() if policy else [])

    def put(self, request):
        try:
            policy = executor.save_policy(self.tenant, request.data, request.user.username)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(policy.as_rows())
