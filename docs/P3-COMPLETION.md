# P3 — Real actuation: COMPLETION RECORD

Date: 2026-11-26. Implemented directly; adversarially verified (5 skeptic agents; 3 confirmed HOLDS, 2 independently re-audited by hand).

## The core honesty guarantee
**An Action is NEVER marked `executed` unless external state actually changed.** Every path that sets `status="executed"` lives in `execute_action()`, reachable only after `actuators.actuate()` returns `real` or `simulated`:
- `real` — a provider API call succeeded; `execution_receipt` holds the inverse-op data.
- `simulated` — the demo tenant only (`slug="paykraft"`); nothing external touched, clearly labelled.
- `manual` — no actuator/credentials; a human must apply it (returned before `executed`).
- `failed` — a provider call errored; `last_error` set (returned before `executed`).

`seed_demo` (demo tenant only) stamps executed rows `execution_mode="simulated"` — never claims real.

## What shipped

### Actuator layer (`backend/actions/actuators/`)
- `base.py` — `ActuationResult(mode, receipt, detail, error)` contract.
- `github.py` — `disable_identity` (remove org member + revert via re-invite), `revoke_session` (OAuth grant revoke; revoke-only, revert=manual).
- `aws.py` — `block_ip` (authorize_security_group_ingress + revert revoke).
- `workspace.py` — `disable_identity` (suspend + un-suspend), `revoke_session` (signOut + token revoke).
- `__init__.py` — registry/dispatch: picks the tenant's connected provider; demo→simulated; else real or honest manual. Inherently-manual action types (force_mfa, rotate_key, quarantine_device, page_human, open_incident) are always manual.

### Executor (`backend/actions/executor.py`)
- `execute_action` now calls the actuator and branches on the result (real/simulated → executed+receipt; manual → manual; failed → failed+last_error).
- `rollback_action` calls `actuators.revert()` with the receipt — a **real** provider call, not a status flip. Failed revert leaves the action `executed` (change still live). Manual revert leaves it executed with a human-facing note.
- `apply_due_auto_rollbacks` (L3 timer) now calls `rollback_action` (real revert) and clears the timer when it can't revert (no loop).

### Model (`backend/actions/models.py`)
- Action: `execution_mode`, `execution_receipt` (JSON), `last_error`, `manual` status.
- `connectors.TrackedSession` — a concrete external session `revoke_session` can target.

### Frontend
- `Action` type extended (`manual`/`failed`, `executionMode`); StatusPill handles them; Provenance detail shows an honest badge: APPLIED TO PROVIDER / SIMULATED (DEMO) / MANUAL — APPLY BY HAND.

## Verification (all green)
| Check | Result |
|---|---|
| full pytest (fresh DB) | 84 passed (73 base+P2 + 8 P3 + 3 adversarial) |
| `manage.py check` | no issues |
| migration drift | none |
| ruff (actions, connectors, core) | all checks passed |
| frontend `tsc -b` | clean |
| frontend vitest | 10 passed |
| migrations exist | actions.0002 + connectors.0005 |

P3 tests (`actions/tests/test_p3_actuation.py` + the skeptic's `test_adversarial_p3.py`) lock in: demo→simulated, real-without-creds→manual (not executed), real-with-creds→real+receipt, provider-error→failed, rollback calls provider revert, manual can't be silently rolled back, L3 sweep reverts, force_mfa→manual (even demo), zero-connector tenant→all manual incl. unknown types.

## Adversarial verdicts
HOLDS: no-regressions, l3-auto-rollback, receipt-and-true-rollback. The two honesty claims (never-fake-executed, manual-not-theater) were independently re-audited by hand (the verifier agents stalled) and confirmed: only execute_action sets executed, and only after a real/simulated actuator result.

## Scope limits (honest)
- GitHub `revoke_session` needs a `token:<id>` target (a username can't be session-killed); revert of a revoked OAuth grant is impossible (manual — user re-authenticates).
- AWS `block_ip` needs a configured `security_group_id` on the connector; otherwise manual.
- Workspace actuators need domain-wide-delegation creds; otherwise manual.
- No per-provider write-scope preflight beyond credential presence (relies on the provider API rejecting an under-scoped token → failed, recorded).

## Still not done (P4)
- Razorpay billing (empty `billing/` app) + GST invoices.
- Startup/domain verification.
