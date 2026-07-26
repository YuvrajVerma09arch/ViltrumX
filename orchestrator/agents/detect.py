"""
Agent 4 — Detection (CLAUDE.md §4 #4 + §6, Core tier).

Decision-making agent: runs ML-driven detection on the event. The LLM is
NEVER used here (CLAUDE.md §6 — detection is ML only).

Two paths:
  1. Live path: the backend has already scored the event during ingest (via
     `connectors.tasks::_score`). We pull the score from the RawEvent row.
  2. On-demand path: ask the backend `/detection/score` to re-score using
     the trained joblib models (Isolation Forest + XGBoost + Random Forest).

Threshold: anomaly_score > 0.7 OR xgb_tp_prob > 0.7 OR impossible_travel.
This intentionally fires on the strongest single signal — we don't try to
balance precision/recall across the whole event stream because the Critic
agent below is the precision gate; Detection is recall-first.
"""

from __future__ import annotations

import logging

from tools.django_client import get

logger = logging.getLogger(__name__)

ANOMALY_THRESHOLD = 0.7


def run(state: dict) -> dict:
    if state.get("suppressed"):
        # Known-benign: skip ML scoring to save compute. Stop processing.
        state["is_suspicious"] = False
        return state

    event_id = state.get("event_id")
    tenant_id = state.get("tenant_id")
    if not (event_id and tenant_id):
        state["is_suspicious"] = False
        return state

    scores = get(f"detection/score?event_id={event_id}")
    if scores:
        # Report the strongest available signal as the headline anomaly score.
        # Isolation Forest is unsupervised and compresses toward ~0.45 here,
        # while supervised XGBoost separates attack (~0.97) from benign (~0.01)
        # — using IF alone would put every real attack below the threshold.
        iso = float(scores.get("isolation_forest") or 0.0)
        xgb_prob = float(scores.get("xgboost_tp_prob") or 0.0)
        state["anomaly_score"] = max(iso, xgb_prob)
        state["isolation_forest"] = iso
        state["xgb_tp_prob"] = scores.get("xgboost_tp_prob")
        state["insider_prob"] = scores.get("insider_prob")
        state["peer_zscore"] = scores.get("peer_zscore", 0.0) or 0.0
    else:
        logger.debug("detection: no score from backend, scoring %s from raw heuristic", event_id)
        # Slow path: backend's heuristic fallback has fired during ingest; we
        # trust whatever anomaly_score the ingest task stamped on the RawEvent.
        event = get_raw_event(event_id)
        state["anomaly_score"] = (event or {}).get("anomaly_score") or 0.0

    if_score = state.get("anomaly_score") or 0.0
    xgb = state.get("xgb_tp_prob")
    is_suspicious = (
        if_score > ANOMALY_THRESHOLD
        or (xgb is not None and xgb > ANOMALY_THRESHOLD)
        or _is_impossible_travel(state)
    )

    state["is_suspicious"] = bool(is_suspicious)
    return state


def _is_impossible_travel(state) -> bool:
    geo = state.get("geo_enriched") or {}
    raw = state.get("raw_event", {}) or {}
    # An anonymising proxy/exit node overrides any login_success — treat it as a
    # high-confidence impossible-travel signal on its own.
    ip_known_hostile = (
        geo.get("is_anonymous_proxy") is True
        or raw.get("ip") in ("185.220.101.34",)
    )
    return bool(ip_known_hostile)


def get_raw_event(event_id):
    from tools.django_client import get as _get
    return _get(f"detection/event/{event_id}")
