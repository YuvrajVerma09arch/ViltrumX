# ViltrumX Backend — Django + DRF

> **Status: shell + stub API live.** The project structure, auth, and every
> v1 endpoint exist and serve the PayKraft demo fixtures. Real logic replaces
> the stubs module by module — worklist in [`docs/BUILD-PLAN.md`](../docs/BUILD-PLAN.md),
> contract in [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) §10.

## Run it

```bash
# data stores first (repo root)
docker compose up -d postgres redis neo4j qdrant

cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # core deps; requirements-ml.txt comes in Week 3
python manage.py migrate
python manage.py seed_demo               # login: arjun.mehta@paykraft.in / viltrumx-demo
python manage.py runserver               # → http://localhost:8000/api/v1/
```

Or the whole stack in containers: `docker compose up -d` (backend included, auto-migrates + seeds).

Try it:

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username":"arjun.mehta@paykraft.in","password":"viltrumx-demo"}' | jq -r .access)
curl -s localhost:8000/api/v1/incidents -H "Authorization: Bearer $TOKEN" | jq .
curl -s "localhost:8000/api/v1/incidents/INC-042/narrative?lang=hi" -H "Authorization: Bearer $TOKEN" | jq .
```

## Quality gates (same as CI)

```bash
ruff check .
bandit -r . -ll -x ./.venv
pytest .          # 11 contract tests — they outlive the stubs, keep them green
```

## Layout

```
backend/
├── viltrumx/           # project: settings split (base/dev/staging/prod/test), urls, celery
├── core/               # tenancy·RBAC·audit·incidents  + demo_data.py (the API contract fixtures)
├── connectors/         # WEEK 2: synthetic replay, GitHub webhook/poller
├── ontology/           # WEEK 2: entity resolution → Neo4j
├── detection/          # WEEK 3: ML model serving (requirements-ml.txt)
├── actions/            # WEEK 1: governed Actions, policy gate, rollback, provenance
│   └── demo_state.py   #   mutable stub state (rollback/policy edits round-trip today)
├── reports/            # WEEK 4: LLM narratives (Groq/Ollama), compliance packs
└── billing/            # fixture-tier for viva (INR/GST/UPI data)
```

**How the stubs work:** views in `core/views.py` serve dicts from
`core/demo_data.py` — a 1:1 transliteration of `frontend/src/data/mock.ts`.
Each view carries a `# WEEK n:` note saying what replaces it. A module is done
when its fixture import is gone and the contract tests still pass.
