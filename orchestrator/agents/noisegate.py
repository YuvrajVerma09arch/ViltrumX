"""
Agent 2 — Triage / Noise-Gate (CLAUDE.md §4 #2 + §6 row 4).

Clusters + dedups alerts, suppresses known-benign duplicates before they
hit expensive downstream agents. We pay for ML scoring once for the
representative event of a cluster, not 1,842 times for every S3 GetObject
in an exfil burst.

Suppression is decided entirely by the backend's HDBSCAN clusterer (which owns
the trained model). The orchestrator carries NO demo fingerprints of its own:
if the backend is unreachable we deliberately do NOT suppress (fail toward
detection — never silently drop a real event).
"""

from __future__ import annotations

import logging

from tools.django_client import post

logger = logging.getLogger(__name__)


def run(state: dict) -> dict:
    raw = state.get("raw_event", {}) or {}
    principal = (raw.get("principal") or "").lower()
    target = (raw.get("target") or "").lower()
    etype = (raw.get("event_type") or "").lower()

    suppressed = False

    # Defer to the backend HDBSCAN clusterer (it has the trained model). The
    # backend returns cluster_id + suppressed flag for this event. If the
    # call fails (backend down, no event_id), we do NOT suppress.
    if state.get("event_id"):
        result = post(
            "detection/noisegate",
            json={"event_id": state["event_id"],
                  "target": target, "eventType": etype, "principal": principal},
        )
        if result:
            state["cluster_id"] = result.get("cluster_id")
            suppressed = bool(result.get("suppressed"))

    state["suppressed"] = suppressed
    if suppressed:
        logger.debug("noisegate: suppressed %s/%s from %s", target, etype, principal)
    return state
