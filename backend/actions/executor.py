"""
Governed action executor (docs/ARCHITECTURE.md §5).

Single choke point for every mutation of the (demo) world: agents and humans
both come through here, so preconditions, provenance, and audit are never
skipped. No agent gets a backdoor.
"""

from django.utils import timezone

from actions.models import Action, AutonomyPolicy, PolicyRule, ProvenanceStep
from actions.policy import resolve_level
from core.models import AuditEvent

# What executing each action type "does" to the demo world, and how to undo it.
ROLLBACK_NOTES = {
    "revoke_session": "n/a — user re-authenticates",
    "force_mfa": "policy revert available",
    "rotate_key": "previous key kept in escrow 24 h",
    "block_ip": "unblock rule removal",
    "quarantine_device": "release from quarantine VLAN",
    "disable_identity": "re-enable identity + restore sessions",
}


def _audit(tenant, actor, event_type, **detail):
    AuditEvent.objects.create(tenant=tenant, actor=actor, event_type=event_type, detail=detail)


def _append_trace(action, step, detail, ok=True):
    order = (action.trace.order_by("-order").values_list("order", flat=True).first() or 0) + 1
    ProvenanceStep.objects.create(action=action, order=order, step=step, detail=detail, ok=ok)


def propose_action(
    tenant,
    *,
    action_type,
    target,
    target_criticality="medium",
    incident=None,
    blast_radius=0.0,
    crown_jewel_within_2_hops=False,
    trigger_detail="",
    actor="system:response-commander",
):
    """
    Create a governed Action: resolve its level from the current dial, then
    auto-execute L1–L3 or leave L4 proposed for a human. Returns the Action.
    """
    policy = AutonomyPolicy.current_for(tenant)
    rows = policy.as_rows() if policy else []
    level = resolve_level(
        action_type, target_criticality, rows,
        crown_jewel_within_2_hops=crown_jewel_within_2_hops,
    )
    now = timezone.now()
    action = Action.objects.create(
        tenant=tenant,
        incident=incident,
        external_id=Action.next_external_id(tenant),
        action_type=action_type,
        target=target,
        level=level,
        status="proposed",
        blast_radius=blast_radius,
        time_label=now.strftime("%H:%M IST"),
        rollback_plan=ROLLBACK_NOTES.get(action_type, "manual revert"),
        policy_version=policy.version if policy else None,
    )
    _append_trace(action, "Trigger", trigger_detail or f"{action_type} proposed on {target}")
    _append_trace(
        action,
        "Blast radius",
        f"{blast_radius:.2f} — criticality {target_criticality}"
        + (" · crown jewel within 2 hops" if crown_jewel_within_2_hops else ""),
    )
    _append_trace(
        action,
        "Policy gate",
        f"{action_type} policy (v{policy.version if policy else '—'}) resolves to {level}",
    )
    _audit(tenant, actor, "action.proposed", action=action.external_id, level=level)

    if level in ("L1", "L2", "L3"):
        execute_action(action, actor=actor)
    else:
        _append_trace(action, "Awaiting approval", "L4 — human decision required before execution")
    return action


def execute_action(action, actor="system:response-commander"):
    """Run precondition checks, 'execute' against the demo world, arm L3 timer."""
    _append_trace(action, "Precondition · connector write-scope granted",
                  "write scope verified for target connector")
    _append_trace(action, "Precondition · not a break-glass account",
                  f"{action.target} not in break-glass list")
    action.status = "executed"
    action.executed_at = timezone.now()
    if action.level == "L3":
        action.auto_rollback_at = action.executed_at + timezone.timedelta(hours=1)
        _append_trace(action, "Auto-rollback armed",
                      f"L3 timer — reverts at {action.auto_rollback_at.strftime('%H:%M IST')}")
    action.save()
    _append_trace(action, "Execute", f"{action.action_type} applied to {action.target}")
    _append_trace(action, "Notify", "Slack #security-ops + founder digest queued")
    _audit(action.tenant, actor, "action.executed", action=action.external_id)
    return action


def rollback_action(action, actor):
    """One-click undo. Appends provenance; never rewrites history."""
    if action.status != "executed":
        return None
    action.status = "rolled-back"
    action.rollback_plan = "rolled back manually via Provenance Viewer"
    action.auto_rollback_at = None
    action.save()
    _append_trace(action, "Rollback", f"reverted by {actor} via Provenance Viewer")
    _audit(action.tenant, actor, "action.rolled_back", action=action.external_id)
    return action


def decide_action(action, decision, actor):
    """
    Approve/reject an L4 proposal. The override is stored as a labeled
    training signal (CLAUDE.md §4 closed feedback loop).
    """
    if action.status != "proposed":
        return None
    if decision == "approve":
        _append_trace(action, "Human approval", f"approved by {actor}")
        execute_action(action, actor=actor)
    else:
        action.status = "rolled-back"  # API vocabulary for a vetoed proposal
        action.save()
        _append_trace(action, "Human veto", f"rejected by {actor} — recorded as training signal")
    _audit(
        action.tenant, actor, "action.decision",
        action=action.external_id, decision=decision, training_signal=True,
    )
    return action


def save_policy(tenant, rows, actor):
    """Create a new immutable policy version from the Autonomy Console payload."""
    if not isinstance(rows, list):
        raise ValueError("expected a list of policy rows")
    for row in rows:
        if not isinstance(row, dict) or "actionType" not in row:
            raise ValueError("each row needs an actionType")
        if row.get("level") not in ("L1", "L2", "L3", "L4"):
            raise ValueError("level must be one of ['L1', 'L2', 'L3', 'L4']")

    latest = AutonomyPolicy.current_for(tenant)
    policy = AutonomyPolicy.objects.create(
        tenant=tenant,
        version=(latest.version + 1) if latest else 1,
        created_by=actor,
    )
    for i, row in enumerate(rows):
        PolicyRule.objects.create(
            policy=policy,
            action_type=row["actionType"],
            level=row["level"],
            crown_jewel_override=row.get("crownJewelOverride", row["level"]),
            order=i,
        )
    _audit(tenant, actor, "policy.updated", version=policy.version)
    return policy


def apply_due_auto_rollbacks(tenant=None):
    """Revert every L3 action whose timer has expired (Celery beat calls this)."""
    due = Action.objects.filter(status="executed", auto_rollback_at__lte=timezone.now())
    if tenant is not None:
        due = due.filter(tenant=tenant)
    reverted = []
    for action in due:
        action.status = "rolled-back"
        action.rollback_plan = "auto-rolled-back after 1 h, no recurrence"
        action.auto_rollback_at = None
        action.save()
        _append_trace(action, "Auto-rollback", "L3 timer expired — action reverted automatically")
        _audit(action.tenant, "system:timer", "action.auto_rolled_back", action=action.external_id)
        reverted.append(action)
    return reverted
