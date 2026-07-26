"""
Agent 6 — Verification / Critic (CLAUDE.md §4 #6, Core tier).

Adversarially tries to *refute* an Investigation finding. Only survivors
pass to the Response Commander. This is the precision gate that keeps the
graduated autonomy trustworthy (CLAUDE.md §1 — "the blocker to autonomy is
trust, not capability").

Refutation tests (each adds 0.10–0.35 weight against critic_passed):
  R1 — Geo precision:             the 'hostile' IP must resolve to a known
                                   anonymous-proxy or non-office country.
                                   A failed MFA from an office IP is not an
                                   impossible-travel attack.
  R2 — Chain breadth:             ≥2 distinct MITRE tactics in the chain.
                                   A single anomalous GetObject is unworthy
                                   of L2+ containment.
  R3 — Confidence sum:            Σ(confidence of each MITRE-mapped step)
                                   must exceed 1.5 — weak mappings fail.
  R4 — Recall corroboration:      ≥0.7 Qdrant match strengthens; absence
                                   weakens but doesn't veto (novel attacks
                                   are real and must reach Respond).
  R5 — Anomaly floor:             anomaly_score must clear 0.7 OR impossible
                                   travel must be the dominant step. We do
                                   NOT let a noisy UEBA-only flag through.
  R6 — Insider / legit-identity:  PT-02-style insider export must have a
                                   geo in the office range (otherwise we've
                                   confused it with exfil-from-breach). We
                                   don't auto-disable legit employees.

`critic_passed = (refutations_R2..R3..R5..R6 pass) AND R1 passes`.
critic_confidence is a 0–1 score the Response Commander surfaces to humans.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

MIN_CHAIN_STEPS = 2
MIN_MITRE_TACTIC_BREADTH = 1
MIN_MITRE_CONFIDENCE_SUM = 1.5
ANOMALY_FLOOR = 0.7


def run(state: dict) -> dict:
    chain = state.get("attack_chain", []) or []
    if not chain:
        state["critic_passed"] = False
        state["critic_confidence"] = 0.0
        state["critic_refutations"] = ["empty-chain"]
        return state

    geo = state.get("geo_enriched") or {}
    recall_match = state.get("recall_match")
    anomaly = state.get("anomaly_score") or 0.0
    xgb = state.get("xgb_tp_prob")

    refutations = []

    # R1 — Geo precision
    raw = state.get("raw_event", {}) or {}
    if not _passes_geo_precision(state):
        refutations.append("R1:geo-precision-fail")

    # R2 — Chain breadth (≥2 steps)
    if len(chain) < MIN_CHAIN_STEPS:
        refutations.append("R2:chain-too-short")

    # R3 — Sum of MITRE confidences
    conf_sum = sum(float(s.get("confidence", 0.0)) for s in chain)
    if conf_sum < MIN_MITRE_CONFIDENCE_SUM:
        refutations.append("R3:low-mitre-confidence")

    # R5 — Anomaly floor
    impossible_travel = any(s.get("finding_type") == "impossible_travel" for s in chain)
    xgb_confident = xgb is not None and xgb > ANOMALY_FLOOR
    if anomaly < ANOMALY_FLOOR and not impossible_travel and not xgb_confident:
        refutations.append("R5:below-anomaly-floor")

    # R6 — Insider / legit-identity check (PT-02 lives must have office-style geo)
    if any(s.get("finding_type") == "insider_export" for s in chain):
        country = geo.get("country") or raw.get("geo", "")
        if not country or not country.startswith("IN"):
            # Looks like exfil-from-breach misclassified as legitimate-user insider
            refutations.append("R6:insider-geo-conflict")

    # R4 just informs confidence; it doesn't veto (novel attacks are real)
    novelty_bonus = 0.0 if recall_match else -0.05

    state["critic_refutations"] = refutations
    hard_fail = {"R1", "R2", "R5", "R6"} & {r.split(":")[0] for r in refutations}
    state["critic_passed"] = len(hard_fail) == 0

    base_conf = min(0.99, max(0.0, anomaly + novelty_bonus + (0.1 if recall_match else 0)))
    # Penalty scaled to severity of refutations surviving
    if refutations:
        base_conf = max(0.0, base_conf - 0.1 * len(refutations))
    state["critic_confidence"] = round(base_conf, 2)

    if state["critic_passed"]:
        logger.debug(
            "critic: PASS conf=%.2f chain=%s refutations=%s",
            base_conf, len(chain), refutations,
        )
    else:
        logger.info("critic: VETO refutations=%s", refutations)
    return state


def _passes_geo_precision(state) -> bool:
    """If any chain step is impossible_travel or mfa_fatigue, the geo must
    be hostile (anonymous proxy OR non-IN country). Otherwise this gate is
    vacuously true (e.g. an insider_export chain doesn't need Russia geo)."""
    chain = state.get("attack_chain", []) or []
    needs_hostile = any(
        s.get("finding_type") in ("impossible_travel", "mfa_fatigue") for s in chain
    )
    if not needs_hostile:
        return True
    geo = state.get("geo_enriched") or {}
    if geo.get("is_anonymous_proxy"):
        return True
    country = geo.get("country") or (state.get("raw_event", {}).get("geo") or "")
    return bool(country) and not country.startswith("IN")
