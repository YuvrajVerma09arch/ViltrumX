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
