"""
Agent 7 — Response Commander (CLAUDE.md §4 #7 + §5, Core tier).

Executes governed actions per the autonomy dial. IMPORTANT: the agent DOES
NOT bypass the policy gate. It calls the Django `/actions` endpoint, which
runs `actions.executor.propose_action` server-side — that function reads the
tenant's current AutonomyPolicy, resolves the level (L1–L4), and either
auto-executes (L1–L3) or parks for a human approval (L4). Our agent only
*reports what happened*.

This separation is what CLAUDE.md §1 calls "trust, not capability": the
buyer needs the autonomy to be safe, auditable, and reversible, not the
need for the model to do more reasoning.

The orchestrator's job here:
  - Decide WHICH action_types to propose for which chain step
  - Pick the target_criticality + crown_jewel_within_2_hops from the
    Investigation agent (so the dial resolves to the correct L1–L4)
  - Fire them via POST /actions with one job per step (dedup by action_type
    + target to avoid duplicate actions on a 12-op burst)
  - Update state with the proposed Actions for the Explainability agent
"""

from __future__ import annotations

import logging

from tools.actions_api import propose_action

logger = logging.getLogger(__name__)

ACTION_TYPE_FOR_FINDING = {
    "impossible_travel": "revoke_session",
    "mfa_fatigue": "force_mfa",
    "token_creation": "rotate_key",
    "secret_discovery": "rotate_key",     # rotate the AWS key from terraform history
    "s3_exfil_burst": "block_ip",
    "data_exfil": "block_ip",
    "insider_export": "page_human",        # ALWAYS L4 — legitimate identity
    "priv_escalation": "disable_identity",# ALWAYS L4 — same dial row backs up
}


def run(state: dict) -> dict:
    if not state.get("critic_passed"):
        state["actions_proposed"] = []
        return state

    chain = state.get("attack_chain", []) or []
    incident_id = state.get("incident_id")
    tenant_id = state.get("tenant_id")
    criticality = state.get("target_criticality", "medium")
    crown_jewel_within_2_hops = bool(state.get("crown_jewel_within_2_hops"))
    blast = float(state.get("blast_radius") or 0.0)

    proposed, failed = [], []
    seen = set()  # dedup by (action_type, target) so a burst → one action
    for step in chain:
        finding = step.get("finding_type")
        action_type = ACTION_TYPE_FOR_FINDING.get(finding)
        if not action_type:
            continue
        target = step.get("entity") or state.get("principal") or "unknown"
        key = (action_type, target)
        if key in seen:
            continue
        seen.add(key)

        action = propose_action(
            tenant_id,
            action_type=action_type,
            target=target,
            incident_id=incident_id,
            target_criticality=step.get("criticality", criticality),
            blast_radius=blast,
            crown_jewel_within_2_hops=crown_jewel_within_2_hops,
            trigger_detail=f"{finding} → {step.get('step', action_type)} "
                          f"(MITRE {step.get('mitre', '—')})",
        )
        if action:
            proposed.append(action)
        else:
            failed.append({"action_type": action_type, "target": target,
                           "reason": "backend-rejected"})

    state["actions_proposed"] = proposed
    state["actions_failed"] = failed
    if proposed:
        logger.info("respond: proposed %d actions for %s",
                    len(proposed), incident_id or state.get("principal"))
    return state
