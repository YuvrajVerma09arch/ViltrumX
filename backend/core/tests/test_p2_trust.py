"""
P2 regression tests — the trust boundary.

These lock in the behaviours that make ViltrumX safe to hand to two different
customers: role enforcement on writes, cross-tenant isolation, a default
autonomy policy on signup, and per-tenant module entitlements.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from actions.models import AutonomyPolicy
from connectors.models import RawEvent
from core.models import Membership, Tenant


def _make_tenant(slug: str, role: str = "Owner") -> tuple[Tenant, User]:
    tenant = Tenant.objects.create(name=slug.title(), slug=slug)
    user = User.objects.create_user(username=f"u@{slug}.in", email=f"u@{slug}.in",
                                    password="x", is_active=True)
    Membership.objects.create(user=user, tenant=tenant, role=role, display_name="U")
    return tenant, user


def _client(user: User) -> APIClient:
    api = APIClient()
    api.force_authenticate(user=user)
    return api


# ── RBAC ────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_viewer_cannot_approve_action():
    tenant, viewer = _make_tenant("acme", role="Viewer")
    from actions.models import Action

    Action.objects.create(
        tenant=tenant, external_id="ACT-1", action_type="disable_identity",
        target="x", level="L4", status="proposed", blast_radius=0.5,
        time_label="now", rollback_plan="re-enable",
    )
    resp = _client(viewer).post(
        "/api/v1/actions/ACT-1/decision", {"decision": "approve"}, format="json"
    )
    assert resp.status_code == 403, resp.content


@pytest.mark.django_db
def test_viewer_cannot_edit_policy():
    tenant, viewer = _make_tenant("acme", role="Viewer")
    resp = _client(viewer).put(
        "/api/v1/policies",
        [{"actionType": "block_ip", "level": "L1"}],
        format="json",
    )
    assert resp.status_code == 403, resp.content


@pytest.mark.django_db
def test_viewer_cannot_connect_connector():
    tenant, viewer = _make_tenant("acme", role="Viewer")
    resp = _client(viewer).post("/api/v1/connectors/gh/connect")
    assert resp.status_code == 403, resp.content


@pytest.mark.django_db
def test_analyst_can_reject_but_not_edit_policy():
    tenant, analyst = _make_tenant("acme", role="Analyst")
    from actions.models import Action

    Action.objects.create(
        tenant=tenant, external_id="ACT-2", action_type="disable_identity",
        target="x", level="L4", status="proposed", blast_radius=0.5,
        time_label="now", rollback_plan="re-enable",
    )
    assert _client(analyst).post(
        "/api/v1/actions/ACT-2/decision", {"decision": "reject"}, format="json"
    ).status_code == 200
    assert _client(analyst).put(
        "/api/v1/policies", [{"actionType": "block_ip", "level": "L1"}], format="json"
    ).status_code == 403


@pytest.mark.django_db
def test_admin_cannot_grant_owner_invite():
    tenant, admin = _make_tenant("acme", role="Admin")
    resp = _client(admin).post(
        "/api/v1/members/invite",
        {"email": "new@acme.in", "role": "Admin"},
        format="json",
    )
    # Admin may invite an Admin (equal), but never an Owner — role choices
    # exclude Owner from InviteSerializer, so an Owner request is a 400.
    resp2 = _client(admin).post(
        "/api/v1/members/invite", {"email": "o@acme.in", "role": "Owner"}, format="json"
    )
    assert resp.status_code == 201, resp.content
    assert resp2.status_code == 400


# ── Cross-tenant isolation ──────────────────────────────────────────────────
@pytest.mark.django_db
def test_cannot_read_other_tenants_raw_event_by_pk():
    ta, ua = _make_tenant("alpha")
    tb, ub = _make_tenant("beta")
    ev_b = RawEvent.objects.create(
        tenant=tb, source="github", event_type="personal_access_token.create",
        principal="b@beta.in", target="repo", occurred_at=timezone.now(),
    )
    # alpha's user asks for beta's event id → must 404, not leak.
    resp = _client(ua).get(f"/api/v1/detection/event/{ev_b.id}")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_peer_score_only_sees_own_tenant():
    ta, ua = _make_tenant("alpha")
    tb, ub = _make_tenant("beta")
    for _ in range(5):
        RawEvent.objects.create(
            tenant=tb, source="workspace", event_type="login_success",
            principal="b@beta.in", occurred_at=timezone.now(),
        )
    # alpha has no events → peer-z for beta's principal must be 0, not beta's.
    resp = _client(ua).get("/api/v1/detection/peer-score?principal=b@beta.in")
    assert resp.status_code == 200
    assert resp.json()["peer_z"] == 0.0


# ── Default policy on signup ────────────────────────────────────────────────
@pytest.mark.django_db
def test_signup_seeds_default_policy():
    from core.serializers import RegisterSerializer

    s = RegisterSerializer(data={
        "email": "founder@newco.in", "password": "supersecret123",
        "full_name": "Founder", "tenant_name": "NewCo", "tenant_slug": "newco",
    })
    s.is_valid(raise_exception=True)
    out = s.save()
    tenant = out["tenant"]
    policy = AutonomyPolicy.current_for(tenant)
    assert policy is not None
    types = {r["actionType"] for r in policy.as_rows()}
    assert "disable_identity" in types and "block_ip" in types


# ── Per-tenant entitlements (flexibility) ───────────────────────────────────
@pytest.mark.django_db
def test_entitlements_default_to_all_modules():
    tenant, owner = _make_tenant("acme")
    resp = _client(owner).get("/api/v1/tenant/entitlements")
    assert resp.status_code == 200
    body = resp.json()
    assert "command_deck" in body["modules"]
    assert body["connectors_enabled"] == "all"


@pytest.mark.django_db
def test_entitlements_respect_tenant_module_restriction():
    tenant = Tenant.objects.create(
        name="Lite", slug="lite", enabled_modules=["command_deck", "risk"]
    )
    user = User.objects.create_user(username="u@lite.in", email="u@lite.in",
                                    password="x", is_active=True)
    Membership.objects.create(user=user, tenant=tenant, role="Owner", display_name="U")
    body = _client(user).get("/api/v1/tenant/entitlements").json()
    assert body["modules"] == ["command_deck", "risk"]


# ── Action proposal (found by adversarial verify) ───────────────────────────
@pytest.mark.django_db
def test_viewer_cannot_propose_action():
    """A Viewer must not be able to propose an action — proposal can auto-execute
    L2/L3 containment via the policy dial."""
    from actions.models import AutonomyPolicy, PolicyRule
    from core.demo_data import DEFAULT_POLICIES

    tenant, viewer = _make_tenant("acme", role="Viewer")
    policy = AutonomyPolicy.objects.create(tenant=tenant, version=1, created_by="seed")
    for i, r in enumerate(DEFAULT_POLICIES):
        PolicyRule.objects.create(policy=policy, action_type=r["actionType"],
                                  level=r["level"], crown_jewel_override=r["crownJewelOverride"],
                                  order=i)
    resp = _client(viewer).post(
        "/api/v1/actions", {"actionType": "revoke_session", "target": "x"}, format="json"
    )
    assert resp.status_code == 403, resp.content


@pytest.mark.django_db
def test_analyst_can_propose_action():
    from actions.models import AutonomyPolicy, PolicyRule
    from core.demo_data import DEFAULT_POLICIES

    tenant, analyst = _make_tenant("acme", role="Analyst")
    policy = AutonomyPolicy.objects.create(tenant=tenant, version=1, created_by="seed")
    for i, r in enumerate(DEFAULT_POLICIES):
        PolicyRule.objects.create(policy=policy, action_type=r["actionType"],
                                  level=r["level"], crown_jewel_override=r["crownJewelOverride"],
                                  order=i)
    resp = _client(analyst).post(
        "/api/v1/actions", {"actionType": "revoke_session", "target": "x"}, format="json"
    )
    assert resp.status_code in (200, 201), resp.content


# ── Connector entitlement is enforced, not just echoed ──────────────────────
@pytest.mark.django_db
def test_connector_list_respects_entitlement():
    tenant = Tenant.objects.create(
        name="Limited", slug="limited", enabled_connectors=["gh"]
    )
    user = User.objects.create_user(username="u@limited.in", email="u@limited.in",
                                    password="x", is_active=True)
    Membership.objects.create(user=user, tenant=tenant, role="Owner", display_name="U")
    rows = _client(user).get("/api/v1/connectors").json()
    ids = {r["id"] for r in rows}
    assert ids == {"gh"}, f"expected only gh, got {ids}"


@pytest.mark.django_db
def test_unentitled_connector_credentials_forbidden():
    tenant, owner = _make_tenant("acme")
    tenant.enabled_connectors = ["gh"]
    tenant.save(update_fields=["enabled_connectors"])
    resp = _client(owner).post(
        "/api/v1/connectors/aws/credentials", {"provider": "aws"}, format="json"
    )
    assert resp.status_code == 403, resp.content
