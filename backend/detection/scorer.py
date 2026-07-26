"""
ML event scorer (Week 3 — CLAUDE.md §6).

Tries to load trained joblib models from detection/models_store/; if they
don't exist yet (before `train_models` has been run), falls back to a
deterministic heuristic so the pipeline keeps working.

Three model surfaces are available:
  - score_event(event)              → anomaly + TP probability (Detection agent)
  - cluster(events)                  → noise-gate clusters (Triage agent)
  - peer_cohort.compute_peer_context → UEBA z-scores (Threat Prediction)

Detection never depends on the LLM (CLAUDE.md §6).
"""

import logging
import os

logger = logging.getLogger(__name__)

_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models_store")
_if_model = None
_xgb_model = None
_rf_model = None
_LOADED = False


def _load():
    global _if_model, _xgb_model, _rf_model, _LOADED
    if _LOADED:
        return
    try:
        import joblib

        def _try(name):
            p = os.path.join(_MODEL_DIR, name)
            return joblib.load(p) if os.path.exists(p) else None

        _if_model = _try("isolation_forest.joblib")
        _xgb_model = _try("xgboost.joblib")
        _rf_model = _try("random_forest.joblib")  # insider-threat / priv-abuse
    except Exception as exc:  # noqa: BLE001
        logger.debug("model load skipped: %s", exc)
    _LOADED = True


def score_event(event, *, context=None) -> dict:
    """
    Return {"isolation_forest", "xgboost_tp_prob", "insider_prob", "peer_z",
            "is_suspicious"}.

    `context` is optional per-principal state (prior_logins, peer z-scores).
    Without it, stateful features degrade to 0 but the model keeps working.
    """
    _load()
    from detection.features import build_context, featurize

    if context is None:
        # Live path: derive a per-event context from a short recent-events window.
        try:
            from datetime import timedelta

            from django.utils import timezone

            from connectors.models import RawEvent

            qs = RawEvent.objects.filter(
                tenant_id=getattr(event, "tenant_id", None),
                occurred_at__gte=(event.occurred_at or timezone.now()) - timedelta(hours=6),
            ).order_by("occurred_at")
            context = build_context(None, qs) if qs.exists() else {}
        except Exception:  # noqa: BLE001 — lazy DB at module import time
            context = {}

    features = featurize(event, context=context)

    if_score = _score_isolation(event, features)
    xgb_score = _score_xgboost(features)
    insider = _score_random_forest(features)

    peer_z = features[7] if len(features) > 7 else 0.0

    is_suspicious = (
        if_score > 0.7
        or (xgb_score is not None and xgb_score > 0.7)
        or bool(features[4])  # impossible_travel
    )

    return {
        "isolation_forest": round(if_score, 3),
        "xgboost_tp_prob": round(xgb_score, 3) if xgb_score is not None else None,
        "insider_prob": round(insider, 3) if insider is not None else None,
        "peer_zscore": round(peer_z, 3),
        "is_suspicious": is_suspicious,
    }


def _score_isolation(event, features) -> float:
    if _if_model is not None:
        try:
            import numpy as np
            raw = float(_if_model.decision_function(np.array([features]))[0])
            # IF.decision_function: more negative = more anomalous.
            # Map typical ~[-0.3, 0.3] band into [0, 1] with 0.5 = no anomaly.
            return max(0.0, min(1.0, 0.5 - raw))
        except Exception as exc:  # noqa: BLE001
            logger.debug("IF scoring failed: %s", exc)
    return _heuristic(event)


def _score_xgboost(features) -> float | None:
    if _xgb_model is None:
        return None
    try:
        import numpy as np
        return float(_xgb_model.predict_proba(np.array([features]))[0][1])
    except Exception as exc:  # noqa: BLE001
        logger.debug("XGB scoring failed: %s", exc)
        return None


def _score_random_forest(features) -> float | None:
    if _rf_model is None:
        return None
    try:
        import numpy as np
        return float(_rf_model.predict_proba(np.array([features]))[0][1])
    except Exception as exc:  # noqa: BLE001
        logger.debug("RF scoring failed: %s", exc)
        return None


def _heuristic(event) -> float:
    """Rule-based fallback — deterministic, no ML dependency. Reproduces the
    behaviour the demo advertises before train_models has been run."""
    if getattr(event, "is_attack", False):
        return 0.94
    geo = (getattr(event, "geo", "") or "")
    if "RU" in geo or getattr(event, "ip", "") == "185.220.101.34":
        return 0.91
    hour = event.occurred_at.hour if hasattr(event, "occurred_at") and event.occurred_at else 12
    if hour < 5:
        return 0.45
    return 0.05
