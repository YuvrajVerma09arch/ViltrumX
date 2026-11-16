"""
API v1 — real implementations over the Week-1 ledger (Postgres), the Week-2
ontology (Neo4j with a Postgres-mirror fallback), Week-3 detection scores,
and Week-4 reports. Response shapes match frontend/src/data/mock.ts exactly
(camelCase — the built frontend depends on them).
"""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from actions import executor
from actions.models import Action, AutonomyPolicy
from django.utils import timezone
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
    RegisterSerializer,
)
from core.tenancy import tenant_for


class RegisterView(APIView):
    """Public: founder signup → User + Tenant + Owner Membership + JWT."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        user = result["user"]
        tenant = result["tenant"]

        # Issue JWT for immediate login
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": {"id": user.id, "email": user.email, "name": result["membership"].display_name},
                "tenant": {"id": tenant.id, "name": tenant.name, "slug": tenant.slug},
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


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

        # A narrative belongs to a real incident in this tenant's ledger. Never
        # fall through to the shared demo fixture for an unknown incident id.
        if not Incident.objects.filter(tenant=self.tenant, external_id=incident_id).exists():
            return Response({"detail": "Not found."}, status=404)
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
        from ontology.models import OntologyNode

        category = request.query_params.get("category", "identities")
        valid = ["cloud", "identities", "repos", "saas"]
        rows = get_inventory(self.tenant, category)
        if rows is None:
            return Response({"detail": f"category must be one of {valid}"}, status=400)
        # get_inventory() falls back to demo fixtures when the tenant has no
        # ontology nodes. An empty customer ledger must stay empty; only the
        # pre-seeded demo tenant may see the fixtures.
        if not _is_demo_tenant(self.tenant) and not OntologyNode.objects.filter(
            tenant=self.tenant
        ).exists():
            return Response([])
        return Response(rows)


class ConnectorListView(TenantAPIView):
    def get(self, request):
        from connectors.models import Connector

        rows = []
        db_states = {c.connector_id: c for c in Connector.objects.filter(tenant=self.tenant)}
        for fixture in demo_data.CONNECTORS:
            state = db_states.get(fixture["id"])
            if state:
                status = state.status
            else:
                # Not configured for this tenant → available
                status = "available"
            rows.append({**fixture, "status": status})
        return Response(rows)


class ConnectorConnectView(TenantAPIView):
    def post(self, request, connector_id: str):
        from connectors.models import Connector
        from ontology import graph as og

        known = {c["id"]: c for c in demo_data.CONNECTORS}
        if connector_id not in known:
            return Response({"detail": "Unknown connector."}, status=404)
        # Only GitHub has a real OAuth flow; the other connectors are demo-only
        # mocks. A customer tenant must not be told they are "connected".
        if not _is_demo_tenant(self.tenant) and connector_id != "gh":
            return Response({"detail": "Connector not implemented."}, status=503)
        connector, _ = Connector.objects.update_or_create(
            tenant=self.tenant, connector_id=connector_id,
            defaults={"name": known[connector_id]["name"], "status": "connected"},
        )

        # Sync connector into ontology graph
        try:
            if connector_id == "gw":
                og.upsert_node(self.tenant, "sa-gw", "Google Workspace", "saas", criticality="high",
                              meta="Identity provider + admin audit", x=560, y=420)
                og.upsert_edge(self.tenant, "e-gw-user", "sa-gw", "u-user", "authenticates_to")
            elif connector_id == "aws":
                og.upsert_node(self.tenant, "sa-aws", "AWS CloudTrail", "cloud", criticality="high",
                              meta="API activity + S3 access", x=820, y=120)
                og.upsert_edge(self.tenant, "e-aws-s3", "sa-aws", "c-s3", "logs_access")
        except Exception:
            pass

        return Response({**known[connector_id], "status": connector.status})


class IngestReplayView(TenantAPIView):
    def post(self, request):
        from connectors.tasks import replay_synthetic_logs

        scenario = request.data.get("scenario", "inc-042")
        result = replay_synthetic_logs.delay(self.tenant.id, scenario)
        return Response({"queued": True, "taskId": str(result.id), "scenario": scenario})


# ── Risk / purple team / compliance ──────────────────────────────────────────
DEMO_TENANT_SLUG = "paykraft"


def _is_demo_tenant(tenant) -> bool:
    """Return True only for the pre-seeded demo tenant."""
    return tenant.slug == DEMO_TENANT_SLUG


class RiskTrendView(TenantAPIView):
    def get(self, request):
        from detection.models import RiskSnapshot

        if not _is_demo_tenant(self.tenant):
            rows = RiskSnapshot.objects.filter(tenant=self.tenant).order_by("day_label")
            if not rows.exists():
                return Response([])
            return Response(
                [{"day": r.day_label, "org": r.org_score, "forecast": r.forecast} for r in rows]
            )
        rows = RiskSnapshot.objects.filter(tenant=self.tenant).order_by("day_label")
        if not rows.exists():
            return Response(demo_data.RISK_TREND)
        return Response(
            [{"day": r.day_label, "org": r.org_score, "forecast": r.forecast} for r in rows]
        )


class EntityRiskView(TenantAPIView):
    def get(self, request):
        from detection.models import EntityRisk

        if not _is_demo_tenant(self.tenant):
            rows = EntityRisk.objects.filter(tenant=self.tenant).order_by("-score")[:5]
            if not rows.exists():
                return Response([])
            return Response(
                [
                    {
                        "entity": r.entity, "type": r.entity_type, "score": r.score,
                        "trend": r.trend, "reason": r.reason,
                    }
                    for r in rows
                ]
            )
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

        if not _is_demo_tenant(self.tenant):
            rows = ReadinessScore.objects.filter(tenant=self.tenant).order_by("id")
            if not rows.exists():
                return Response([])
            return Response([{"week": r.week_label, "score": r.score} for r in rows])
        rows = ReadinessScore.objects.filter(tenant=self.tenant).order_by("id")
        if not rows.exists():
            return Response(demo_data.READINESS_HISTORY)
        return Response([{"week": r.week_label, "score": r.score} for r in rows])


class PurpleScenariosView(TenantAPIView):
    def get(self, request):
        from reports.models import PurpleScenario

        if not _is_demo_tenant(self.tenant):
            rows = PurpleScenario.objects.filter(tenant=self.tenant).order_by("external_id")
            if not rows.exists():
                return Response([])
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
            if not _is_demo_tenant(self.tenant):
                return Response([])
            return Response(demo_data.RECENT_EXPORTS)
        return Response([{"name": r.name, "kind": r.kind, "when": r.when_label} for r in rows])


class ComplianceExportView(TenantAPIView):
    def post(self, request, framework_id: str):
        from reports.compliance import generate_export

        row = generate_export(self.tenant, framework_id, actor=request.user.username)
        if row is None:
            return Response({"detail": "Unknown framework."}, status=404)
        return Response(row, status=201)


class ComplianceExportDownloadView(TenantAPIView):
    """Download the actual PDF file for a compliance export."""
    def get(self, request, framework_id: str):
        from reports.compliance import generate_pdf
        from django.http import FileResponse

        pdf_buffer = generate_pdf(self.tenant, framework_id)
        filename = f"{framework_id}-{self.tenant.slug}-{timezone.now().strftime('%Y%m%d')}.pdf"
        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=filename,
            content_type="application/pdf",
        )


# ── Settings ─────────────────────────────────────────────────────────────────
class MemberListView(TenantAPIView):
    def get(self, request):
        members = Membership.objects.filter(tenant=self.tenant).select_related("user")
        return Response(MemberSerializer(members, many=True).data)


class InvoiceListView(TenantAPIView):
    # stub-tier for viva (BUILD-PLAN: billing stays fixture-backed)
    def get(self, request):
        if not _is_demo_tenant(self.tenant):
            return Response([])
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
