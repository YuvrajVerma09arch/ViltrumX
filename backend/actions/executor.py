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
    """Run precondition checks, apply the action for REAL, arm the L3 timer.

    Nothing is marked ``executed`` unless external state actually changed:
      * real provider call  → status executed, receipt stored
      * no actuator / creds  → status ``manual`` (a human must apply it)
      * provider call errored → status ``failed`` with last_error
    The demo tenant is simulated (clearly labelled) so the viva storyline works.
    """
    from actions import actuators

    _append_trace(
        action, "Precondition · connector write-scope check",
        "resolving actuator + credentials for the target provider",
    )

    result = actuators.actuate(action.tenant, action)
    action.execution_receipt = result.receipt or {}
    action.last_error = result.error or ""

    if result.mode == "failed":
        action.status = "failed"
        action.execution_mode = "failed"
        action.save()
        _append_trace(action, "Execute failed", result.error or "provider call failed", ok=False)
        _audit(action.tenant, actor, "action.failed", action=action.external_id,
               error=result.error[:200])
        return action

    if result.mode == "manual":
        action.status = "manual"
        action.execution_mode = "manual"
        action.rollback_plan = "manual — apply and revert by hand"
        action.save()
        _append_trace(action, "Manual action required", result.detail, ok=False)
        _audit(action.tenant, actor, "action.manual", action=action.external_id)
        return action

    # real OR simulated (demo): treat as executed.
    action.status = "executed"
    action.execution_mode = result.mode  # "real" | "simulated"
    action.executed_at = timezone.now()
    if action.level == "L3":
        action.auto_rollback_at = action.executed_at + timezone.timedelta(hours=1)
        _append_trace(action, "Auto-rollback armed",
                      f"L3 timer — reverts at {action.auto_rollback_at.strftime('%H:%M IST')}")
    action.save()
    label = "simulated (demo)" if result.mode == "simulated" else "applied"
    _append_trace(
        action, "Execute",
        f"{action.action_type} {label} on {action.target} — {result.detail}",
    )
    _audit(action.tenant, actor, "action.executed", action=action.external_id, mode=result.mode)
    return action


def rollback_action(action, actor):
    """One-click undo that actually reverts external state via the receipt."""
    from actions import actuators

    if action.status != "executed":
        return None

    result = actuators.revert(action.tenant, action)

    if result.mode == "failed":
        # Leave it executed — a failed revert means the change is still live.
        action.last_error = result.error or "revert failed"
        action.save(update_fields=["last_error"])
        _append_trace(action, "Rollback failed", result.error or "revert failed", ok=False)
        _audit(action.tenant, actor, "action.rollback_failed", action=action.external_id)
        return None

    if result.mode == "manual":
        # The action's real-world effect cannot be auto-reverted. Record it as
        # still-live and tell the human exactly what to undo.
        action.status = "executed"
        action.rollback_plan = f"manual revert required — {result.detail}"
        action.save(update_fields=["rollback_plan"])
        _append_trace(action, "Manual rollback required", result.detail, ok=False)
        _audit(action.tenant, actor, "action.rollback_manual", action=action.external_id)
        return None

    action.status = "rolled-back"
    action.rollback_plan = "reverted via actuator"
    action.auto_rollback_at = None
    action.save()
    _append_trace(action, "Rollback", f"{action.action_type} reverted by {actor} — {result.detail}")
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
        result = rollback_action(action, "system:timer")
        if result is not None:
            _append_trace(
                result, "Auto-rollback", "L3 timer expired — action reverted automatically"
            )
            _audit(result.tenant, "system:timer", "action.auto_rolled_back",
                   action=result.external_id)
            reverted.append(result)
        else:
            # Could not auto-revert (manual/failed) — stop retrying so the sweep
            # doesn't loop forever; leave the human-facing note on the action.
            action.auto_rollback_at = None
            action.save(update_fields=["auto_rollback_at"])
    return reverted
