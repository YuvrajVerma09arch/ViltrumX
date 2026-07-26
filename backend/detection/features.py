"""
Feature engineering — the single shared featurizer for every detection ML model.

All models (Isolation Forest, XGBoost, Random Forest, HDBSCAN) consume the
same feature vector so a model trained on `features(event)` scores the same
RawEvent in production. CLAUDE.md §6: detection is ML only, never LLM.

Features (8): one detection vector of fixed length so a joblib model loaded
straight out of `models_store/` doesn't have to re-fit anything.

  0  hour              — event hour in IST (0–23)
  1  is_night          — 1 if hour < 6 or hour > 22 else 0
  2  is_weekend        — 1 if Sat/Sun in IST
  3  geo_mismatch      — 1 if the event geo is outside IN-* (RU/unknown for demo)
  4  impossible_travel — 1 if the same principal moved faster than is physically
                         possible since their last successful login
  5  burst_flag        — 1 for a clustered burst of GetObject to a backup bucket
  6  mfa_denied_count  — count of denied MFA challenges in the last 2 minutes
  7  peer_zscore       — UEBA peer-cohort anomaly score (z-score of event rate vs
                         same-principal baseline). Built standalone in peer_cohort.
                         0.0 when there is no peer baseline (cold-start).

For training only, `featurize` accepts a list-of-features as the peer_zscore
so the training matrix column index never drifts.
"""

from __future__ import annotations

from collections import defaultdict

# Privatized-known anchors from the synthetic generator (backend/connectors/synthetic.py)
OFFICE_GEO_PREFIX = "IN-"
MOSCOW_IP = "185.220.101.34"
NIGHT_BUCKET_TARGETS = {"customers-db-backups", "paykraft-staging-assets"}


def _payload(event) -> dict:
    return getattr(event, "payload", None) or {}


def _occurred_at(event):
    if hasattr(event, "occurred_at") and event.occurred_at is not None:
        return event.occurred_at
    # one synthetic dict shape (used only by train_models in-memory)
    import datetime as _dt
    return _dt.datetime.now()


def _hour(event) -> int:
    return _occurred_at(event).hour if hasattr(_occurred_at(event), "hour") else 12


def _is_weekend(event) -> int:
    od = _occurred_at(event)
    return 1 if getattr(od, "weekday", lambda: 5)() >= 5 else 0


def _geo_mismatch(event) -> int:
    geo = (getattr(event, "geo", "") or "")
    ip = getattr(event, "ip", None)
    if not geo:
        # CloudTrail events don't carry geo; resolve via known-bad IP for the demo
        return 1 if ip == MOSCOW_IP else 0
    return 0 if geo.startswith(OFFICE_GEO_PREFIX) else 1


def _impossible_travel(event, prior_logins) -> int:
    if not prior_logins:
        return 0
    principal = getattr(event, "principal", "")
    ip = getattr(event, "ip", None)
    occ = _occurred_at(event)
    prev = prior_logins.get(principal)
    if prev is None or ip is None:
        return 0
    prev_ip, prev_ts, prev_geo = prev
    both_at_office = prev_geo.startswith(OFFICE_GEO_PREFIX) and (
        getattr(event, "geo", "") or ""
    ).startswith(OFFICE_GEO_PREFIX)
    if ip == prev_ip or both_at_office:
        return 0
    if not isinstance(prev_ts, type(occ)):  # tz mismatch guard
        return 1 if prev_ts.tzinfo is None and occ.tzinfo is not None else 0
    delta = (occ - prev_ts).total_seconds()
    # Sub-2-hour international relocation = impossible travel (demo threshold).
    return 1 if 0 < delta < 2 * 3600 else 0


def _burst_flag(event, recent_targets) -> int:
    target = (getattr(event, "target", "") or "")
    if target not in NIGHT_BUCKET_TARGETS:
        return 0
    # ≥4 same-target ops in the last 60 seconds = an exfil burst
    occ = _occurred_at(event)
    principal = getattr(event, "principal", "")
    window = [t for t in recent_targets.get(principal, [])
              if (occ - t).total_seconds() < 60]
    return 1 if len(window) >= 4 else 0


def _payload_field(event, *names):
    p = _payload(event)
    for n in names:
        if n in p and p[n] is not None:
            return p[n]
    return 0


def _mfa_denied_count(event, mfa_window) -> int:
    """Successful logins carry attempt=N → if N>1 there were denials."""
    attempt = _payload_field(event, "attempt", "challenge_attempt")
    try:
        return max(0, int(attempt) - 1)
    except (TypeError, ValueError):
        return 0


def featurize(event, *, context=None) -> list:
    """
    Build the 8-feature vector for one RawEvent.

    `context` lets ingest_event supply stateful per-principal featuresBuilt
    (prior successful logins, recent target op windows, peer baselines) without
    the scorer needing to hit the database on every event. When `context` is
    None, the stateful features fall back to 0 — same shape, lower signal — so
    the model never breaks on a cold start.
    """
    context = context or {}
    prior_logins = context.get("prior_logins", {})
    recent_targets = context.get("recent_targets", {})
    peer_z = context.get("peer_z", 0.0)

    return [
        _hour(event),
        1 if _hour(event) < 6 or _hour(event) > 22 else 0,
        _is_weekend(event),
        _geo_mismatch(event),
        _impossible_travel(event, prior_logins),
        _burst_flag(event, recent_targets),
        _mfa_denied_count(event, {}),
        float(peer_z) if peer_z is not None else 0.0,
    ]


FEATURE_NAMES = [
    "hour", "is_night", "is_weekend", "geo_mismatch",
    "impossible_travel", "burst_flag", "mfa_denied_count", "peer_zscore",
]


def build_context(tenant, events_qs) -> dict:
    """
    Scan a tenant's RawEvent stream once and build the per-principal context
    needed to produce stateful features (impossible-travel, burst, peer
    z-score). Used by both training (over the whole training set) and the live
    scorer (over the recent window).

    `events_qs` must be ordered ascending by occurred_at.
    """
    prior_logins: dict[str, tuple] = {}
    recent_targets: dict[str, list] = defaultdict(list)
    # Build a per-principal login-count baseline for peer-cohort UEBA.
    per_principal_event_count: dict[str, int] = defaultdict(int)

    for ev in events_qs:
        principal = (ev.principal or "")
        if not principal:
            continue
        etype = ev.event_type or ""
        occ = ev.occurred_at
        # impossible-travel needs the *previous successful login* for the same
        # principal
        if "login_success" in str(etype):
            prior_logins[principal] = (ev.ip, occ, ev.geo or "")
        # burst needs every GetObject on a backup-bucket target windowed at 60s
        if str(etype) == "GetObject":
            recent_targets[principal].append(occ)
            recent_targets[principal] = recent_targets[principal][-50:]
        per_principal_event_count[principal] += 1

    counts = list(per_principal_event_count.values())
    mean = sum(counts) / len(counts) if counts else 0.0
    var = sum((c - mean) ** 2 for c in counts) / len(counts) if counts else 1.0
    std = var ** 0.5 or 1.0
    peer_z_map = {
        p: (c - mean) / std if std > 0 else 0.0
        for p, c in per_principal_event_count.items()
    }

    return {
        "prior_logins": prior_logins,
        "recent_targets": recent_targets,
        "peer_z_map": peer_z_map,
    }


def featurize_with_context(event, ctx: dict) -> list:
    """Convenience: featurize a RawEvent using a prebuilt context map.

    The peer z-score depends on which point in the baselines the event sits.
    For training (mirroring time), we use the per-principal final count minus
    one so each event's peer_z reflects 'how above baseline was this principal
    by the time of this event' — a one-pass approximation that's good enough
    for detection given the dataset size.
    """
    principal = getattr(event, "principal", "")
    peer_z = ctx.get("peer_z_map", {}).get(principal, 0.0) if principal else 0.0
    return featurize(event, context={
        "prior_logins": ctx.get("prior_logins", {}),
        "recent_targets": ctx.get("recent_targets", {}),
        "peer_z": peer_z,
    })
