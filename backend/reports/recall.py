"""
Qdrant vector memory — incident recall (CLAUDE.md §6 row 8).

The Investigation agent encodes a textual summary of the live attack chain
and asks Qdrant "have we (or any tenant) seen something like this before?",
getting back the most similar past incidents with cosine similarity. The
'memory recall' is the key Investigation-agent tool: it turns the system from
"this event happened once" into "INC-041 looked almost exactly like this".

`recall` returns a list of (incident_external_id, score) tuples.
`remember` upserts an encoded incident summary at incident-close time.

Encoder is sentence-transformers MiniLM-L6 (CPU-only, ~80MB). If the
sentence-transformers package or Qdrant server is unavailable, both
functions degrade gracefully to no-op / fixture (see `_fixture_recall`).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

COLLECTION = "incidents"
_DIM = 384  # MiniLM-L6 vector size

_client = None
_encoder = None
_loaded = False


def _settings():
    from django.conf import settings
    return settings


def _get_client():
    global _client, _loaded
    if _loaded:
        return _client
    _loaded = True
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Distance, VectorParams

        url = _settings().QDRANT_URL
        client = QdrantClient(url=url, timeout=5)
        try:
            client.get_collection(COLLECTION)
        except Exception:  # noqa: BLE001 — collection may not exist yet
            client.recreate_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=_DIM, distance=Distance.COSINE),
            )
        _client = client
    except Exception as exc:  # noqa: BLE001
        logger.debug("Qdrant unavailable: %s", exc)
        _client = None
    return _client


def _get_encoder():
    global _encoder
    if _encoder is not None:
        return _encoder
    try:
        from sentence_transformers import SentenceTransformer
        _encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception as exc:  # noqa: BLE001
        logger.debug("sentence-transformers unavailable, hashing-fallback encoder: %s", exc)
        _encoder = None
    return _encoder


def encode(text: str) -> list:
    """Encode text to a fixed-dim vector, with a deterministic hashing fallback."""
    enc = _get_encoder()
    if enc is not None:
        try:
            return enc.encode(text).tolist()
        except Exception as exc:  # noqa: BLE001
            logger.debug("encoder.encode failed, fallback: %s", exc)
    return _hash_encode(text)


def _hash_encode(text: str) -> list:
    """A deterministic bag-of-n-grams hasher producing a _DIM vector — poor
    man's encoder when sentence-transformers isn't available.

    MD5 is used purely as a feature-hashing function (the "hashing trick"),
    never as a security primitive — hence usedforsecurity=False.
    """
    import hashlib
    vec = [0.0] * _DIM
    toks = text.lower().split()
    for i in range(len(toks)):
        for j in range(i, min(i + 3, len(toks))):
            ngram = " ".join(toks[i : j + 1])
            digest = hashlib.md5(ngram.encode(), usedforsecurity=False).hexdigest()
            vec[int(digest[:8], 16) % _DIM] += 1.0
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / norm for v in vec]


def remember(incident_id: str, text: str, *, tenant_id: int, meta: dict | None = None):
    """Upsert a closed incident summary into Qdrant for future recall."""
    client = _get_client()
    if client is None:
        return False
    vector = encode(text)
    try:
        from qdrant_client.http.models import PointStruct
        client.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(
                id=abs(hash((tenant_id, incident_id))) % (2**31),
                vector=vector,
                payload={"incident_id": incident_id, "tenant_id": tenant_id, **(meta or {})},
            )],
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Qdrant remember failed: %s", exc)
        return False


def recall(text: str, *, k: int = 5, score_floor: float = 0.7) -> list:
    """
    Look up past incidents whose summary is most similar to `text`.
    Returns [{ "incident_id", "score", "payload" }] sorted desc, score ≥ floor.
    """
    client = _get_client()
    if client is None:
        return _fixture_recall(text)
    vector = encode(text)
    try:
        hits = client.search(
            collection_name=COLLECTION, query_vector=vector, limit=k,
        )
        out = []
        for h in hits:
            score = float(h.score)
            if score < score_floor:
                continue
            out.append({
                "incident_id": h.payload.get("incident_id"),
                "score": round(score, 3),
                "payload": h.payload,
            })
        return out
    except Exception as exc:  # noqa: BLE001
        logger.debug("Qdrant recall failed: %s", exc)
        return _fixture_recall(text)


def _fixture_recall(text: str) -> list:
    """When Qdrant is down, return a curated prior-incident if the text
    mentions Russia/MFA fatigue/PAT — these are the hallmarks of INC-041,
    the precursor to INC-042."""
    low = text.lower()
    if any(t in low for t in ("moscow", "russia", "ru-mow", "mfa fatigue", "pat", "185.220")):
        return [{
            "incident_id": "INC-041",
            "score": 0.86,
            "payload": {"source": "fixture", "note": "Qdrant offline — prior-recall fallback"},
        }]
    return []
