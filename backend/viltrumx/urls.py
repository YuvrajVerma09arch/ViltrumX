from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from connectors.views import GitHubWebhookView
from core import views as v
from core import views_agent as va

api_v1 = [
    # auth
    path("auth/token", TokenObtainPairView.as_view(), name="token"),
    path("auth/token/refresh", TokenRefreshView.as_view(), name="token-refresh"),
    # command deck
    path("agents/status", v.AgentStatusView.as_view(), name="agents-status"),
    path("feed", v.ActivityFeedView.as_view(), name="feed"),
    path("incidents", va.IncidentCollectionView.as_view(), name="incidents"),
    # NOTE: the two literal `incidents/recall*` routes MUST precede
    # `incidents/<str:incident_id>` or the detail route swallows them.
    path("incidents/recall", va.RecallView.as_view(), name="incident-recall"),
    path(
        "incidents/recall/remember",
        va.RememberView.as_view(),
        name="incident-remember",
    ),
    path("incidents/<str:incident_id>", v.IncidentDetailView.as_view(), name="incident-detail"),
    path(
        "incidents/<str:incident_id>/narrative",
        v.IncidentNarrativeView.as_view(),
        name="incident-narrative",
    ),
    # ontology / inventory / onboarding
    path("ontology/graph", v.OntologyGraphView.as_view(), name="ontology-graph"),
    path("ontology/blast-radius", va.BlastRadiusView.as_view(), name="ontology-blast-radius"),
    path("ontology/criticality", va.CriticalityView.as_view(), name="ontology-criticality"),
    path("inventory", v.InventoryView.as_view(), name="inventory"),
    path("connectors", v.ConnectorListView.as_view(), name="connectors"),
    path(
        "connectors/<str:connector_id>/connect",
        v.ConnectorConnectView.as_view(),
        name="connector-connect",
    ),
    path("ingest/replay", v.IngestReplayView.as_view(), name="ingest-replay"),
    path(
        "ingest/scenario/<str:scenario>",
        va.ScenarioEventsView.as_view(),
        name="ingest-scenario",
    ),
    # detection (orchestrator-facing — ARCH §6 service-token surface)
    path("detection/event/<int:event_id>", va.RawEventDetailView.as_view(), name="detection-event"),
    path("detection/score", va.DetectionScoreView.as_view(), name="detection-score"),
    path("detection/noisegate", va.NoiseGateView.as_view(), name="detection-noisegate"),
    path("detection/correlate", va.CorrelateView.as_view(), name="detection-correlate"),
    path("detection/peer-score", va.PeerScoreView.as_view(), name="detection-peer-score"),
    # actions / autonomy / provenance
    path("actions", va.ActionCollectionView.as_view(), name="actions"),
    path("actions/<str:action_id>/trace", v.ActionTraceView.as_view(), name="action-trace"),
    path(
        "actions/<str:action_id>/rollback", v.ActionRollbackView.as_view(), name="action-rollback"
    ),
    path(
        "actions/<str:action_id>/decision", v.ActionDecisionView.as_view(), name="action-decision"
    ),
    path("policies", v.PolicyView.as_view(), name="policies"),
    # risk / purple team / compliance
    path("risk/trend", v.RiskTrendView.as_view(), name="risk-trend"),
    path("risk/entities", v.EntityRiskView.as_view(), name="risk-entities"),
    path("risk/readiness", v.ReadinessView.as_view(), name="risk-readiness"),
    path("risk/forecast", va.RiskForecastView.as_view(), name="risk-forecast"),
    path("purple/scenarios", v.PurpleScenariosView.as_view(), name="purple-scenarios"),
    path("purple/scenarios/<str:scenario_id>/run", v.PurpleRunView.as_view(), name="purple-run"),
    path("compliance/frameworks", v.FrameworksView.as_view(), name="frameworks"),
    path("compliance/exports", v.RecentExportsView.as_view(), name="exports"),
    path(
        "compliance/<str:framework_id>/export",
        v.ComplianceExportView.as_view(),
        name="compliance-export",
    ),
    # settings
    path("members", v.MemberListView.as_view(), name="members"),
    path("billing/invoices", v.InvoiceListView.as_view(), name="invoices"),
    # command-deck feed writer (orchestrator)
    path("tenants/<int:tenant_id>/feed", va.FeedEntryView.as_view(), name="tenant-feed"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("webhooks/github", GitHubWebhookView.as_view(), name="github-webhook"),
]
