# CLAUDE.md — ViltrumX
### The Security Decision OS for India's Startup Economy

> **One-liner:** An ontology-driven, autonomous Security Operations Platform that models a
> startup's entire attack surface as a living digital twin, then predicts, investigates, and
> neutralizes threats through governed, fully-auditable autonomous actions — built for the
> Indian startup that has real attack surface and zero analysts, and understood in the founder's
> own language.

> **Tagline:** *"Most tools display alerts. ViltrumX makes governed decisions — grounded in your
> world, proven every night, understood in your language."*

---

## 0. Read This First — Project Context & Non-Negotiables

**What this is now:** a BE (AI/ML) major college project, not a hackathon entry. Treat it as a
real product spec — the ambition is to be genuine infrastructure for India's startup ecosystem,
not a weekend demo. That means the code, the docs, and the pitch all need to hold up to someone
who actually knows this market.

**Hard rubric constraints — do not violate these:**

| Constraint | Requirement |
|---|---|
| Frontend | React + TypeScript — mandatory |
| Backend | Django + DRF — mandatory |
| Component count | Minimum 10 substantive product screens **excluding** the marketing hero/landing page → target **13 total screens** (§7) |
| Production readiness | Must show a real CI/CD workflow, containerization, and environment separation (§10) — this is graded, so it needs to exist as working config, not just a slide |

**Before writing any pitch copy, README claim, or slide for this project, read §2.** Earlier
drafts (the original hackathon deck) made two claims that are not accurate as of mid-2026 and
must not be repeated: that continuous purple-teaming is unclaimed territory, and that securing
AI agents/non-human identities is "ahead of the market." Both are wrong now — see §2 for what to
say instead.

---

## 1. Product Vision & Positioning

### 1.1 The core insight
Three things are true about the "autonomous SOC" market in 2026:

1. **"AI agents triage your alerts" is no longer a pitch — it's the price of entry.** 20+ funded
   vendors and every major incumbent (CrowdStrike, Palo Alto, Microsoft, Google) now say this.
2. **The blocker to autonomy is trust, not capability.** No founder lets an AI disable their own
   account on a hunch. Whoever makes autonomy safe, reversible, and auditable wins the buyer —
   but "graduated autonomy" itself is now an expected feature, not a differentiator on its own.
3. **The genuinely unserved market is the Indian startup with real attack surface and zero
   security headcount, paying in rupees, subject to Indian law.** Every AI-SOC vendor above is
   priced for a US/EU enterprise buyer ($36K–$100K+/yr, custom enterprise contracts) and built
   for US/EU compliance (SOC 2, HIPAA). None of them speak to DPDP Act obligations, CERT-In's
   6-hour breach-reporting mandate, or RBI rules — and none of them explain a finding in Hindi.

**ViltrumX's wedge = an ontology-grounded, governed-autonomy SOC, priced and built for the
Indian startup, that proves itself and speaks the founder's language.**

### 1.2 Who it's for
Seed → Series-B Indian startups (20–300 people) with no SOC and no security team, but a real
attack surface: Google Workspace/Microsoft 365, GitHub, AWS/GCP, Razorpay/payment rails, and a
product that increasingly ships its own AI features.

### 1.3 Why not the incumbents
Dropzone, Prophet, 7AI, Simbian, Radiant, Exaforce, CrowdStrike Charlotte, Palo Alto Cortex
AgentiX, and Microsoft's Security Copilot agents all assume you already have a SIEM, a security
budget, and an English-speaking security team reading the output. ViltrumX assumes none of that.
Different buyer, different price point, different compliance surface, different language. Not a
head-to-head feature fight.

### 1.4 USP pillars (updated)
1. **Ontology-grounded governed autonomy** — decisions are actions on a typed graph, not scripts;
   every action has a precondition, blast-radius score, rollback plan, and provenance record.
2. **Business-criticality grounding** — every entity in the ontology carries a founder-assigned
   criticality weight, so the system can reason about *impact* ("this is the payments DB"), not
   just technical severity. This is a real, named gap in the current market — nobody else does it.
3. **India-first compliance** — evidence packs generated natively for DPDP Act 2023, CERT-In's
   6-hour reporting window, and RBI cybersecurity frameworks for BFSI customers, alongside SOC 2.
4. **Multilingual explainability** — every investigation narrative, alert, and report can render
   in Hindi/Gujarati/English via the same IndicTrans2 pipeline already built for CrimeGPT. A
   non-technical founder gets "your customer database was accessed from Russia at 3 AM" in the
   language they actually think in. No competitor above does this in any language but English.
5. **Sovereign / self-hostable inference option** — the explanation layer can run on a
   self-hosted open-weight model (Llama/Mistral via vLLM or Ollama) instead of a foreign cloud
   API, for customers whose DPDP obligations make that matter. Detection never depends on this —
   ML is local and deterministic either way (§6).
6. **Founder Mode** — a plain-language, rupee-denominated impact view alongside the technical
   view, so a non-technical CEO can actually make the "do we freeze this transaction" call
   instead of just reading a technical severity score.
7. **Priced for the buyer that actually needs it** — INR pricing, GST invoicing, UPI/Razorpay
   billing, self-serve onboarding in under 10 minutes — not a six-figure annual contract.

---

## 2. Competitive Reality Check (2026) — keep this section current

| Vendor | What they actually own | Verdict for us |
|---|---|---|
| Dropzone AI, Prophet Security | Mature Tier-1/2 triage & investigation, strong integrations | We don't out-triage them. We're not competing here. |
| 7AI | "Swarming" 60+ agent architecture, $130M Series A (largest cyber Series A ever) | Architecture-heavy enterprise play; wrong buyer for us. |
| Simbian | Already ships continuous offensive validation (AI Pentest Agent) feeding a shared context back to defensive agents | **Our "continuous purple team" is not unclaimed — it's rare, not novel.** Pitch it as "closing a loop almost nobody closes," never as "nobody does this." |
| Astrix, Oasis, Token Security, GitGuardian | Non-human-identity / AI-agent security — Cisco in talks to acquire Astrix for $250–350M, Oasis raised $120M, every major vendor (Cisco, Microsoft, Google, Palo Alto) launched competing NHI products at RSAC 2026 | **"Securing AI agents/NHIs" is the single hottest, most funded niche in security right now — not a gap.** Keep it as a roadmap line only. Never claim to be ahead here. |
| CrowdStrike Charlotte, Palo Alto Cortex AgentiX, Microsoft Security Copilot agents | Full incumbent stacks, deep telemetry, enterprise distribution | We don't compete on breadth of integration. We compete on buyer segment + compliance + language. |
| Bricklayer AI, UnderDefense, Todyl, Radiant (SMB tier) | Starting to serve SMBs, per-device pricing | Closest analogue to our segment — but all still US/EU-market, English-only, no India compliance angle. |

**Claims we are NOT allowed to make in any pitch, slide, or README:**
- ❌ "Nobody does continuous purple-teaming" → ✅ "One of the few platforms that closes the
  detect-and-verify loop, alongside Simbian."
- ❌ "We're ahead of the market on securing AI agents" → ✅ "AI-agent identity governance is on
  our roadmap; today we focus on the identities and infrastructure a startup already has."
- ❌ "Nobody targets startups" → ✅ "Underserved relative to enterprise, with real early movers
  (Bricklayer, UnderDefense) — our edge is India compliance + language, not first-mover claims."

---

## 3. The Ontology Engine (core architecture — the actual moat)

Same three primitives Palantir uses for Foundry/Gotham (they already apply this model to
cybersecurity themselves — we're borrowing their operating model, not inventing the concept, and
the pitch should say so plainly rather than imply novelty).

### 3.1 Objects
- **Identities:** `User`, `ServiceAccount`, `APIKey`, `AIAgent` (tracked as roadmap-tier, §11)
- **Assets:** `Device`, `CloudResource`, `Repo`, `SaaSApp`, `DataAsset`
- **Security objects:** `Alert`, `Incident`, `ThreatActor`, `AttackPath`, `Action`
- **New in this version:** every Object carries a `business_criticality` property (Low/Med/High/
  Crown-Jewel), assigned during onboarding by the founder/admin — this is what grounds Founder
  Mode and blast-radius scoring in actual business impact, not just technical severity.

### 3.2 Links
`authenticates_to` · `has_access_to` · `owns` · `member_of` · `communicates_with` ·
`escalated_to` · `exfiltrated_from` · `impersonates`. Lateral movement, blast radius, and
insider threats are graph queries over these links (Neo4j).

### 3.3 Actions (governed write-back)
Every autonomous response is a typed Action with: preconditions, required-permission,
blast-radius score (now weighted by `business_criticality` of the target object), rollback plan,
and provenance record. Examples: `revoke_session`, `force_mfa`, `disable_identity`, `rotate_key`,
`quarantine_device`, `block_ip`, `open_incident`, `page_human`, `generate_compliance_evidence`.

---

## 4. Agent Roster — 8 Specialists + Orchestrator

| # | Agent | Role | Tier |
|---|---|---|---|
| 1 | **Ontology Sync / Ingestion** | Parses, normalizes, and resolves raw logs into Objects/Links in Neo4j | Core |
| 2 | **Triage / Noise-Gate** | Clusters + dedups alerts, suppresses known-benign | Core |
| 3 | **Threat Prediction** | Behavioral ML risk-forecasting before impact | Core |
| 4 | **Detection** | Brute-force, insider, exfil, priv-esc, impossible-travel | Core |
| 5 | **Investigation (Digital Detective)** | Builds attack chains; calls MITRE mapping as a tool | Core |
| 6 | **Verification / Critic** | Adversarially tries to refute the finding before response fires | Core |
| 7 | **Response Commander** | Executes governed Actions per the autonomy dial, with rollback | Core |
| 8 | **Explainability & Reporting** | Business + compliance reports, decision provenance, **renders in Hindi/Gujarati/English via IndicTrans2**, Founder Mode plain-language view | Core |
| — | **Orchestrator (LangGraph)** | Coordinates every agent, route, memory | Core |

**Closed feedback loop:** any analyst/founder override on a decision becomes a labeled training
signal that retrains the Noise-Gate + Detection models and nudges the autonomy dial for that
tenant. This must actually be wired up, not just claimed on a slide.

---

## 5. Governed Autonomy Ladder (per-action-type, per-tenant)

| Tier | Automated behavior | Example | Reversibility |
|---|---|---|---|
| L1 — always auto | Enrichment, correlation, evidence-gathering, report drafting | Build timeline, geolocate IP | Read-only |
| L2 — auto + notify | Low-blast-radius containment | Revoke one session, force MFA | Trivial |
| L3 — auto + auto-rollback | Medium containment with a timer | Block IP for 1h → auto-review | Self-reverts |
| L4 — propose only | High-blast-radius | Disable exec account, quarantine prod | Human approves |

The dial is a policy object in the ontology, editable per-tenant and per-entity-criticality. This
is table-stakes in 2026 (analyst scoring rubrics already grade "Autonomous Investigation Depth"
by L1–L3 coverage) — build it well and transparently, don't pitch it as invented here.

---

## 6. ML Stack (detection is ML; LLMs only explain — never detect)

| Job | Algorithm(s) | Type |
|---|---|---|
| Behavioral anomaly (logins, access) | Isolation Forest, LOF, One-Class SVM | Unsupervised |
| Alert true/false-positive + risk scoring | XGBoost / LightGBM | Supervised |
| Insider-threat / privilege-abuse classification | Random Forest | Supervised |
| Alert clustering & dedup (noise-gate) | HDBSCAN / DBSCAN | Unsupervised |
| Peer-group / cohort anomaly (UEBA) | Peer-group analysis | Statistical |
| Sequence / temporal behavior anomaly | LSTM / GRU, Autoencoders | Deep (next milestone) |
| Attack-path & blast-radius discovery | Neo4j GDS: shortest-path, betweenness/PageRank, community detection | Graph |
| Entity behavior embeddings | node2vec on the ontology graph | Graph ML |
| "Seen this before?" memory recall | sentence-transformer embeddings → Qdrant | Retrieval |
| Explanation / narrative / reports (any language) | LLM grounded on ontology (cloud API or self-hosted per §1.4 pillar 5) | Generative only |

---

## 7. Frontend — 13 Components (React + TypeScript)

Rubric requires 10+ product screens excluding the hero page. This plan gives you the mandatory
10, plus a landing page and two components that make the product feel real and gradeable as
"production ready" rather than a pile of dashboards.

| # | Component | Counts toward rubric? | What it does | Key libs |
|---|---|---|---|---|
| — | **Hero / Landing Page** | No (marketing) | Public-facing pitch, positioning, CTA | Framer Motion |
| 1 | **Login / Signup / Auth** | Yes | Org signup, SSO-ready auth shell | React Hook Form |
| 2 | **Onboarding & Integrations Wizard** | Yes | Connect Google Workspace, GitHub, AWS, Razorpay/Slack in <10 min; cold-start | OAuth flows |
| 3 | **Command Deck (Mission Control)** | Yes | Live agent activity, incident feed, global status | WebSocket, Framer Motion |
| 4 | **Ontology Explorer** | Yes | Interactive entity–relationship graph | React Flow + Cytoscape |
| 5 | **Investigation Workspace** | Yes | Attack chain, forensic timeline, evidence, AI narrative (multilingual toggle) | Recharts, timeline UI |
| 6 | **Autonomy Console** | Yes | Graduated-autonomy dial; per-action-type policy config | Custom form/state |
| 7 | **Provenance / Audit Viewer** | Yes | Replay any autonomous decision; one-click rollback | Diff/replay UI |
| 8 | **Risk & Prediction Dashboard** | Yes | Risk scores, forecasts, Defense Readiness Score, **Founder Mode toggle** | Recharts/D3 |
| 9 | **Attack Surface Inventory** | Yes | Identities, SaaS, cloud, repos + posture | Table + graph |
| 10 | **Purple Team Console** | Yes | Schedule/run simulated attacks; caught/contained pass-fail | Scenario UI |
| 11 | **Report & Compliance Center** | Yes | SOC 2 / DPDP / CERT-In / RBI evidence, export PDF | react-pdf |
| 12 | **Settings / Admin / RBAC & Billing** | Yes | Org roles, tenant defaults, INR billing/subscription | Custom form/state |

**Total: 13 screens (1 hero + 12 counted toward the rubric's "10+").**
Shared: a `components/` design system — dark "terminal" theme, StatTiles, AgentCard, GraphCanvas,
ProvenanceTimeline, AutonomyDial, LanguageToggle.

---

## 8. Backend — Django + DRF

- **Multi-tenant + RBAC + audit log** (django-tenants or row-level scoping)
- **`connectors/` app** — Google Workspace, GitHub, AWS CloudTrail, Slack, Razorpay pollers/webhooks
- **`ontology/` app** — entity resolution → syncs Objects/Links to Neo4j
- **`detection/` service** — serves ML models (FastAPI microservice or Django + joblib)
- **`orchestrator/`** — LangGraph (Python) driving the agent graph
- **`actions/` app** — governed Actions, precondition checks, rollback, provenance write
- **`reports/` app** — LLM-grounded generation, multilingual rendering, compliance templates
- **`billing/` app** — INR pricing, GST invoicing, Razorpay/UPI integration
- **Realtime:** Django Channels (WebSockets) for live agent viz
- **Async:** Celery + Redis for ingestion, ML scoring, purple-team jobs

---

## 9. Data Layer

| Store | Role |
|---|---|
| PostgreSQL | System of record (tenants, users, incidents, actions, audit, billing) |
| Neo4j | The Ontology graph — objects, links, attack paths, GDS analytics |
| Qdrant | Vector memory — incident/precedent recall |
| Redis | Real-time queues + WebSocket pub/sub + Celery broker |

---

## 10. CI/CD & Production-Readiness Reference

This needs to exist as real config in the repo, not just a diagram, since it's graded.

### 10.1 Branching model
`main` (production, tag-released) ← `develop` (staging, auto-deployed) ← `feature/*` (PR into develop)

### 10.2 Environments

| Env | Trigger | Notes |
|---|---|---|
| Local | `docker-compose up` | Full stack incl. Postgres/Neo4j/Qdrant/Redis |
| Staging | merge to `develop` | Auto-deployed, seeded with synthetic demo tenant |
| Production | tag push `v*` | Requires manual approval via GitHub Environment protection rule |

### 10.3 Reference workflows (`.github/workflows/`)

**`backend-ci.yml`**
```yaml
name: Backend CI
on:
  pull_request:
    paths: ["backend/**"]
  push:
    branches: [develop, main]
    paths: ["backend/**"]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_DB: viltrumx_test, POSTGRES_PASSWORD: postgres }
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 10s --health-timeout 5s --health-retries 5
      redis:
        image: redis:7
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r backend/requirements.txt
      - run: ruff check backend/
      - run: bandit -r backend/ -ll
      - run: python backend/manage.py migrate --check
      - run: pytest backend/ --cov=backend --cov-report=xml
```

**`frontend-ci.yml`**
```yaml
name: Frontend CI
on:
  pull_request:
    paths: ["frontend/**"]
  push:
    branches: [develop, main]
    paths: ["frontend/**"]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20", cache: "npm" }
      - run: npm ci
      - run: npm run lint
      - run: npm run type-check
      - run: npm run test -- --coverage
      - run: npm run build
```

**`build-and-push.yml`**
```yaml
name: Build & Push Images
on:
  push:
    branches: [main]
    tags: ["v*"]
jobs:
  docker:
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write }
    strategy:
      matrix: { service: [frontend, backend, orchestrator] }
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with: { registry: ghcr.io, username: "${{ github.actor }}", password: "${{ secrets.GITHUB_TOKEN }}" }
      - uses: docker/build-push-action@v6
        with:
          context: "./${{ matrix.service }}"
          push: true
          tags: "ghcr.io/${{ github.repository }}/${{ matrix.service }}:${{ github.sha }}"
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - uses: aquasecurity/trivy-action@master
        with:
          image-ref: "ghcr.io/${{ github.repository }}/${{ matrix.service }}:${{ github.sha }}"
          severity: CRITICAL,HIGH
```

**`deploy.yml`**
```yaml
name: Deploy
on:
  workflow_run:
    workflows: ["Build & Push Images"]
    types: [completed]
jobs:
  deploy-staging:
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - run: echo "pull latest images, docker compose -f docker-compose.staging.yml up -d"
  deploy-prod:
    needs: deploy-staging
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    environment: production   # manual approval gate configured in repo settings
    steps:
      - run: echo "trigger production rollout"
```

### 10.4 Other production hygiene to include
- Pre-commit hooks: `black`, `isort`, `ruff` (Python); `eslint`, `prettier` (TS)
- Secrets via GitHub Secrets locally / a real secrets manager (Vault, AWS Secrets Manager) at
  scale — never committed `.env`
- Container image scanning on every build (Trivy, above)
- IaC roadmap note: Docker Compose is enough for this project; Kubernetes manifests are a
  SCALE-phase item, not required for grading

---

## 11. Build Scope Tiering — Core vs Stretch vs Vision

Don't build all 13 screens and 8 agents to the same depth. Spend real engineering time here:

**Core (must work live, end-to-end):** Ontology Explorer, 3–4 agents (Ingestion, Detection,
Investigation, Response Commander), Autonomy Console, Provenance/Audit Viewer, Command Deck.
This is the actual differentiated spine — it's what makes "governed decisions, not alerts" true
in front of an examiner.

**Stretch (working but can be narrower in scope):** Purple Team Console (a scripted "we ran this
last night, here's the score" is fine), Risk & Prediction Dashboard + Founder Mode, Report &
Compliance Center with at least one real DPDP/CERT-In template, multilingual toggle on at least
the Investigation Workspace.

**Vision only (describe, don't build):** Full AI-agent/NHI identity governance (§2 — this is the
most contested niche in security right now, don't compete there shallow), Kubernetes/multi-region
scale infra, insurance-readiness export.

---

## 12. Roadmap

| Phase | Deliverable |
|---|---|
| **NOW** (this project) | Ontology Engine + Core agents + Command Deck + Autonomy Dial + Provenance + scripted purple-team demo, Docker Compose, working CI |
| **NEXT** | Deep-learning models (LSTM/autoencoder), more India-specific connectors (Zoho, local cloud providers), SSO |
| **SCALE** | Multi-tenant SaaS hardening, AI-agent/NHI governance (once the category matures further), K8s, insurance-readiness scoring |

---

## 13. Honest Risks & Open Questions

- **Autonomy liability** — who's responsible when an Action is wrong? Answer: graduated dial +
  rollback + provenance, stated plainly, not hand-waved.
- **Cold-start data** — synthetic baselines + purple-team seeding; validate this is actually
  convincing in a demo, not just claimed.
- **LLM cost/latency** — mitigated by ML-for-detection; LLM only on the explanation path.
- **Connector breadth for India specifically** — Okta/AWS-first connector lists (copied from the
  Western competitor playbook) don't match what Indian startups actually run. Prioritize Google
  Workspace, GitHub, AWS/GCP, and Razorpay over Okta — most Indian seed-stage startups don't use
  Okta.
- **Neo4j at scale** — fine for startup-sized ontologies; revisit at enterprise scale.
- **Don't overclaim novelty** — see §2's "claims we are NOT allowed to make" list. A judge/examiner
  who knows this space will discount everything else in the pitch if one claim is checkably false.

---

## 14. Demo / Viva Narrative

1. Onboard a fake Indian startup in under 60 seconds via the Integrations Wizard (Google
   Workspace + GitHub + AWS connected).
2. Ontology Explorer lights up — the startup's world as a live graph, crown-jewel assets tagged.
3. Trigger an attack (impossible-travel login → GitHub token abuse → S3 exfil attempt).
4. Watch agents hand off live on the Command Deck.
5. Autonomy Console shows an auto-revoked session (L2) but a *proposed* account disable (L4).
6. Provenance Viewer — replay the decision, hit Undo.
7. Switch Founder Mode + Hindi toggle — same investigation, plain-language, rupee-denominated
   impact, in Hindi.
8. Purple Team Console — "we ran this exact attack against ourselves last night and caught it.
   Defense Readiness: 94%."
9. Report & Compliance Center — one-click DPDP/CERT-In evidence export.
10. Close on the tagline.

---

## 15. USP Backlog — ideas beyond current scope, for later iterations

- Cyber-insurance-linkable readiness score (export Defense Readiness Score to underwriters)
- Regional cloud provider connectors (E2E Networks, CtrlS) alongside AWS/GCP for data-residency-
  sensitive customers
- WhatsApp-based alerting for founders who live in WhatsApp, not Slack
- A "second opinion" mode: cross-check high-stakes L4 proposals with a second, independently
  reasoning agent before surfacing to the human (mirrors the "Double-Check" pattern some
  competitors already do by pairing two separate vendors — we could do it natively)
