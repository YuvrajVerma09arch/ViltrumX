import pytest

from actions import executor
from actions.models import AutonomyPolicy, PolicyRule
from core.demo_data import DEFAULT_POLICIES
from core.models import Tenant


def _tenant(slug):
    t = Tenant.objects.create(name=slug.title(), slug=slug)
    policy = AutonomyPolicy.objects.create(tenant=t, version=1, created_by="test")
    for i, r in enumerate(DEFAULT_POLICIES):
        PolicyRule.objects.create(policy=policy, action_type=r["actionType"], level=r["level"],
                                  crown_jewel_override=r["crownJewelOverride"], order=i)
    return t


@pytest.mark.django_db
def test_demo_force_mfa_is_manual_not_simulated():
    t = _tenant("paykraft")
    a = executor.propose_action(t, action_type="force_mfa", target="x@paykraft.in",
                                target_criticality="medium", blast_radius=0.1)
    # force_mfa defaults to L2 -> auto-executes -> must land manual even for demo
    a.refresh_from_db()
    print("DEMO force_mfa ->", a.status, a.execution_mode)
    assert a.status == "manual"
    assert a.execution_mode == "manual"


@pytest.mark.django_db
def test_real_zero_connector_all_types_manual():
    t = _tenant("acme")
    for at, tgt in [("disable_identity","a@acme.in"),("revoke_session","a@acme.in"),
                    ("block_ip","8.8.8.8"),("force_mfa","a@acme.in"),("rotate_key","k"),
                    ("quarantine_device","dev"),("page_human","x"),("open_incident","x"),
                    ("totally_unknown_type","z")]:
        a = executor.propose_action(t, action_type=at, target=tgt,
                                    target_criticality="medium", blast_radius=0.1)
        # force any proposed to execute
        if a.status == "proposed":
            executor.decide_action(a, "approve", "t")
        a.refresh_from_db()
        print(f"REAL {at} (level={a.level}) -> status={a.status} mode={a.execution_mode}")
        assert a.status == "manual", f"{at} was {a.status}"


@pytest.mark.django_db
def test_real_connected_workspace_but_global_creds_absent_manual(settings):
    from connectors.models import Connector
    settings.GOOGLE_SERVICE_ACCOUNT_JSON = ""
    settings.GOOGLE_WORKSPACE_ADMIN = ""
    t = _tenant("acme")
    Connector.objects.create(tenant=t, connector_id="gw", name="GW", status="connected",
                             provider="workspace", credentials={})
    a = executor.propose_action(t, action_type="disable_identity", target="v@acme.in",
                                target_criticality="medium", blast_radius=0.1)
    if a.status == "proposed":
        executor.decide_action(a, "approve", "t")
    a.refresh_from_db()
    print("REAL gw-connected, empty creds, no global ->", a.status, a.execution_mode)
    assert a.status == "manual"
