# P0 — Truth & deployability: COMPLETION RECORD

Date: 2026-11-26. Verified by independent re-run of every gate check (not just the workflow's self-report).

## Verification (all green)
| Check | Command | Result |
|---|---|---|
| Django check (test) | `manage.py check --settings=viltrumx.settings.test` | no issues |
| Django check (prod) | `manage.py check --settings=viltrumx.settings.prod ALLOWED_HOSTS=example.com` | no issues |
| Migrations drift | `makemigrations --check --dry-run` | No changes detected |
| Backend tests | `pytest --ds=viltrumx.settings.test` | 59 passed |
| Migrations apply | `migrate` on fresh sqlite | 27 applied, exit 0 |
| Health endpoint (live) | `curl /healthz` on daphne | `{"status":"ok","db":"ok","redis":"error"}` HTTP 200 (db critical, redis optional) |
| Auth guard (live) | `curl /api/v1/incidents` | HTTP 401 |
| Frontend type-check | `npx tsc -b` | exit 0 |
| Frontend build | `npx vite build` | exit 0 |
| Frontend tests | `npx vitest run` | 10 passed |
| Frontend lint | `npx oxlint` | 0 errors (2 pre-existing fast-refresh warnings) |
| Honesty scan | grep rendered `8/8`/`IndicTrans2`/`Critic-verified` | none in rendered output |

## What changed
- **Email**: SMTP vars documented in `.env.example`; `EMAIL_BACKEND` already env-driven; verification mail path unchanged (console default kept for dev).
- **Prod settings**: `DJANGO_SETTINGS_MODULE` wired in Dockerfile + both compose files; `docker-compose.prod.yml` sets prod for backend/celery/celery-beat; `prod.py` strips empty ALLOWED_HOSTS and falls back to localhost with a warning.
- **Static/TLS**: whitenoise middleware + CompressedManifest storage; `entrypoint.sh` runs collectstatic (+ opt-in migrate) then daphne on `$PORT`; `SECURE_PROXY_SSL_HEADER` + `CSRF_TRUSTED_ORIGINS` in base; nginx `/health` proxies real backend and `/static/`→backend.
- **Health**: `HealthView` + `GET /healthz` (DB critical, Redis optional).
- **Incident bug**: `IncidentCreateView` now writes `occurred_at`/`time_label` (were NOT NULL, caused first-incident 500).
- **Compliance**: `reportlab>=4.2` + `whitenoise>=6.7` declared; Devanagari font restored (valid TTF, 219KB); compliance import guarded.
- **Honesty**: removed `8/8 agents` (now derived), PayKraft literal in Inventory, IndicTrans2/Critic-verified claims, demo-tenant env label; HI/GU narrative no longer returns wrong-company English (404 instead); `streamUrl()` returns null without a tenant and builds absolute ws URL; live feed falls back to 5s polling with `live|polling|offline` mode badge.
- **Containers**: loopback-bound infra ports, `restart: unless-stopped`, celery-beat service, VITE_API_URL build arg.
- **Assets**: `NotoSansDevanagari-Regular.ttf` and `branding/viltrumx-mark.png` restored.

## Deferred (explicitly not P0)
Real connector polling (GitHub audit-log), WS JWT auth middleware (P1), RBAC + invites + default policy (P2), real actuation/rollback (P3), Razorpay billing + startup verification (P4).
