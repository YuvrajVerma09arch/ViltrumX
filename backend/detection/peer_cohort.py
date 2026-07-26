"""
Peer-cohort / UEBA anomaly (CLAUDE.md §6 row 5).

For each principal we maintain a baseline of their own behavioural rate
(events/day), and a per-principal-type cohort baseline. A z-score above the
cohort threshold marks the principal's behaviour as anomalous *relative to
their peers*, not just to themselves.

The caller (scorer / training) supplies a prebuilt context because the
peer-cohort mean/std need a baselines window read up-front. For the demo, a
peer group is implicitly the tenant's STAFF list — there are ~4 principals —
so the cohort is naturally small and the z-score is meaningful.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta


def compute_peer_context(events_qs, window_days: int = 7) -> dict:
    """
    Build per-principal peer-cohort z-scores over the last `window_days`.

    Returns:
        {
          "per_principal_count": {principal: event_count},
          "cohort_mean": float, "cohort_std": float,
          "peer_z_map": {principal: z_score},
          "baseline_rate": {principal: events_per_day},
        }
    """
    per_principal: dict[str, int] = defaultdict(int)
    per_principal_login: dict[str, int] = defaultdict(int)
    if not events_qs:
        return _empty_context()

    events = list(events_qs)
    latest = max(e.occurred_at for e in events)
    cutoff = latest - timedelta(days=window_days)

    for ev in events:
        if not ev.principal or ev.occurred_at is None or ev.occurred_at < cutoff:
            continue
        per_principal[ev.principal] += 1
        if "login" in str(ev.event_type):
            per_principal_login[ev.principal] += 1

    counts = list(per_principal.values())
    mean = sum(counts) / len(counts) if counts else 0.0
    var = sum((c - mean) ** 2 for c in counts) / len(counts) if counts else 1.0
    std = var ** 0.5 or 1.0
    peer_z_map = {p: (c - mean) / std for p, c in per_principal.items()}
    baseline_rate = {p: c / max(1, window_days) for p, c in per_principal.items()}

    return {
        "per_principal_count": dict(per_principal),
        "per_principal_login": dict(per_principal_login),
        "cohort_mean": mean,
        "cohort_std": std,
        "peer_z_map": peer_z_map,
        "baseline_rate": baseline_rate,
        "window_days": window_days,
    }


def _empty_context():
    return {
        "per_principal_count": {}, "per_principal_login": {},
        "cohort_mean": 0.0, "cohort_std": 1.0,
        "peer_z_map": {}, "baseline_rate": {}, "window_days": 7,
    }


def flag_outliers(peer_ctx: dict, z_threshold: float = 2.0) -> list:
    """Return principals whose peer-cohort z-score exceeds the threshold."""
    z_map = peer_ctx.get("peer_z_map", {}) or {}
    return [
        {"principal": p, "z": round(z, 2), "count": peer_ctx["per_principal_count"].get(p, 0)}
        for p, z in z_map.items()
        if z >= z_threshold
    ]
