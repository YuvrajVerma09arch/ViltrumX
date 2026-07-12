"""
Stub API v1 — serves the PayKraft fixtures so the frontend runs against a real
authenticated server from day 0.

YUVRAJ: this file is your worklist. Each view has a `# WEEK n:` note saying
what replaces it (see docs/BUILD-PLAN.md). Replace stubs one at a time; the
frontend can't tell the difference as long as the response shape holds.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from actions import demo_state
from core import demo_data
from reports.demo_narratives import NARRATIVE


class FixtureView(APIView):
    """Return a static fixture. Subclasses set `payload`."""

    permission_classes = [IsAuthenticated]
    payload: object = None

    def get(self, request, **kwargs):
        return Response(self.payload)


# ── Command Deck ─────────────────────────────────────────────────────────────
class AgentStatusView(FixtureView):
    # WEEK 3: orchestrator heartbeats via Redis instead of a fixture
    payload = demo_data.AGENTS


class ActivityFeedView(FixtureView):
    # WEEK 3: tail of the per-tenant Redis event stream
    payload = demo_data.ACTIVITY_FEED


class IncidentListView(FixtureView):
    # WEEK 1: Incident.objects.for_tenant(request.user) + serializer
    payload = demo_data.INCIDENTS


class IncidentDetailView(APIView):
    # WEEK 1: get_object_or_404 on the Incident model
    permission_classes = [IsAuthenticated]

    def get(self, request, incident_id: str):
        incident = next((i for i in demo_data.INCIDENTS if i["id"] == incident_id), None)
        if incident is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(
            {**incident, "attackChain": demo_data.ATTACK_CHAIN, "evidence": demo_data.EVIDENCE}
        )


class IncidentNarrativeView(APIView):
    # WEEK 4: grounded LLM generation (Groq/Ollama) + IndicTrans2 rendering
    permission_classes = [IsAuthenticated]

    def get(self, request, incident_id: str):
        lang = request.query_params.get("lang", "en")
        if lang not in NARRATIVE:
            return Response({"detail": f"lang must be one of {sorted(NARRATIVE)}"}, status=400)
        return Response(NARRATIVE[lang])


# ── Ontology / inventory / onboarding ────────────────────────────────────────
class OntologyGraphView(FixtureView):
    # WEEK 2: Cypher MATCH over Neo4j, tenant-scoped
    payload = {"nodes": demo_data.ONT_NODES, "edges": demo_data.ONT_EDGES}


class InventoryView(APIView):
    # WEEK 2: derived from ontology objects by label
    permission_classes = [IsAuthenticated]
    CATEGORIES = {
        "identities": demo_data.INV_IDENTITIES,
        "cloud": demo_data.INV_CLOUD,
        "repos": demo_data.INV_REPOS,
        "saas": demo_data.INV_SAAS,
    }

    def get(self, request):
        category = request.query_params.get("category", "identities")
        if category not in self.CATEGORIES:
            valid = sorted(self.CATEGORIES)
            return Response({"detail": f"category must be one of {valid}"}, status=400)
        return Response(self.CATEGORIES[category])


class ConnectorListView(FixtureView):
    # WEEK 2: Connector model rows + real GitHub connector status
    payload = demo_data.CONNECTORS


# ── Risk / purple team / compliance ──────────────────────────────────────────
class RiskTrendView(FixtureView):
    # WEEK 3: aggregated detection scores from Postgres
    payload = demo_data.RISK_TREND


class EntityRiskView(FixtureView):
    # WEEK 3: top-N entity scores from the detection pipeline
    payload = demo_data.ENTITY_RISK


class ReadinessView(FixtureView):
    # WEEK 4: computed from purple-team run results
    payload = demo_data.READINESS_HISTORY


class PurpleScenariosView(FixtureView):
    # WEEK 4: PurpleScenario model + nightly Celery beat results
    payload = demo_data.PT_SCENARIOS


class FrameworksView(FixtureView):
    # WEEK 4: control-mapping tables + evidence pack generator
    payload = demo_data.FRAMEWORKS


class RecentExportsView(FixtureView):
    payload = demo_data.RECENT_EXPORTS


# ── Settings ─────────────────────────────────────────────────────────────────
class MemberListView(FixtureView):
    # WEEK 1: Membership model + RBAC roles
    payload = demo_data.MEMBERS


class InvoiceListView(FixtureView):
    # stub-tier for viva (BUILD-PLAN: billing stays fixture-backed)
    payload = demo_data.INVOICES


# ── Actions / policies (mutable in-memory stubs — see actions/demo_state.py) ─
class ActionListView(APIView):
    # WEEK 1: Action model + governed lifecycle
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(demo_state.list_actions())


class ActionTraceView(APIView):
    # WEEK 1: ProvenanceStep rows for the action
    permission_classes = [IsAuthenticated]

    def get(self, request, action_id: str):
        if not demo_state.action_exists(action_id):
            return Response({"detail": "Not found."}, status=404)
        return Response(demo_data.PROVENANCE_TRACE)


class ActionRollbackView(APIView):
    # WEEK 1: executor.rollback() + new provenance record + audit event
    permission_classes = [IsAuthenticated]

    def post(self, request, action_id: str):
        action = demo_state.rollback_action(action_id)
        if action is None:
            return Response({"detail": "Not found or not rollbackable."}, status=409)
        return Response(action)


class ActionDecisionView(APIView):
    # WEEK 1: approve/reject an L4 proposal; the override becomes a labeled
    # training signal (CLAUDE.md §4 closed feedback loop)
    permission_classes = [IsAuthenticated]

    def post(self, request, action_id: str):
        decision = request.data.get("decision")
        if decision not in ("approve", "reject"):
            return Response({"detail": "decision must be 'approve' or 'reject'"}, status=400)
        action = demo_state.decide_action(action_id, decision)
        if action is None:
            return Response({"detail": "Not found or not pending."}, status=409)
        return Response(action)


class PolicyView(APIView):
    # WEEK 1: versioned AutonomyPolicy model; PUT creates a new version + audit
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(demo_state.get_policies())

    def put(self, request):
        try:
            return Response(demo_state.set_policies(request.data))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
