"""
Mutable in-memory stub state for actions + policies, so the Provenance
rollback button and Autonomy Console edits round-trip through the real API
before the Week-1 models exist.

In-memory = resets on server restart. That's fine for the stub phase; the
Week-1 models replace this module entirely.
"""

import copy

from core import demo_data

_actions = copy.deepcopy(demo_data.ACTIONS)
_policies = copy.deepcopy(demo_data.DEFAULT_POLICIES)

VALID_LEVELS = {"L1", "L2", "L3", "L4"}


def list_actions():
    return _actions


def _find(action_id: str):
    return next((a for a in _actions if a["id"] == action_id), None)


def action_exists(action_id: str) -> bool:
    return _find(action_id) is not None


def rollback_action(action_id: str):
    action = _find(action_id)
    if action is None or action["status"] != "executed":
        return None
    action["status"] = "rolled-back"
    action["rollback"] = "rolled back manually via Provenance Viewer"
    return action


def decide_action(action_id: str, decision: str):
    action = _find(action_id)
    if action is None or action["status"] != "proposed":
        return None
    action["status"] = "executed" if decision == "approve" else "rolled-back"
    return action


def get_policies():
    return _policies


def set_policies(payload):
    if not isinstance(payload, list):
        raise ValueError("expected a list of policy rows")
    for row in payload:
        if not isinstance(row, dict) or "actionType" not in row:
            raise ValueError("each row needs an actionType")
        if row.get("level") not in VALID_LEVELS:
            raise ValueError(f"level must be one of {sorted(VALID_LEVELS)}")
    _policies.clear()
    _policies.extend(copy.deepcopy(payload))
    return _policies
