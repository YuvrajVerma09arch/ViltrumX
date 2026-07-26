"""
Agent 8 — Explainability & Reporting (CLAUDE.md §4 #8, Stretch tier; the
only LLM-calling agent per §6).

The orchestrator's job here is small but important: when an incident has
been confirmed + actions proposed, ask the backend's narrative endpoint to
generate the EN/HI/GU narrative grounded on the attack chain + provenance.
The backend's `reports/narratives.py` (which calls `reports/llm.py` → Groq
or Ollama) already does the heavy lifting; here we trigger + cache all three
language variants so the frontend toggle is instant.

LLM never scores or decides (§6 — "detection is ML; LLMs only explain").
"""

from __future__ import annotations

import logging

from tools.django_client import get

logger = logging.getLogger(__name__)

LANGS = ("en", "hi", "gu")


def run(state: dict) -> dict:
    incident_id = state.get("incident_id")
    tenant_id = state.get("tenant_id")
    if not (incident_id and tenant_id):
        return state

    # Fire narrative generation for each language. The backend stores
    # each result as IncidentNarrative rows so frontend reads are free.
    narratives = {}
    for lang in LANGS:
        narrative = get(f"incidents/{incident_id}/narrative",
                        params={"lang": lang})
        if narrative:
            narratives[lang] = narrative
    state["narrative"] = narratives

    # If the LLM produced any narrative at all, mark the incident resolved
    # so the dashboard can flip its state. The backend Incident endpoint
    # handles state transitions; we just nudge if all three langs succeeded.
    if len(narratives) == len(LANGS):
        logger.info("explain: generated narratives for %s in en/hi/gu",
                    incident_id)

    return state
