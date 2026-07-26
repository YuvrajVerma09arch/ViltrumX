"""
Noise-Gate / Triage Agent (CLAUDE.md §4 Agent 2 + §6 row 4).

Alert clustering + dedup with HDBSCAN. The goal is to take a stream of
suspicious events and collapse near-identical ones into one *Alert* so the
downstream Investigation agent doesn't waste effort on 1,842 copies of the
same S3 GetObject burst.

`cluster(events)` returns a list of (cluster_id, event_id). id=-1 means noise
(singletons that HDBSCAN deliberately won't force into a cluster) — those pass
through as their own clusters of size 1. A "known-benign" cluster is one whose
centroid sits inside the benign region defined by `BENIGN_BUCKET_KEYS`.

The trained model is cached as `models_store/hdbscan.joblib`. Detection scorer
loads it on first use and falls back to an exact-match dedup heuristic when
absent (so the system never throws on a cold start).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models_store")
_CLUSTERER = None
_LOADED = False

# Heuristic known-benign fingerprints: (target, event_type) pairs that don't
# deserve escalation ever — the nightly backup job touches the same bucket
# every night at 02:15 from the on-prem backup service IP.
BENIGN_FINGERPRINTS = {
    ("customers-db-backups", "PutObject"),
    ("paykraft-staging-assets", "PutObject"),
}


def _featurize_for_cluster(event) -> list:
    """A compact 3-feature fingerprint for clustering: target, type, hour."""
    import hashlib
    target = (getattr(event, "target", "") or "")
    etype = (getattr(event, "event_type", "") or "")
    occ = getattr(event, "occurred_at", None)
    hour = occ.hour if occ and hasattr(occ, "hour") else 12
    # stable integer hash of (target, type) — fits HDBSCAN's euclidean space.
    # MD5 here is a fast non-cryptographic bucketing function, never a security
    # primitive; usedforsecurity=False makes that explicit to scanners.
    digest = hashlib.md5(
        f"{target}|{etype}".encode(), usedforsecurity=False
    ).hexdigest()
    h = int(digest[:6], 16) % 1000
    return [h / 1000.0, hour / 23.0, 1.0 if str(etype) == "GetObject" else 0.0]


def _load():
    global _CLUSTERER, _LOADED
    if _LOADED:
        return
    try:
        import joblib
        path = os.path.join(_MODEL_DIR, "hdbscan.joblib")
        if os.path.exists(path):
            _CLUSTERER = joblib.load(path)
    except Exception as exc:  # noqa: BLE001
        logger.debug("noise-gate load skipped: %s", exc)
    _LOADED = True


def cluster(events):
    """
    Cluster an iterable of RawEvent into Alert groups.

    Returns a list of dicts — one per cluster:
        {"cluster_id": int, "events": [RawEvent, ...], "size": int,
         "suppressed": bool}

    `suppressed=True` means every event in this cluster is known-benign; the
    orchestrator treats suppression as a triage-veto and never investigates.
    """
    _load()
    events = list(events)
    if not events:
        return []

    vectors = [_featurize_for_cluster(e) for e in events]

    labels = None
    if _CLUSTERER is not None:
        try:
            import numpy as np
            labels = _CLUSTERER.fit_predict(np.array(vectors))
        except Exception as exc:  # noqa: BLE001
            logger.debug("HDBSCAN predict failed, heuristic dedup: %s", exc)

    if labels is None:
        labels = _heuristic_labels(events, vectors)

    groups: dict[int, list] = {}
    for ev, lab in zip(events, labels, strict=False):
        groups.setdefault(int(lab), []).append(ev)

    out = []
    for cid, members in groups.items():
        suppressed = _is_benign_cluster(members)
        out.append({
            "cluster_id": cid,
            "events": members,
            "size": len(members),
            "suppressed": suppressed,
        })
    return out


def _heuristic_labels(events, vectors):
    """Fallback dedup when HDBSCAN isn't loaded: group on exact (target, type)."""
    seen: dict[tuple, int] = {}
    labels = []
    next_id = 0
    for ev in events:
        key = ((ev.target or ""), (ev.event_type or ""))
        if key not in seen:
            seen[key] = next_id
            next_id += 1
        labels.append(seen[key])
    return labels


def _is_benign_cluster(members) -> bool:
    """A cluster is benign if its dominant (target,type) is a known-benign
    fingerprint AND the principal is the on-prem backup service."""
    if not members:
        return False
    target = members[0].target or ""
    etype = members[0].event_type or ""
    if (target, etype) not in BENIGN_FINGERPRINTS:
        return False
    # Only the backup-svc principal is considered benign here.
    return all("backup-svc" in (m.principal or "") for m in members)


def should_suppress(event) -> bool:
    """Single-event suppression: is this event alone known-benign?"""
    target = (event.target or "")
    etype = (event.event_type or "")
    if (target, etype) in BENIGN_FINGERPRINTS and "backup-svc" in (event.principal or ""):
        return True
    return False
