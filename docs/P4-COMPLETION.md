# P4 — Billing + startup verification: COMPLETION RECORD

Date: 2026-11-26. Implemented directly; adversarially verified.

## A. Razorpay billing (`backend/billing/`)
- `models.py` — `Order` (one-off/annual), `Subscription` (monthly), `GstInvoice`, `WebhookEvent` (idempotency). **All money is integer paise.**
- `razorpay_client.py` — client singleton from env; `PLANS` catalogue (Seed ₹9,999 / Growth ₹14,999 / Scale ₹74,999 — entry tiers kept under the ₹15,000 RBI e-mandate no-AFA threshold); `verify_payment_signature` + `verify_webhook_signature` (raw body).
- `gst.py` — GST-inclusive → taxable split, paise-exact; SAC 998314; CGST+SGST intra-state vs IGST inter-state by place of supply.
- `views.py`:
  - `POST /billing/orders` (Owner-only) → Razorpay order; returns public key id only, never the secret.
  - `POST /billing/verify` → **idempotent** (select_for_update + status==paid early-return); signature checked before marking paid; generates the GST invoice on success.
  - `POST /webhooks/razorpay` (public, `csrf_exempt`, no auth) → verifies **raw** body HMAC, dedupes on `X-Razorpay-Event-Id`, `payment.captured` fulfils idempotently; `payment.failed` does NOT lock the order.
  - `GET /billing/plans` → catalogue + whether live; `GET /billing/invoices` → real GST invoices (replaces the demo stub).
- `billing/urls.py` included into `api_v1`; webhook at root `/webhooks/razorpay`.

### Going live (business side — the long pole)
1. Pvt Ltd KYC: business PAN + COI/CIN + MOA/AOA + signatory PAN/address + Board Resolution/PoA + UBO >10% + bank ₹1 verify + GST/UDYAM cert.
2. **Live production website** exposing About / Contact / Pricing / Terms / Privacy / **Refund-Cancellation** in INR — Razorpay auto-checks these URLs. (This is the #1 activation stall.)
3. Enable auto-capture; generate `rzp_live_*` keys + a live webhook secret (separate from test).
4. Register `https://<host>/webhooks/razorpay`; subscribe to `payment.captured`, `payment.failed`, `subscription.charged`, `subscription.halted`.
5. Set the env vars in `.env.example` (RAZORPAY_*, GST_SELLER_*).
Notes: prices >₹15,000 need bank AFA per cycle (repriced entry tiers under it); we generate GST invoices ourselves (Razorpay's API is non-GST only); settlements T+2.

## B. Startup verification (`backend/core/verification.py`)
- Layer 1 — **free-email gate** at signup (`RegisterSerializer.validate_email`): gmail/yahoo/etc. rejected; set `REQUIRE_BUSINESS_EMAIL=0` to bypass locally.
- Layer 2 — **DNS TXT ownership**: `POST /verify/domain/start` mints `viltrumx-verify=<hex>`; customer publishes `_viltrumx.<domain>`; `POST /verify/domain/check` resolves and marks verified (dns.resolver; `VERIFICATION_DNS_ENABLED=0` for offline).
- Layer 3 — **GSTIN**: `POST /verify/gstin` validates format + mod-36 checksum locally (free); optional Surepass/Karza vendor lookup via `GSTIN_API_KEY`/`GSTIN_API_URL`.
- **Enforcement**: `ConnectorConnectView` returns 403 for an unverified non-demo tenant — you cannot connect a live source until the company domain is verified. Frontend shows a "Verify your company domain" banner.
- Tenant fields: `domain`, `domain_token`, `domain_verified_at`, `gstin`, `gstin_legal_name`, `gstin_verified_at`, `verification_status`.

## C. Frontend
- `api.ts`: billing (plans/orders/verify/invoices) + verification (status/domain-start/domain-check/gstin) endpoints.
- `Settings.tsx`: plans fetched from `/billing/plans`; **Subscribe** loads Razorpay Checkout.js and verifies on success; invoices are real.
- `AppLayout.tsx`: verification banner when the tenant is unverified.

## Verification (all green)
| Check | Result |
|---|---|
| full pytest (fresh DB) | 99 passed (85 + 14 P4 billing/verification) |
| `manage.py check` | no issues |
| migration drift | none (billing.0001 + core.0004) |
| ruff (billing, core) | all checks passed |
| frontend `tsc -b` | clean |
| frontend vitest | 10 passed |
| old demo InvoiceListView route | removed (billing app serves invoices) |

P4 tests (`billing/tests/test_p4_billing.py`) lock in: GST intra/inter-state paise math, sequential unique invoices, order 503-without-keys + Owner-only, plans catalogue, real invoices, webhook bad-signature 401, webhook captured→paid+GST, free-email rejected vs business-email allowed, GSTIN checksum, domain TXT flow, DNS-off verification.
