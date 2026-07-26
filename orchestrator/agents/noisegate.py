"""
Agent 2 — Triage / Noise-Gate (CLAUDE.md §4 #2 + §6 row 4).

Clusters + dedups alerts, suppresses known-benign duplicates before they
hit expensive downstream agents. We pay for ML scoring once for the
representative event of a cluster, not 1,842 times for every S3 GetObject
in an exfil burst.

Two suppression paths:
  1. Single-event forearm suppression — known-benign (target, type) for the
     backup-svc principal. Fast path used by the live `detect` agent.
  2. Recall suppression — when this event's `(target, type, hour)` fingerprint
     is identical to a recently-scored-benign cluster, suppress.

We use the backend's `detection/noisegate.py` post-`score_event` for the
single-event path because re-implementing HDBSCAN on the orchestrator side
duplicates 100k of models/clustering work. The orchestrator here just makes
the call: query the backend's `/actions/inspect-suppress` endpoint with the
event fingerprint, and gate downstream stages on the answer.
"""

from __future__ import annotations

import logging

from tools.django_client import post

logger = logging.getLogger(__name__)

# Fast-path fingerprints: same set as detection.noisegate.BENIGN_FINGERPRINTS.
# Kept in sync here so the orchestrator answers without an HTTP fetch.
_KNOWN_BENIGN = {
    ("customers-db-backups", "PutObject"),
    ("paykraft-staging-assets", "PutObject"),
}


def run(state: dict) -> dict:
    raw = state.get("raw_event", {}) or {}
    principal = (raw.get("principal") or "").lower()
    target = (raw.get("target") or "").lower()
    etype = (raw.get("event_type") or "").lower()

    suppressed = False

    # Fast single-event path: backup-svc writing to a backup-bucket is benign.
    if (target, etype) in _KNOWN_BENIGN and "backup-svc" in principal:
        suppressed = True

    # Defer to backend HDBSCAN clusterer (it has the trained model). The
    # backend returns cluster_id + suppressed flag for this event.
    if not suppressed and state.get("event_id"):
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
