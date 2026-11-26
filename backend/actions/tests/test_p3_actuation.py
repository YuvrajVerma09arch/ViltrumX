"""
P3 regression tests — real actuation honesty.

The headline promise of "governed autonomy" is that an executed action really
changed the world. These tests lock in the inverse guarantee: an action is NEVER
marked ``executed`` unless something external actually changed, the demo tenant
is clearly ``simulated``, real tenants without credentials get ``manual``, and a
rollback of a real action uses the stored receipt.
"""

from unittest.mock import patch

import pytest

from actions import executor
from actions.models import AutonomyPolicy, PolicyRule
from core.demo_data import DEFAULT_POLICIES
from core.models import Tenant


def _tenant(slug="acme") -> Tenant:
    t = Tenant.objects.create(name=slug.title(), slug=slug)
    policy = AutonomyPolicy.objects.create(tenant=t, version=1, created_by="test")
    for i, r in enumerate(DEFAULT_POLICIES):
        PolicyRule.objects.create(
            policy=policy, action_type=r["actionType"], level=r["level"],
            crown_jewel_override=r["crownJewelOverride"], order=i,
        )
    return t


def _propose(tenant, action_type, target, level="L2", criticality="medium"):
    # Force a known level by monkeypatching resolve_level result via a policy row.
    return executor.propose_action(
        tenant, action_type=action_type, target=target,
        target_criticality=criticality, blast_radius=0.1,
    )


# ── Demo tenant = simulated, never real ─────────────────────────────────────
@pytest.mark.django_db
def test_demo_tenant_actions_are_simulated_not_real():
    t = _tenant("paykraft")
    a = _propose(t, "block_ip", "8.8.8.8")  # block_ip is L3 → auto-executes
    assert a.status == "executed"
    assert a.execution_mode == "simulated"


# ── Real tenant, no connector creds = manual, NOT executed ──────────────────
@pytest.mark.django_db
def test_real_tenant_without_connector_is_manual_not_executed():
    t = _tenant("acme")  # no connectors configured at all
    a = _propose(t, "disable_identity", "mallory@acme.in")
    # disable_identity defaults to L4, so it parks as proposed; approving it
    # runs the executor, which must land on "manual" (nothing external changed).
    executor.decide_action(a, "approve", "tester@acme.in")
    a.refresh_from_db()
    assert a.status == "manual", "must not claim executed when nothing changed"
    assert a.execution_mode == "manual"


# ── Real tenant with a connected provider = real actuation via mock ─────────
@pytest.mark.django_db
def test_real_tenant_with_github_cred_actuates_for_real():
    from connectors.models import Connector

    t = _tenant("acme")
    Connector.objects.create(
        tenant=t, connector_id="gh", name="GitHub", status="connected",
        provider="github", credentials={"access_token": "t", "org": "acme"},
        github_org_login="acme", github_access_token="t",
    )
    a = _propose(t, "disable_identity", "mallory")

    fake = type("R", (), {"status_code": 204, "text": ""})()
    with patch("actions.actuators.github.requests.delete", return_value=fake) as rm:
        executor.decide_action(a, "approve", "tester@acme.in")
    a.refresh_from_db()
    assert a.status == "executed"
    assert a.execution_mode == "real"
    assert a.execution_receipt.get("login") == "mallory"
    assert rm.called


# ── Provider error = failed, not executed ───────────────────────────────────
@pytest.mark.django_db
def test_provider_error_marks_failed():
    from connectors.models import Connector

    t = _tenant("acme")
    Connector.objects.create(
        tenant=t, connector_id="gh", name="GitHub", status="connected",
        provider="github", credentials={"access_token": "t", "org": "acme"},
        github_org_login="acme", github_access_token="t",
    )
    a = _propose(t, "disable_identity", "mallory")
    import requests as _rq

    with patch("actions.actuators.github.requests.delete",
               side_effect=_rq.RequestException("boom")):
        executor.decide_action(a, "approve", "tester@acme.in")
    a.refresh_from_db()
    assert a.status == "failed"
    assert a.last_error


# ── Rollback of a real action uses the receipt (real revert) ────────────────
@pytest.mark.django_db
def test_rollback_real_action_calls_provider_revert():
    from connectors.models import Connector

    t = _tenant("acme")
    Connector.objects.create(
        tenant=t, connector_id="gh", name="GitHub", status="connected",
        provider="github", credentials={"access_token": "t", "org": "acme"},
        github_org_login="acme", github_access_token="t",
    )
    a = _propose(t, "disable_identity", "mallory")
    ok = type("R", (), {"status_code": 204, "text": ""})()
    with patch("actions.actuators.github.requests.delete", return_value=ok):
        executor.decide_action(a, "approve", "tester@acme.in")
    a.refresh_from_db()
    assert a.status == "executed"

    restored = type("R", (), {"status_code": 200, "text": ""})()
    with patch("actions.actuators.github.requests.put", return_value=restored) as put:
        executor.rollback_action(a, "tester@acme.in")
    a.refresh_from_db()
    assert a.status == "rolled-back"
    assert put.called


# ── A manual action cannot be silently "rolled back" ────────────────────────
@pytest.mark.django_db
def test_rollback_of_manual_action_is_refused():
    t = _tenant("acme")
    a = _propose(t, "disable_identity", "mallory@acme.in")
    executor.decide_action(a, "approve", "tester@acme.in")
    a.refresh_from_db()
    assert a.status == "manual"
    # rollback only applies to executed actions
    assert executor.rollback_action(a, "tester") is None


# ── L3 auto-rollback actually reverts (simulated demo) ──────────────────────
@pytest.mark.django_db
def test_l3_auto_rollback_reverts():
    from datetime import timedelta

    from django.utils import timezone

    t = _tenant("paykraft")
    a = _propose(t, "block_ip", "1.2.3.4")
    assert a.level in ("L2", "L3")
    # Force it to look like a due L3 action.
    a.level = "L3"
    a.status = "executed"
    a.execution_mode = "simulated"
    a.auto_rollback_at = timezone.now() - timedelta(minutes=1)
    a.save()
    reverted = executor.apply_due_auto_rollbacks(tenant=t)
    a.refresh_from_db()
    assert any(r.pk == a.pk for r in reverted)
    assert a.status == "rolled-back"


# ── Inherently-manual action types never auto-execute table talk ────────────
@pytest.mark.django_db
def test_force_mfa_is_manual():
    t = _tenant("acme")
    a = _propose(t, "force_mfa", "x@acme.in")
    assert a.execution_mode == "manual"
