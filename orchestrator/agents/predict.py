"""
Agent 3 — Threat Prediction (CLAUDE.md §4 #3 + §6 row 2, Core tier but
background-mode). Forecasts short-term risk per principal via the
peer-cohort UEBA z-score: a principal whose event rate today is >2σ above
their own / the cohort's baseline is forecast as elevated-risk.

This agent runs both:
  - inline (during a per-event graph invocation): it stamps a per-event
    peer_zscore from the live RawEvent context
  - scheduled (Celery beat hourly): re-computes RiskSnapshot + EntityRisk
    rows for the dashboard fed via Django's `/risk/trend` + `/risk/entities`

For the inline path it's effectively a fast read of what the Detection
featurizer already computed — kept separate so the responsibility split the
CLAUDE.md spec describes (Detection picks the *event*, Prediction forecasts
the *principal*) is honoured in code.
"""

from __future__ import annotations

import logging

from tools.django_client import get, post

logger = logging.getLogger(__name__)


def run(state: dict) -> dict:
    """Inline: pull the live peer z-score for the principal and stamp it on
    state. If above 2.0, set `risk_forecast_elevated=True` so the Critic
    strengthens confidence slightly."""
    principal = state.get("principal")
    tenant_id = state.get("tenant_id")
    if not (principal and tenant_id):
        return state

    # The Detection agent already populated peer_zscore via the backend
    # score_event call; if for some reason it's missing, ask the backend.
    peer_z = state.get("peer_zscore") or 0.0
    if not peer_z:
        # params= is required: django_client.get(path, **kw) forwards kwargs to
        # httpx, so a positional dict would be a TypeError.
        result = get("detection/peer-score", params={"q": principal}) or {}
        peer_z = float(result.get("peer_z", 0.0) or 0.0)
        state["peer_zscore"] = round(peer_z, 3)

    state["risk_forecast_elevated"] = peer_z >= 2.0
    return state


def forecast_job() -> dict:
    """Scheduled entry point (Celery beat). Recomputes per-principal risk
    forecast and writes RiskSnapshot + EntityRisk rows on the backend.
    Backend's `/risk/forecast` endpoint does the heavy lift; here we just
    trigger it for the orchestrator's current tenant context.
    """
    result = post("risk/forecast", json={"window_days": 7})
    if result is None:
        logger.warning("predict.forecast_job: backend rejected forecast job")
        return {}
    return result
