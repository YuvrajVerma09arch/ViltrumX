"""
Action actuators — real external state changes for governed actions (P3).

Each actuator knows how to apply ONE action type against a concrete provider
and how to revert it using the receipt the apply step returns. This is what
turns "governed autonomy" from a DB ledger into real containment.

Contract (see ``actions/actuators/__init__.py``)::

    apply(tenant, action) -> ActuationResult(mode, receipt, detail)
    revert(tenant, action) -> ActuationResult(mode, receipt, detail)

Modes:
    real      — a provider API call succeeded; receipt carries the inverse op.
    manual    — no safe programmatic path (or missing creds). The action is
                recorded as requiring a human, never faked as executed.
    failed    — a provider call was attempted and errored; last_error is set.

Nothing here raises out to the caller: failures are returned as ``failed`` so
the executor can record them without breaking the request.
"""

from __future__ import annotations

import dataclasses
import logging

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ActuationResult:
    mode: str  # "real" | "manual" | "failed"
    receipt: dict = dataclasses.field(default_factory=dict)
    detail: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.mode in ("real", "manual")


def real(receipt: dict, detail: str = "") -> ActuationResult:
    return ActuationResult("real", receipt=receipt, detail=detail)


def manual(detail: str) -> ActuationResult:
    return ActuationResult("manual", detail=detail)


def failed(error: str) -> ActuationResult:
    return ActuationResult("failed", error=error)
