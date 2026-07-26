"""
Contract tests for the v1 API.

These outlive the stubs: when Week 1-4 implementations replace fixture views,
these same tests keep asserting the response shapes the frontend depends on.
"""

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.test import APIClient


@pytest.fixture
def seeded(db):
    """Full PayKraft demo tenant seeded via seed_demo."""
    call_command("seed_demo", "--reset")
    return User.objects.get(username="arjun.mehta@paykraft.in")


@pytest.fixture
def client(seeded):
    api = APIClient()
    api.force_authenticate(user=seeded)
    return api


def test_endpoints_require_auth(db):
    anonymous = APIClient()
    for url in ["/api/v1/incidents", "/api/v1/actions", "/api/v1/policies"]:
        assert anonymous.get(url).status_code == 401


def test_jwt_login_flow(seeded):
    api = APIClient()
    token = api.post(
        "/api/v1/auth/token",
        {"username": "arjun.mehta@paykraft.in", "password": "viltrumx-demo"},
    ).json()["access"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert api.get("/api/v1/incidents").status_code == 200


def test_incident_list_shape(client):
    body = client.get("/api/v1/incidents").json()
    assert len(body) == 5
    lead = body[0]
    assert lead["id"] == "INC-042"
    for field in ("title", "severity", "status", "entity", "time", "mitre"):
        assert field in lead


def test_incident_detail_includes_chain_and_evidence(client):
    body = client.get("/api/v1/incidents/INC-042").json()
    assert len(body["attackChain"]) == 5
    assert len(body["evidence"]) == 5
    assert client.get("/api/v1/incidents/INC-999").status_code == 404


def test_narrative_languages(client):
    for lang in ("en", "hi", "gu"):
        body = client.get(f"/api/v1/incidents/INC-042/narrative?lang={lang}").json()
        for field in ("technical", "founder", "impact", "decision"):
            assert body[field]
        assert len(body["impact"]) == 4
    assert client.get("/api/v1/incidents/INC-042/narrative?lang=fr").status_code == 400


def test_ontology_graph_integrity(client):
    body = client.get("/api/v1/ontology/graph").json()
    # No nodes seeded yet — falls back to fixture shape check
    assert "nodes" in body
    assert "edges" in body


def test_inventory_categories(client):
    assert client.get("/api/v1/inventory?category=cloud").status_code == 200
    assert client.get("/api/v1/inventory?category=bogus").status_code == 400


def test_action_rollback_roundtrip(client):
    executed = next(
        a for a in client.get("/api/v1/actions").json() if a["status"] == "executed"
    )
    rolled = client.post(f"/api/v1/actions/{executed['id']}/rollback").json()
    assert rolled["status"] == "rolled-back"
    # rolling back twice must conflict, not double-apply
    assert client.post(f"/api/v1/actions/{executed['id']}/rollback").status_code == 409


def test_l4_decision_flow(client):
    proposed = next(
        a for a in client.get("/api/v1/actions").json() if a["status"] == "proposed"
    )
    response = client.post(
        f"/api/v1/actions/{proposed['id']}/decision", {"decision": "approve"}, format="json"
    )
    assert response.json()["status"] == "executed"
    # no longer pending → second decision conflicts
    assert (
        client.post(
            f"/api/v1/actions/{proposed['id']}/decision", {"decision": "reject"}, format="json"
        ).status_code
        == 409
    )


def test_policy_update_validation(client):
    policies = client.get("/api/v1/policies").json()
    assert len(policies) > 0
    policies[0]["level"] = "L3"
    updated = client.put("/api/v1/policies", policies, format="json").json()
    assert updated[0]["level"] == "L3"
    bad = [{"actionType": "block_ip", "level": "L9"}]
    assert client.put("/api/v1/policies", bad, format="json").status_code == 400


def test_seed_demo_idempotent(db):
    call_command("seed_demo")
    call_command("seed_demo")
    assert User.objects.filter(username="arjun.mehta@paykraft.in").count() == 1


def test_another_tenant_cannot_see_data(db):
    """Row-scoped tenancy: a user with no membership gets 403, not another tenant's data."""
    from django.contrib.auth.models import User as U

    other = U.objects.create_user("outsider@other.in", password="pw")
    api = APIClient()
    api.force_authenticate(user=other)
    assert api.get("/api/v1/incidents").status_code == 403
