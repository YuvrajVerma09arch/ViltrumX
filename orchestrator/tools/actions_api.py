"""
Governed Actions API tool (CLAUDE.md §4 Agent 7, ARCH §6).

The Response Commander NEVER bypasses the policy gate. It asks the backend
to propose the action; the backend runs `resolve_level` from the per-tenant
autonomy dial, persists provenance, and either auto-executes (L1–L3) or
leaves it proposed for a human (L4). The agent simply reports what happened.

POST /api/v1/actions now exists on the backend and accepts the service token.
"""

from __future__ import annotations

import logging

from tools.django_client import post

logger = logging.getLogger(__name__)


# Map an attack finding to a *primary* containment action. Each finding picks
# a low-blast L2 where reversible, an L3 timer where temporary, and an L4
# proposal where blast radius crosses crown-jewel proximity. These are
# *hints* — the dial is the source of truth, not the agent.
ACTION_TYPE_FOR_FINDING = {
    "impossible_travel": "revoke_session",
    "mfa_fatigue": "force_mfa",
    "token_abuse": "revoke_session",        # also rotate the PAT downstream
    "pat_creation": "rotate_key",
    "secret_discovery": "rotate_key",       # the AWS key lives in the repo
    "data_exfil": "block_ip",
    "insider_export": "page_human",         # ALWAYS human-in-the-loop for a legit identity
    "priv_escalation": "disable_identity",
}


def propose_action(tenant_id: int, *, action_type: str, target: str,
                   incident_id: str | None = None,
                   target_criticality: str = "medium",
                   blast_radius: float = 0.0,
                   crown_jewel_within_2_hops: bool = False,
                   trigger_detail: str = "") -> dict | None:
    """Propose a governed Action. Returns the persisted action (or None)."""
    payload = {
        "actionType": action_type,
        "target": target,
        "targetCriticality": target_criticality,
        "blastRadius": blast_radius,
        "crownJewelWithin2Hops": crown_jewel_within_2_hops,
        "triggerDetail": trigger_detail or f"{action_type} proposed on {target}",
    }
    if incident_id:
        payload["incidentId"] = incident_id
    result = post("actions", json=payload)
    if result is None:
        logger.warning("propose_action: backend rejected %s on %s", action_type, target)
    return result


def propose_for_finding(finding: dict, tenant_id: int) -> list:
    """Given an Investigation finding (list of attack_chain steps), propose a
    sequence of governed actions covering each step. Returns the persisted
    Actions (or [] on failure).

    Order matters: revoke_session before block_ip so we cut access before
    containment. We pick one action per meaningful step (dedup by action_type
    + target) to avoid spamming the Provenance viewer with 12 identical GetObject rows.
    """
    chain = finding.get("attack_chain", [])
    incident_id = finding.get("incident_id")
    cj = bool(finding.get("crown_jewel_within_2_hops"))
    crit = finding.get("target_criticality", "medium")
    proposed = []
    seen = set()
    for step in chain:
        finding_type = step.get("finding_type") or _infer_finding_type(step)
        action_type = step.get("action_type") or ACTION_TYPE_FOR_FINDING.get(finding_type)
        if not action_type:
            continue
        target = step.get("entity") or step.get("target") or "unknown"
        dedup_key = (action_type, target)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        action = propose_action(
            tenant_id,
            action_type=action_type,
            target=target,
            incident_id=incident_id,
            target_criticality=step.get("criticality", crit),
            blast_radius=float(finding.get("blast_radius", 0.0)),
            crown_jewel_within_2_hops=cj,
            trigger_detail=f"{finding_type} → {step.get('step', action_type)}",
        )
        if action:
            proposed.append(action)
    return proposed


def _infer_finding_type(step: dict) -> str:
    """Best-effort mapping from an attack-chain step to a finding id."""
    text = " ".join(str(v) for v in step.values()).lower()
    if "impossible" in text or "travel" in text:
        return "impossible_travel"
    if "mfa" in text and "fatigue" in text:
        return "mfa_fatigue"
    if "pat" in text or "personal_access_token" in text:
        return "pat_creation"
    if "pat" in text or "token" in text:
        return "token_abuse"
    if "secret" in text or "terraform" in text or "key" in text:
        return "secret_discovery"
    if "exfil" in text or "getobject" in text:
        return "data_exfil"
    if "insider" in text or "deepa" in text:
        return "insider_export"
    if "escalat" in text:
        return "priv_escalation"
    return "anomaly"
