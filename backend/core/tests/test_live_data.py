"""A customer's empty ledger must never turn into the demo organization's data."""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.models import Membership, Tenant


@pytest.fixture
def empty_client(db):
    tenant = Tenant.objects.create(name="Customer", slug="empty-customer")
    user = User.objects.create_user("owner@example.com", password="test-password")
    Membership.objects.create(user=user, tenant=tenant, role="Owner", display_name="Owner")
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.parametrize("path", [
    "risk/trend", "risk/entities", "risk/readiness", "purple/scenarios",
    "compliance/exports", "billing/invoices",
    "inventory?category=identities", "inventory?category=cloud",
    "inventory?category=repos", "inventory?category=saas",
])
def test_empty_customer_never_receives_fixtures(empty_client, path):
    response = empty_client.get(f"/api/v1/{path}")
    assert response.status_code == 200
    assert response.json() == []


def test_unknown_incident_never_receives_demo_narrative(empty_client):
    response = empty_client.get("/api/v1/incidents/INC-042/narrative?lang=en")
    assert response.status_code == 404


def test_unimplemented_connector_does_not_claim_connection(empty_client):
    response = empty_client.post("/api/v1/connectors/aws/connect")
    assert response.status_code == 503
    from connectors.models import Connector

    assert not Connector.objects.filter(status="connected").exists()


def test_empty_customer_has_no_compliance_frameworks(empty_client):
    """The framework list is a PayKraft fixture, not a shared catalogue."""
    response = empty_client.get("/api/v1/compliance/frameworks")
    assert response.status_code == 200
    assert response.json() == []


def test_empty_customer_connector_statuses_are_db_driven(empty_client):
    """The catalogue is shared, but connection status must never come from fixtures."""
    response = empty_client.get("/api/v1/connectors")
    assert response.status_code == 200
    rows = response.json()
    assert rows, "the connector catalogue should still be returned"
    assert all(row["status"] == "available" for row in rows)


def test_inventory_fixture_fallback_is_demo_only(empty_client):
    """A customer with nodes in one category must not receive demo fixtures in another.

    The view-level guard checks for *any* ontology node, so this regression is
    only caught by the tenant-scoped guard in ontology.graph.get_inventory.
    """
    from ontology.models import OntologyNode

    tenant = Tenant.objects.get(slug="empty-customer")
    OntologyNode.objects.create(
        tenant=tenant, external_id="c-acme", label="s3://acme-data", node_type="cloud",
    )

    cloud = empty_client.get("/api/v1/inventory?category=cloud").json()
    assert len(cloud) == 1
    assert cloud[0]["name"] == "s3://acme-data"

    for category in ("identities", "repos", "saas"):
        response = empty_client.get(f"/api/v1/inventory?category={category}")
        assert response.status_code == 200
        assert response.json() == []


def test_demo_tenant_still_gets_frameworks_and_inventory(db):
    """The demo tenant keeps its fixtures — the viva demo must not regress."""
    from django.core.management import call_command

    call_command("seed_demo", "--reset")
    demo = User.objects.get(username="arjun.mehta@paykraft.in")
    api = APIClient()
    api.force_authenticate(demo)

    assert api.get("/api/v1/compliance/frameworks").json()
    assert api.get("/api/v1/inventory?category=identities").json()
