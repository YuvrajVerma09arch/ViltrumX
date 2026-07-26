"""
LangGraph orchestrator — 8 specialist agents wired into a state machine
(CLAUDE.md §4).

State contract: see `state.py` (typed dict).
Node functions: see `agents/{sync,noisegate,predict,detect,investigate,
critic,respond,explain}.py`.

Graph flow (per event):
  START
   → sync          (resolve ontology + geo enrichment)
   → noisegate      (suppress known-benign duplicates)
   → predict       (peer-cohort UEBA z-score inline)
   → detect        (ML: IF + XGB + RF; sets is_suspicious)
   → [if suspicious]
       investigate → critic → [if critic passes] respond → explain
   → END

Closed feedback loop (CLAUDE.md §4): every human override emits a
training_signal=1 audit event; the Celery `retrain_from_feedback` task
surveys these and runs `train_models`. That wiring lives in the backend's
`connectors/tasks.py` (not here) so the orchestrator stays HTTP-only.

HTTP-only: agents never import the Django ORM directly. They talk to the
backend over the service token (ARCH §6) through `tools.django_client`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from langgraph.graph import END, StateGraph

from agents import (
    critic,
    detect,
    explain,
    investigate,
    noisegate,
    predict,
    respond,
    sync,
)
from state import fresh_state

logger = logging.getLogger(__name__)


def _wrap(name: str, fn: Callable) -> Callable:
    """Log agent entry/exit + never crash the graph on a single agent
    exception. Returning state unchanged on failure is safer than crashing
    mid-incident — the Critic will fail the finding downstream."""
    def wrapped(state: dict) -> dict:
        try:
            return fn(state)
        except Exception as exc:  # noqa: BLE001
            logger.exception("agent %s raised: %s", name, exc)
            return state
    return wrapped


# ── Conditional edges ────────────────────────────────────────────────────────
def _after_noisegate(state: dict) -> str:
    if state.get("suppressed"):
        return END
    return "predict"


def _after_detect(state: dict) -> str:
    return "investigate" if state.get("is_suspicious") else END


def _after_critic(state: dict) -> str:
    return "respond" if state.get("critic_passed") else END


def _after_respond(state: dict) -> str:
    # Only generate narratives when at least one Action was proposed (LLM
    # cost discipline — CLAUDE.md §13 honest risks).
    return "explain" if state.get("actions_proposed") else END


# ── Graph wiring ──────────────────────────────────────────────────────────────
def build_graph():
    g = StateGraph(dict)

    g.add_node("sync", _wrap("sync", sync.run))
    g.add_node("noisegate", _wrap("noisegate", noisegate.run))
    g.add_node("predict", _wrap("predict", predict.run))
    g.add_node("detect", _wrap("detect", detect.run))
    g.add_node("investigate", _wrap("investigate", investigate.run))
    g.add_node("critic", _wrap("critic", critic.run))
    g.add_node("respond", _wrap("respond", respond.run))
    g.add_node("explain", _wrap("explain", explain.run))

    g.set_entry_point("sync")
    g.add_edge("sync", "noisegate")
    g.add_conditional_edges("noisegate", _after_noisegate,
                            {"predict": "predict", END: END})
    g.add_edge("predict", "detect")
    g.add_conditional_edges("detect", _after_detect,
                            {"investigate": "investigate", END: END})
    g.add_edge("investigate", "critic")
    g.add_conditional_edges("critic", _after_critic,
                            {"respond": "respond", END: END})
    g.add_conditional_edges("respond", _after_respond,
                            {"explain": "explain", END: END})
    g.add_edge("explain", END)
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_event(tenant_id: int, raw_event: dict, event_id: int | None = None) -> dict:
    """Entry point — called by the Celery task `run_orchestrator` and by the
    backend's `/ingest/replay` flow when VILTRUMX_RUN_ORCHESTRATOR=1."""
    state = fresh_state(tenant_id, raw_event or {}, event_id=event_id)
    try:
        return get_graph().invoke(state)
    except Exception as exc:  # noqa: BLE001
        # Last-resort guard: never raise out of run_event so a Celery failure
        # never breaks ingest. The state we started with is still returned.
        logger.exception("orchestrator run_event failed: %s", exc)
        return state


__all__ = ["build_graph", "get_graph", "run_event"]
