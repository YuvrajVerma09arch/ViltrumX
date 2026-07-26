"""
Shared orchestrator state — typed contract for all 8 agents (CLAUDE.md §4).

All keys are optional at graph-entry; agents only read keys their stage needs.
This is the LangGraph state dict that flows through `build_graph().invoke(...)`.
Keys are primitive (str/int/float/list[dict]) so the graph survives a Celery
JSON round-trip without custom serializers.

Stages (their responsibilities — full spec in CLAUDE.md §4):
  sync        — resolve raw_event to ontology nodes, enrich IP/geo
  noisegate   — cluster + suppress known-benign duplicates
  predict     — forecast short-term risk per entity (background job too)
  detect      — ML-driven is_suspicious decision (never LLM)
  investigate — build attack_chain (graph walk + MITRE + recall)
  critic      — adversarially try to refute; only survivors reach respond
  respond     — propose governed actions via the Django policy gate
  explain     — generate EN/HI/GU narrative via the LLM (only LLM agent)
"""

from __future__ import annotations

# Stage names — used as LangGraph node ids. Stable so conditionals can route.
STAGES = (
    "sync",
    "noisegate",
    "predict",
    "detect",
    "investigate",
    "critic",
    "respond",
    "explain",
)

DEFAULT_STATE: dict = {
    "tenant_id": None,
    "raw_event": {},
    "event_id": None,

    # sync outputs
    "principal": None,
    "principal_entity": None,        # ontology node external_id
    "geo_enriched": None,

    # noisegate outputs
    "cluster_id": None,
    "suppressed": False,

    # predict / detect outputs
    "anomaly_score": None,
    "xgb_tp_prob": None,
    "insider_prob": None,
    "peer_zscore": 0.0,
    "is_suspicious": False,

    # investigate outputs
    # list of step dicts:
    #   {step, entity, finding_type, mitre, time, detail, confidence}
    "attack_chain": [],
    "incident_id": None,
    "target_criticality": "medium",
    "crown_jewel_within_2_hops": False,
    "blast_radius": 0.0,
    "recall_match": None,           # {incident_id, score}
    "novel": True,                    # True unless recall found a >0.7 match

    # critic outputs
    "critic_passed": False,
    "critic_confidence": 0.0,
    "critic_refutations": [],

    # respond outputs
    "actions_proposed": [],          # list of Action dicts returned by Django API
    "actions_failed": [],

    # explain outputs
    "narrative": None,                # fetched on-demand by the frontend

    # provenance plumbing
    "stage_log": [],                  # ~10 entries per event for the feed
}


def fresh_state(tenant_id: int, raw_event: dict, event_id: int | None = None) -> dict:
    state = dict(DEFAULT_STATE)
    state.update({
        "tenant_id": tenant_id,
        "raw_event": raw_event or {},
        "event_id": event_id,
    })
    return state
