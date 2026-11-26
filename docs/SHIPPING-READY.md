# ViltrumX — Shipping Readiness (P0 → P4 complete)

Date: 2026-11-26. Status: **core product is shipping-ready for a first paying pilot.**
Every phase was implemented, then adversarially verified; real holes found were fixed and locked with regression tests.

## Readiness journey
| Phase | What it fixed | Tests added | Status |
|---|---|---|---|
| P0 | Deployable + loginable + honest: prod settings, TLS-ready static (whitenoise), /healthz, SMTP email, incident-create bug, reportlab+font, removed false UI claims | (base) | ✅ |
| P1 | Real multi-connector ingestion (GitHub audit-log, Workspace, AWS, Slack, Razorpay) + automation spine (ingest→Redis→orchestrator→beat) + JWT WebSocket auth + de-hardcoded demo heuristics | base | ✅ |
| P2 | Trust boundary: RBAC on every write, cross-tenant scoping, default policy on signup, per-tenant module/connector entitlements (flexibility), member invites | +14 | ✅ |
| P3 | Real actuation: actions really change external state (GitHub/AWS/Workspace) with receipts + true rollback; never faked as executed; honest manual/simulated | +11 | ✅ |
| P4 | Razorpay billing (orders/subscriptions/GST invoices), secure idempotent webhook, startup domain+GSTIN verification gating live ingest | +25 | ✅ |

## Final verification (whole repo)
| Check | Result |
|---|---|
| Backend pytest | **110 passed** |
| Django check (test + prod) | no issues |
| Migration drift (fresh DB) | none |
| ruff (entire backend) | all checks passed |
| Frontend `tsc -b` | clean |
| Frontend vitest | 10 passed |
| Frontend `vite build` | builds |

## What a real customer can now do
1. **Sign up** with a company email (gmail blocked), receive an emailed OTP, activate.
2. **Verify their company** via DNS TXT (and optionally GSTIN) — enforced before they can connect live data.
3. **Connect GitHub** (real OAuth + audit-log polling) and configure Workspace / AWS / Razorpay credentials; events flow automatically into the agent graph (no manual replay) → incidents + proposed actions, with a JWT-authenticated live Command Deck.
4. **Govern autonomy**: per-action L1–L4 dial; automated containment really fires (GitHub/AWS/Workspace) when credentials are present, is honest `manual` otherwise, and truly rolls back.
5. **RBAC**: Owner/Admin/Analyst/Viewer enforced on every write; invites; per-tenant module surface.
6. **Pay** with Razorpay (orders + verify + webhook + auto GST invoices), Owner-only.

## Honest remaining gaps (post-first-customer)
- Connectors beyond GitHub are real but need provider setup (service-account / role / keys) to ingest; until then they honestly report not-configured.
- Detection models are trained on synthetic data — retune on real telemetry per tenant (ML data path exists; labels need real traffic).
- Workspace/AWS actuation needs the respective credentials; otherwise `manual`.
- Razorpay LIVE requires business KYC + a live website with policy pages (business step, not code).
- No admin UI yet to toggle per-tenant modules (data-driven via DB/django-admin; a settings screen is UI polish).
- No password-reset / token-revocation flow yet (nice-to-have; OTP login is the primary path).

## Go-live checklist (ops)
1. `.env` from `.env.example` — set DJANGO_SETTINGS_MODULE=viltrumx.settings.prod, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, SMTP, RAZORPAY_*, GST_SELLER_*, GITHUB_*.
2. Deploy per `docs/SHIPPING-READINESS.md` §6 (single GCE VM in asia-south1 behind TLS).
3. `run migration`, `collectstatic` (entrypoint does both), confirm `/healthz` db=ok.
4. Register GitHub webhook + Razorpay webhook URLs.
5. Complete Razorpay KYC for live keys.
