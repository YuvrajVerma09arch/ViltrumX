"""
Agent 1 — Ontology Sync / Ingestion (CLAUDE.md §4 #1, Core tier).

Responsibilities:
  - resolve the raw_event's principal to an ontology node (via backend API)
  - enrich the IP → country/region/city/ISP using the local geoip map
  - stamp the entity external_id so the Investigation agent can graph-walk

It does NOT detect anything — pure L1 enrichment per CLAUDE.md §5. Detection
is Agent 4's job. Feed lines are written by the backend's ingest task.

Note on HTTP-only design: this agent calls the Django backend over the service
token (ARCH §6) and never imports Django directly — so the orchestrator
container ships only langgraph + httpx.
"""

from __future__ import annotations

import logging

from tools.django_client import get
from tools.geoip import resolve

logger = logging.getLogger(__name__)


def run(state: dict) -> dict:
    raw = state.get("raw_event", {}) or {}
    principal = (
        raw.get("principal")
        or raw.get("actor_email")
        or (raw.get("userIdentity") or {}).get("userName")
    )
    state["principal"] = principal

    # ── Geo enrichment — L1, always auto, on the orchestrator side ──────────
    ip = (
        raw.get("ip")
        or raw.get("ipAddress")
        or raw.get("sourceIPAddress")
    )
    state["geo_enriched"] = resolve(ip) if ip else None

    # ── Ontology node resolution (graph lives on the backend) ───────────────
    # Backend's `connectors/tasks.py::_upsert_ontology` already created a stub
    # node for this principal when the event was ingested. We GET the graph
    # and locate the principal by label so the Investigation agent has a
    # concrete starting node for the blast-radius walk. Failure is silent:
    # investigate re-resolves from the principal string.
    if principal:
        graph = get("ontology/graph") or {}
        pid = principal.lower()
        for n in (graph.get("nodes") or []):
            label = (n.get("label") or "").lower()
            node_id = (n.get("id") or "").lower()
            if (
                label == pid
                or node_id == pid
                or label == pid.split("@")[0]
                or pid.startswith(label)
            ):
                state["principal_entity"] = n.get("id")
                break

    return state
