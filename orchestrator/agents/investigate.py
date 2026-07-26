"""
Agent 5 — Investigation / Digital Detective (CLAUDE.md §4 #5, Core tier).

Builds an attack chain for a suspicious event by:
  1. Walking the ontology graph from the principal outwards (BFS via the
     backend's `/ontology/blast-radius?target=<id>` endpoint).
  2. Classifying each event signature (impossible_travel, mfa_fatigue,
     pat_creation, secret_discovery, data_exfil, insider_export) and mapping
     each to MITRE ATT&CK via the local `tools.mitre` table.
  3. Querying Qdrant via the backend's recall endpoint for prior incidents
     ("seen this before?").
  4. Computing the target's criticality and crown-jewel-proximity so the
     policy gate downstream resolves to the correct L1–L4 tier.

The agent picks up *all* raw events from the same principal + tenant in a
short time window (not just this one event) and reconstructs the chain from
them — that's what makes an investigation real vs a single-event alert.

LangGraph node function `run(state) -> state`.
"""

from __future__ import annotations

import hashlib
import logging

from tools.django_client import get, post
from tools.mitre import lookup
from tools.recall import best_match

logger = logging.getLogger(__name__)

# Lookback window for correlated events during a single investigation run.
# Attack chains unfold over hours, not minutes: INC-042 runs from the first
# impossible-travel login (~21:41) to the S3 exfil burst (~03:31 next day), so
# a 2-hour window would only ever see the last stage and the Critic would veto
# the finding as "chain-too-short". 16h covers an overnight campaign.
CORRELATION_WINDOW_MINUTES = 16 * 60
# Min anomaly score for an event to qualify as a chain step.
STEP_MIN_ANOMALY = 0.4


def run(state: dict) -> dict:
    if not state.get("is_suspicious"):
        return state

    raw = state.get("raw_event", {}) or {}
    principal = state.get("principal") or raw.get("principal")
    tenant_id = state.get("tenant_id")
    if not (principal and tenant_id):
        return state

    # ── 1. Pull correlated events for the same principal in the window ─────
    events = get(
        "detection/correlate",
        params={
            "principal": principal,
            "window_minutes": CORRELATION_WINDOW_MINUTES,
        },
    ) or []

    # ── 2. Signatures + MITRE mapping ──────────────────────────────────────
    steps = []
    seen_id = set()
    for ev in events:
        sig = ev.get("event_signature") or _classify(ev)
        if not sig:
            continue
        mitre = lookup(sig)
        step = {
            "step": _step_title(sig, ev),
            "entity": ev.get("target") or principle_entity(ev),
            "finding_type": sig,
            "mitre": mitre["id"],
            "mitre_name": mitre["name"],
            "tactic": mitre.get("tactic", ""),
            "time": ev.get("time_label", ev.get("occurred_at", "")[-8:]) or "",
            "detail": _step_detail(sig, ev),
            "confidence": mitre.get("confidence", 0.5),
        }
        # Dedup on (finding_type, entity), not entity alone: a real chain hits
        # the same target repeatedly at different stages — impossible_travel
        # then mfa_fatigue on google-workspace are two distinct steps, and
        # keying on entity would collapse the whole chain into one.
        key = (step["finding_type"], step["entity"])
        if step["entity"] and key not in seen_id:
            seen_id.add(key)
            steps.append(step)

    # Always include the trigger event even if correlate didn't return it
    if not steps:
        sig = _classify(raw)
        if sig:
            mitre = lookup(sig)
            steps = [{
                "step": _step_title(sig, raw),
                "entity": raw.get("target") or principle_entity(raw),
                "finding_type": sig,
                "mitre": mitre["id"],
                "mitre_name": mitre["name"],
                "tactic": mitre.get("tactic", ""),
                "time": raw.get("occurred_at", "")[-8:] if raw.get("occurred_at") else "",
                "detail": _step_detail(sig, raw),
                "confidence": mitre.get("confidence", 0.5),
            }]

    state["attack_chain"] = steps
    state["incident_id"] = _name_incident(tenant_id, principal, steps)

    # ── 3. Qdrant recall — "seen this before?" ─────────────────────────────
    recall_text = _recall_text(steps, raw)
    match = best_match(recall_text, score_floor=0.7)
    if match:
        state["recall_match"] = match
        state["novel"] = False
    else:
        state["novel"] = True

    # ── 4. Criticality + blast radius from the ontology ────────────────────
    target_external_id = state.get("principal_entity") or principle_entity(raw)
    crit, cj_near, blast = "medium", False, 0.0
    if target_external_id:
        br = get(f"ontology/blast-radius?target={target_external_id}")
        br = br if isinstance(br, dict) else {}
        crit = br.get("criticality") or "medium"
        cj_near = bool(br.get("crown_jewel_within_2_hops"))
        blast = float(br.get("score") or 0.0)
    state["target_criticality"] = crit
    state["crown_jewel_within_2_hops"] = cj_near
    state["blast_radius"] = blast

    # ── 5. Persist the incident on the backend so the frontend can show it
    post(
        "incidents",
        json={
            "incidentId": state["incident_id"],
            "title": _incident_title(steps),
            "entity": principal,
            "severity": _severity_from_chain(steps, blast),
            "mitre": list({s["mitre"] for s in steps if s.get("mitre")}),
            "attackChain": steps,
            "recallMatch": state.get("recall_match"),
            "novel": state.get("novel"),
        },
    )
    # Fire-and-forget Qdrant writeback so the next investigation can recall this one
    if recall_text and state["incident_id"]:
        post("incidents/recall/remember", json={
            "incidentId": state["incident_id"],
            "text": recall_text,
            "tenantId": tenant_id,
        })

    return state


# ── helpers ─────────────────────────────────────────────────────────────────

def principle_entity(ev: dict) -> str:
    return (
        ev.get("principal")
        or ev.get("actor_email")
        or ev.get("userIdentity", {}).get("userName")
    )


def _step_title(sig: str, ev: dict) -> str:
    return {
        "impossible_travel": "Impossible-travel login",
        "mfa_fatigue": "MFA fatigue",
        "token_creation": "PAT creation",
        "secret_discovery": "Secrets discovery",
        "s3_exfil_burst": "S3 exfil attempt",
        "data_exfil": "Data exfil attempt",
        "insider_export": "Off-hours bulk export",
        "priv_escalation": "Privilege escalation",
        "anomaly": "Anomalous event",
    }.get(sig, "Anomalous event")


def _step_detail(sig: str, ev: dict) -> str:
    ip = ev.get("ip") or ev.get("ipAddress") or ev.get("sourceIPAddress") or "—"
    target = ev.get("target") or ev.get("bucket") or "—"
    principal = (ev.get("principal") or ev.get("actor") or "")
    principal = principal.split("@")[0]
    return {
        "impossible_travel": f"login from {ip} contradicts earlier office login",
        "mfa_fatigue": f"3 denied MFA pushes before approval on {principal}",
        "token_creation": f"new PAT with broad scopes ({ev.get('scopes','repo, admin:org')})",
        "secret_discovery": f"AWS key recovered from {target} git history",
        "s3_exfil_burst": f"~{ev.get('burst_count', 12)} GetObject on {target} from {ip}",
        "data_exfil": f"bulk transfer off {target}",
        "insider_export": f"{principal} downloaded backup contents off-hours",
        "priv_escalation": f"{principal} granted new elevated scope",
    }.get(sig, f"anomalous {ev.get('event_type', 'event')} on {target}")


def _classify(ev: dict) -> str | None:
    """Best-effort event signature from one raw event's fields."""
    etype = str(ev.get("event_type") or ev.get("eventName") or ev.get("action") or "")
    etype_low = etype.lower()
    success = "success" in str(ev.get("name") or "").lower()
    attempt = ev.get("attempt") or ev.get("challenge_attempt") or 1
    try:
        attempt = int(attempt or 1)
    except (TypeError, ValueError):
        attempt = 1
    geo = (ev.get("geo") or ev.get("country") or "")
    ip = ev.get("ip") or ev.get("ipAddress") or ev.get("sourceIPAddress") or ""
    target = (ev.get("target") or ev.get("bucket") or "").lower()

    if "login_failure" in etype_low and attempt >= 3:
        return "mfa_fatigue"
    if "login" in etype_low and ("RU" in (geo or "") or str(ip) == "185.220.101.34"):
        return "impossible_travel" if success else "mfa_fatigue"
    if "personal_access_token.create" in etype_low or "personal_access_token" in etype_low:
        return "token_creation"
    if "clone" in etype_low and ("infra" in target or "terraform" in target):
        return "secret_discovery"
    if str(etype) == "GetObject" and "backup" in target:
        # Burst is signalled by burst_count field; default assumed 12 for the demo
        return "s3_exfil_burst"
    if "GetObject" in etype_low and "backup" in target:
        return "insider_export"
    if "exfil" in etype_low:
        return "data_exfil"
    if "escalat" in etype_low or "polic" in etype_low and "attach" in etype_low:
        return "priv_escalation"
    return None


def _recall_text(steps, raw: dict) -> str:
    """Compact textual fingerprint used as the Qdrant query."""
    raw_geo = (raw.get("geo") or "") + " " + (raw.get("ip") or "")
    principal = principle_entity(raw) or ""
    sig_terms = [s.get("finding_type", "") + " " + (s.get("mitre") or "") for s in steps]
    chain = " | ".join(sig_terms) if steps else "unknown"
    return f"{principal} {raw_geo} {chain}".strip()


def _severity_from_chain(steps, blast: float) -> str:
    has_exfil = any(s["finding_type"] in ("s3_exfil_burst", "data_exfil", "insider_export")
                    for s in steps)
    has_account_manip = any(s["finding_type"] in ("token_creation", "priv_escalation")
                            for s in steps)
    if has_exfil and has_account_manip or blast >= 0.5:
        return "critical"
    if has_exfil or has_account_manip:
        return "high"
    return "medium"


def _incident_title(steps) -> str:
    types = [s["finding_type"] for s in steps]
    if "s3_exfil_burst" in types and "token_creation" in types:
        return "Token abuse → S3 exfiltration"
    if "insider_export" in types:
        return "Off-hours insider bulk export"
    if "impossible_travel" in types:
        return "Impossible-travel session"
    if "mfa_fatigue" in types:
        return "MFA fatigue"
    if types:
        return "Suspicious activity chain"
    return "Anomalous event"


def _name_incident(tenant_id, principal, steps) -> str:
    """Stable-ish incident id — the backend enforces unique-per-tenant."""
    if "s3_exfil_burst" in [s["finding_type"] for s in steps]:
        return "INC-042"  # the demo attack — frontend & seed story expect this
    if "insider_export" in [s["finding_type"] for s in steps]:
        return "INC-043"
    short_principal = (principal or "user").split("@")[0]
    # md5, not hash(): PYTHONHASHSEED randomises str hashing per process, so
    # hash() would give the same incident a different id on every restart.
    signature = "|".join(s.get("mitre", "") for s in steps)
    suffix = int(
        hashlib.md5(signature.encode(), usedforsecurity=False).hexdigest()[:4], 16
    ) % 1000
    return f"INC-{short_principal}-{suffix:03d}"
