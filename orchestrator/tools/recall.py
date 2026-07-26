"""
Incident recall tool — the orchestrator view of Qdrant memory (CLAUDE.md §6 row 8).

The orchestrator is deliberately HTTP-only (ARCH §6) so it doesn't ship
sentence-transformers or the Qdrant client itself. Instead it calls the
backend's recall endpoint, which encodes the query against the MiniLM-L6
model and queries Qdrant. When Qdrant is offline the backend returns a
curated fixture recall, so this tool never throws.

`recall(text)` returns a list of {incident_id, score, payload} dicts ordered
by cosine similarity (descending). The Investigation agent uses these to
decide whether to lift confidence ('INC-041 looked almost identical') or to
flag a novel attack.
"""

from __future__ import annotations

import logging

from tools.django_client import get

logger = logging.getLogger(__name__)


def recall(text: str, *, k: int = 5) -> list:
    """Recall similar past incidents from Qdrant via the backend."""
    if not text:
        return []
    result = get("incidents/recall", params={"q": text, "k": k})
    if not result or "matches" not in result:
        return []
    return result["matches"]


def best_match(text: str, *, score_floor: float = 0.7) -> dict | None:
    """Convenience for the Investigation agent — one strongest recall or None."""
    hits = recall(text, k=5)
    for h in hits:
        if float(h.get("score", 0)) >= score_floor:
            return h
    return None
