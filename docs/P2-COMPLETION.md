# P2 — Trust boundary + per-tenant flexibility: COMPLETION RECORD

Date: 2026-11-26. Implemented directly, then independently adversarially verified (5 skeptic agents refuted 3 claims → all 3 fixed → re-verified).

## What shipped

### RBAC (role enforcement on every write)
- `core/tenancy.py`: role hierarchy (Viewer<Analyst<Admin<Owner) + `require_role()`.
- `TenantAPIView.require_role()` helper; applied to every mutating view:
  - **Analyst+**: propose action, approve/reject action, rollback, run purple, export compliance, ingest replay, create incident, remember/forecast, feed write.
  - **Admin+**: connect/disconnect connector (incl. GitHub OAuth disconnect), store credentials, edit policy, invite members, tag criticality.
- The orchestrator service user is an Analyst, so the agent pipeline still works but cannot self-approve L4 or edit policy.

### Cross-tenant isolation
- Every `RawEvent` query in `core/views_agent.py` scoped by `tenant=self.tenant` (detail-by-pk, score, noisegate, peer-score, forecast, burst-check).
- `reports/recall.py` filters Qdrant results by `tenant_id`; `RecallView` passes it.
- `FeedEntryView` rejects a tenant-id mismatch instead of writing cross-tenant.

### Default autonomy policy on signup
- `RegisterSerializer.create` seeds `AutonomyPolicy` v1 (6 action types from `DEFAULT_POLICIES`) inside the signup transaction — `resolve_level()` has real rows from day one; the Autonomy Console is not blank.

### Per-tenant flexibility (the "different clients, different services" requirement)
- `Tenant.enabled_modules` + `enabled_connectors` (JSONField); empty = all defaults.
- `Tenant.has_module()` / `connector_enabled()`.
- `GET /tenant/entitlements` returns the tenant's module set + entitled/connected connectors.
- `ConnectorListView` **filters** to entitled connectors (inert before adversarial verify caught it).
- `ConnectorCredentialsView` rejects a non-entitled connector (403).
- Frontend `AppLayout` nav hides modules the tenant isn't entitled to (fail-open on API hiccup; API still enforces).

### Member invites
- `POST /members/invite` (Admin+): attaches an existing user or creates an inactive account + emails an invite; cannot grant a role above the caller's.

## Adversarial verification (multi-agent)
5 skeptic agents tried to refute the P2 claims. Results:
- HOLDS: default-policy-on-signup.
- REFUTED → **fixed**: (1) `POST /actions` had no role check (Viewer could auto-execute L2/L3) → now Analyst; (2) connector entitlements were echoed but not enforced → `ConnectorListView` filters + credentials 403; (3) "migration committed" — a git-status artifact, not a bug (file exists, applies, drift-free).
- Tenant-isolation: independently re-audited — all RawEvent queries scoped, recall filtered.

## Verification (all green)
| Check | Result |
|---|---|
| full pytest (fresh DB) | 73 passed (59 base + 14 P2 trust tests) |
| `manage.py check` | no issues |
| migration drift | none |
| ruff (core, connectors) | all checks passed |
| frontend `tsc -b` | clean |
| frontend vitest | 10 passed |
| frontend oxlint | pre-existing warnings only |

P2 trust tests (`core/tests/test_p2_trust.py`) lock in: viewer-can't-approve/edit-policy/connect/propose, analyst-can-reject/propose, admin-can't-grant-owner, cross-tenant pk 404, peer-score isolation, default-policy-on-signup, entitlement default + restriction, connector-list filtering, unentitled-credentials 403.

## Still not done (P3–P4)
- **P3 actuation**: actions still write DB rows only; rollback is a status flip.
- **P4**: Razorpay billing + startup/domain verification.
- (Tenant module sets are data-driven but no admin UI yet to edit them — can be set via DB/django-admin; a settings screen is a later UI task.)
