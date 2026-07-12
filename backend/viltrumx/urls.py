from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core import views as v

api_v1 = [
    # auth
    path("auth/token", TokenObtainPairView.as_view(), name="token"),
    path("auth/token/refresh", TokenRefreshView.as_view(), name="token-refresh"),
    # command deck
    path("agents/status", v.AgentStatusView.as_view(), name="agents-status"),
    path("feed", v.ActivityFeedView.as_view(), name="feed"),
    path("incidents", v.IncidentListView.as_view(), name="incidents"),
    path("incidents/<str:incident_id>", v.IncidentDetailView.as_view(), name="incident-detail"),
    path(
        "incidents/<str:incident_id>/narrative",
        v.IncidentNarrativeView.as_view(),
        name="incident-narrative",
    ),
    # ontology / inventory / onboarding
    path("ontology/graph", v.OntologyGraphView.as_view(), name="ontology-graph"),
    path("inventory", v.InventoryView.as_view(), name="inventory"),
    path("connectors", v.ConnectorListView.as_view(), name="connectors"),
    # actions / autonomy / provenance
    path("actions", v.ActionListView.as_view(), name="actions"),
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
    path("purple/scenarios", v.PurpleScenariosView.as_view(), name="purple-scenarios"),
    path("compliance/frameworks", v.FrameworksView.as_view(), name="frameworks"),
    path("compliance/exports", v.RecentExportsView.as_view(), name="exports"),
    # settings
    path("members", v.MemberListView.as_view(), name="members"),
    path("billing/invoices", v.InvoiceListView.as_view(), name="invoices"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
]
