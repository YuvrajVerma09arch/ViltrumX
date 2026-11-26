"""
Actuator registry + dispatch (P3).

``actuate(tenant, action)`` and ``revert(tenant, action)`` are the single entry
points the executor calls. They pick the right provider actuator for an action
and return an :class:`ActuationResult`.

Design principle — honesty over theater:
  * If a real provider actuator is available and its credentials are present,
    we call the real API and record the receipt.
  * If the tenant is the seeded DEMO tenant (``paykraft``), we simulate a
    success so the viva storyline runs — but the Action is stamped
    ``execution_mode="simulated"`` so nothing pretends it touched a real system.
  * Otherwise (real tenant, no actuator/creds) we return ``manual`` — the human
    is told explicitly to apply it. We NEVER mark an action ``executed`` when
    nothing external changed.
"""

from __future__ import annotations

import logging

from actions.actuators import aws as _aws
from actions.actuators import github as _github
from actions.actuators import workspace as _workspace
from actions.actuators.base import ActuationResult, manual

logger = logging.getLogger(__name__)

DEMO_TENANT_SLUG = "paykraft"

# action_type -> ordered list of (provider, module) to try.
# The first provider the tenant has connected wins.
_APPLY = {
    "disable_identity": [("workspace", _workspace), ("github", _github)],
    "revoke_session": [("workspace", _workspace), ("github", _github)],
    "block_ip": [("aws", _aws)],
}

# Actions with no safe programmatic actuator today -> always manual.
_INHERENTLY_MANUAL = {
    "force_mfa": "Force MFA through your IdP admin console.",
    "rotate_key": "Rotate the key in the source console, then update the secret store.",
    "quarantine_device": "Quarantine the device through your MDM/EDR.",
    "page_human": "Page the on-call human; no system change needed.",
    "open_incident": "Incident opened in the ledger; no external change.",
}


def _connected_providers(tenant) -> set[str]:
    from connectors.models import Connector

    ids = set(
        Connector.objects.filter(tenant=tenant, status="connected")
        .values_list("connector_id", flat=True)
    )
    # connector_id ("gw") vs provider slug ("workspace") — normalise.
    alias = {"gw": "workspace", "gh": "github", "aws": "aws", "rzp": "razorpay"}
    return {alias.get(i, i) for i in ids}


def _is_demo(tenant) -> bool:
    return getattr(tenant, "slug", "") == DEMO_TENANT_SLUG


def actuate(tenant, action) -> ActuationResult:
    """Apply ``action`` for real if possible; simulate only for the demo tenant."""
    action_type = action.action_type

    if action_type in _INHERENTLY_MANUAL:
        return manual(_INHERENTLY_MANUAL[action_type])

    candidates = _APPLY.get(action_type)
    if not candidates:
        return manual(f"No actuator for '{action_type}'; apply manually.")

    connected = _connected_providers(tenant)
    for provider, module in candidates:
        if provider not in connected:
            continue
        fn = getattr(module, f"apply_{action_type}", None) or getattr(module, action_type, None)
        if fn is None:
            continue
        result = fn(tenant, action)
        if result.mode in ("real", "failed"):
            return result
        # manual from a connected provider that lacks detail → keep trying next
    if _is_demo(tenant):
        return ActuationResult(
            "simulated", detail=f"[demo] {action_type} simulated for the PayKraft storyline"
        )
    return manual(
        f"No connected provider can actuate '{action_type}' for this tenant; apply manually."
    )


def revert(tenant, action) -> ActuationResult:
    """Undo ``action`` using its receipt; manual/simulated degrade honestly."""
    if getattr(action, "execution_mode", "") == "simulated":
        return ActuationResult("simulated", detail="[demo] simulated revert")
    receipt = action.execution_receipt or {}
    provider = receipt.get("provider")
    action_type = action.action_type

    module = {"workspace": _workspace, "github": _github, "aws": _aws}.get(provider)
    if module is None:
        return manual("No receipt/provider to revert from; undo manually.")
    fn = getattr(module, f"revert_{action_type}", None)
    if fn is None:
        return manual(f"No revert implemented for {action_type} on {provider}.")
    return fn(tenant, action)
