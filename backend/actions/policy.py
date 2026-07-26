"""
The policy gate — the single most important function in the backend
(docs/BUILD-PLAN.md Week 1 step 2).

Pure Python on purpose: no Django imports, so it is trivially unit-testable
and the orchestrator can reason about it without a database.
"""

LEVELS = ("L1", "L2", "L3", "L4")
_RANK = {level: i for i, level in enumerate(LEVELS)}

# Fail-safe: an action type the dial has never seen must never auto-execute.
DEFAULT_LEVEL = "L4"

CROWN_JEWEL = "crown-jewel"


def max_level(*levels: str) -> str:
    """Return the most restrictive (highest) of the given L1–L4 levels."""
    return max(levels, key=lambda lv: _RANK[lv])


def resolve_level(
    action_type: str,
    target_criticality: str,
    policy_rows,
    crown_jewel_within_2_hops: bool = False,
) -> str:
    """
    Resolve the autonomy level for a proposed action.

    policy_rows: iterable of {"actionType", "level", "crownJewelOverride"}
    (the exact shape the /policies API serves).

    Rules (docs/ARCHITECTURE.md §5):
      1. base level = the dial's row for this action type; unknown type → L4.
      2. if the target is a crown jewel — or one sits within 2 hops of its
         blast set — bump to max(base, crownJewelOverride).
      3. HIGH-criticality targets never resolve below L2: "always auto" is
         reserved for read-only work, not containment on important entities.
    """
    row = next((r for r in policy_rows if r.get("actionType") == action_type), None)
    if row is None:
        return DEFAULT_LEVEL

    level = row.get("level", DEFAULT_LEVEL)
    if level not in _RANK:
        return DEFAULT_LEVEL

    override = row.get("crownJewelOverride", level)
    if override not in _RANK:
        override = level

    criticality = (target_criticality or "").lower().replace("_", "-")
    if criticality == CROWN_JEWEL or crown_jewel_within_2_hops:
        level = max_level(level, override)
    elif criticality == "high":
        level = max_level(level, "L2")

    return level
