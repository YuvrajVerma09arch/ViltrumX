# ViltrumX Backend — Django + DRF (skeleton)

> **Status: structure only.** Implementation starts after frontend demo sign-off
> (owner: Yuvraj). See root `CLAUDE.md` §8 for the full spec.

## Intended layout

```
backend/
├── viltrumx/          # Django project (settings split: base/dev/staging/prod)
├── connectors/        # Google Workspace, GitHub, AWS CloudTrail, Slack, Razorpay pollers/webhooks
├── ontology/          # entity resolution → syncs Objects/Links to Neo4j
├── detection/         # serves ML models (joblib) — Isolation Forest, XGBoost, HDBSCAN
├── actions/           # governed Actions: preconditions, blast radius, rollback, provenance
├── reports/           # LLM-grounded generation, IndicTrans2 multilingual rendering, compliance templates
├── billing/           # INR pricing, GST invoicing, Razorpay/UPI
└── manage.py
```

Cross-cutting: multi-tenant scoping + RBAC + append-only audit log; Django
Channels for realtime; Celery + Redis for async ingestion/scoring jobs.

## Bootstrap (when ready)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
django-admin startproject viltrumx .
```

Backend CI (`.github/workflows/backend-ci.yml`) activates automatically once
`backend/manage.py` exists.
