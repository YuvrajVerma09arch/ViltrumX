# P1 — Real ingestion + automation spine: COMPLETION RECORD

Date: 2026-11-26. Verified by independent re-run (check, migrate, tests, E2E publish).

## The core fix
Before P1, a real event could enter only via a synthetic replay and **never reached the orchestrator** (the worker subscribed to `viltrumx:events`; nothing published to it). P1 closes the loop:

**Real vendor record → normalize → RawEvent (deduped) → scored → published to `viltrumx:events` → orchestrator worker runs the 8-agent graph → incident + proposed actions.**

Proven end-to-end (mocked Redis): a real GitHub `personal_access_token.create` audit record ingested → `RawEvent` stored → **published to `viltrumx:events`** with `tenant_slug` and `home_country`; a replay of the same record dedupes to 0.

## What shipped

### Connectors (5 providers, graceful degradation)
- `backend/connectors/providers/`: `github.py` (audit-log poll + backfill, the only place PAT-creation events exist), `google_workspace.py` (Admin SDK Reports login events), `aws.py` (CloudTrail lookup_events), `slack.py` (alert sink + optional audit logs), `razorpay.py` (payments).
- Each exposes `is_configured() / poll() / backfill()`; missing deps (boto3, google-api) or creds → returns 0, never crashes.
- `ConnectorCredentialsView` (POST `/connectors/<id>/credentials`) stores per-provider secrets into `Connector.credentials` (never echoed back); generic disconnect endpoint.
- Dedupe via `IngestedEvent` unique (tenant, source, external_id).

### Automation spine
- `connectors/tasks.py::_publish_to_orchestrator` publishes to Redis `viltrumx:events` (guarded, never breaks ingest).
- `CELERY_BEAT_SCHEDULE`: poll-all-connectors (5 min), sweep-auto-rollbacks (1 min), nightly-readiness (02:30). Wrapper modules `actions/tasks.py`, `reports/tasks.py`.
- `core/service_auth.py`: per-tenant Membership now created from `X-Tenant` slug (was: first tenant only).
- `orchestrator/tools/django_client.py`: `X-Tenant` via contextvar, applied per request.
- `orchestrator/main.py`: worker threads `tenant_slug` from each message into the graph + contextvar.

### JWT WebSocket auth (Command Deck now ticks for real users)
- `backend/core/ws_auth.py::JWTAuthMiddleware` reads `?token=<jwt>`, validates via SimpleJWT, sets `scope["user"]`.
- `asgi.py` stacks JWT → session auth; `consumers.py` falls back to the user's first membership when the URL omits a tenant id.

### De-hardcoding (real tenants no longer inherit PayKraft)
- `tools/geoip.py`: real MaxMind GeoLite2 path (`GEOIP_DB_PATH`), offline floor only for synthetic ranges, unknown public IP = `known:False` (not "safe").
- `agents/detect.py`, `noisegate.py`, `investigate.py`: removed literal `185.220.101.34`, `customers-db-backups`, `backup-svc`; foreign-geo detection is `country != home_country`.
- `INC-042/INC-043` now only for the `paykraft` demo tenant; real tenants get deterministic `INC-<yyyymmdd>-<hash>`.

### Settings
- Provider/secret keys added to `settings/base.py` (`GITHUB_WEBHOOK_SECRET`, `GOOGLE_*`, `AWS_ROLE_ARN`, `SLACK_BOT_TOKEN`, `RAZORPAY_*`, `ORCHESTRATOR_ENABLED/STREAM/TENANT_SLUG`, `TENANT_HOME_COUNTRY`). The P0 gap (webhook secret never assigned) is closed.
- `requirements.txt`: `boto3`, `google-api-python-client`, `google-auth`, `razorpay`.

## Verification (all green)
| Check | Result |
|---|---|
| `manage.py check` | no issues |
| migration drift | none (0004 applied) |
| fresh migrate | OK |
| pytest | 59 passed |
| import smoke (5 providers + normalize + ws_auth) | IMPORTS OK |
| orchestrator compile (main/tools/agents) | OK |
| orchestrator selftest | 8 agents compiled, ran end-to-end |
| E2E ingest→publish | published to `viltrumx:events`, dedupe 1→0 |
| ruff (connectors/core/actions/reports/orchestrator) | all checks passed |
| hardcoded demo literals in real path | none (only paykraft-gated selftest) |

## What a customer can do now vs still cannot
**Now:** connect GitHub and get real audit-log events; configure Workspace/AWS/Razorpay credentials; events auto-flow to the agent graph and produce incidents+actions without a human replay; Command Deck WS authenticates a JWT user; beat runs pollers.

**Still P2–P4:**
- RBAC enforcement (Viewer can still approve L4), invites, default policy on signup, criticality persistence.
- Real actuation (actions still DB-only; rollback is a status flip).
- Razorpay billing + startup/domain verification.
- Cross-tenant scoping fixes in `views_agent.py`/`recall.py`.
