# ViltrumX

**The Security Decision OS for India's Startup Economy.**
An ontology-driven, autonomous Security Operations Platform that models a startup's entire
attack surface as a living digital twin, then predicts, investigates, and neutralizes threats
through governed, fully-auditable autonomous actions — built for the Indian startup with real
attack surface and zero analysts, and understood in the founder's own language.

> *Most tools display alerts. ViltrumX makes governed decisions — grounded in your world,
> proven every night, understood in your language.*

Full product spec: [`CLAUDE.md`](./CLAUDE.md) · System design:
[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) · Build roadmap:
[`docs/BUILD-PLAN.md`](./docs/BUILD-PLAN.md).

## Repository layout

| Path | What | Status |
|---|---|---|
| `frontend/` | React + TypeScript app — 13 screens (1 hero + 12 rubric screens) | ✅ UI demo (mock data) |
| `backend/` | Django + DRF — multi-tenant API, connectors, governed actions | 🔜 skeleton |
| `orchestrator/` | LangGraph agent graph — the 8 specialist agents | 🔜 skeleton |
| `.github/workflows/` | CI (frontend + backend), image build & scan, gated deploy | ✅ live |
| `docker-compose.yml` | Postgres 16 · Neo4j 5 (+GDS) · Qdrant · Redis 7 | ✅ live |

## Quick start

**Frontend demo (no Docker needed):**

```bash
cd frontend
npm install
npm run dev        # → http://localhost:5173
```

**Data stores (requires Docker Desktop):**

```bash
cp .env.example .env
docker compose up -d
# Neo4j browser → http://localhost:7474
```

## Environments

| Env | Trigger | Notes |
|---|---|---|
| Local | `docker compose up` | full stack |
| Staging | merge to `develop` | `docker-compose.staging.yml`, seeded demo tenant |
| Production | tag push `v*` | manual approval via GitHub Environment protection |

## Screens (frontend)

Hero/Landing (marketing) + 12 product screens: Auth · Onboarding & Integrations Wizard ·
Command Deck · Ontology Explorer · Investigation Workspace (EN/हिंदी/ગુજરાતી + Founder Mode) ·
Autonomy Console · Provenance/Audit Viewer · Risk & Prediction Dashboard · Attack Surface
Inventory · Purple Team Console · Report & Compliance Center (DPDP/CERT-In/RBI/SOC 2) ·
Settings/RBAC/Billing (INR + GST).
