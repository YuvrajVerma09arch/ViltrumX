# ViltrumX — 4-Week Backend & Agents Build Plan

> Companion to [`ARCHITECTURE.md`](./ARCHITECTURE.md). Assumes: viva in ~4 weeks, **full stack
> must run live**, Yuvraj is comfortable with Django + DRF, LLM = Groq API (local Ollama as
> sovereign stretch).

---

## The answer: Django spine first, agents in Week 3

Agents are the pitch, but they are **consumers, not foundations**. Build order follows the
dependency graph:

1. **Agents need a world to act on.** Investigation walks the ontology (Neo4j), Response fires
   governed `Action`s (Django models + policy gate), everything writes provenance (Postgres).
   Build agents first and you'd be mocking all three — throwaway work.
2. **The frontend is a finished contract.** Every DRF endpoint you ship flips a real screen from
   mock to live (§10 of ARCHITECTURE) — visible, demoable progress every few days, and each screen
   is its own integration test.
3. **The rubric grades Django + DRF + production readiness.** The agents differentiate the pitch;
   the spine earns the marks. Spine slips are unrecoverable; agent scope can flex (see drop order).

## The symmetric model — one plane per week

| Week | Plane | Stores touched | Screens that go live |
|---|---|---|---|
| 1 | **Record plane** — tenancy, incidents, actions, policy | Postgres | Command Deck (feed), Provenance, Autonomy, Settings |
| 2 | **Graph plane** — ontology, ingestion, connectors | Neo4j, Redis | Ontology Explorer, Inventory, Onboarding |
| 3 | **Intelligence plane** — ML detection, LangGraph agents | joblib, Qdrant | Investigation, Risk, Command Deck (live stream) |
| 4 | **Explanation & proof plane** — LLM, i18n, purple team, compliance | Groq/Ollama | Investigation narratives, Purple Team, Reports |

Each week ends with: CI green · seeded demo works · one rehearsal click-through of the new screens.

## Division of labor

- **Claude:** Django project shell + stub APIs returning mock-identical fixtures (Day 0),
  frontend `api.ts` swap layer + per-screen flips, CI upkeep, code review of your modules,
  fixture/seed tooling.
- **Yuvraj:** all real logic — models' behavior, connectors, ML training, LangGraph agents,
  the governed-action executor. (Your rule: you write it, Claude reviews.)

---

## Week 0 — setup (this weekend, ~half a day)

- [ ] Install **Docker Desktop for Mac** → `docker compose up -d` → verify Neo4j browser
      (`localhost:7474`) and `psql` connect.
- [ ] `python3.12 -m venv backend/.venv && pip install -r backend/requirements.txt`
- [ ] **Claude generates the shell:** Django project (settings split base/dev/staging/prod),
      apps (`core connectors ontology detection actions reports billing`), SimpleJWT auth,
      stub viewsets serving fixtures identical to `mock.ts`, pytest smoke tests, backend CI
      services enabled. From this moment the frontend runs against a real server.
- [ ] Push → confirm backend CI activates and is green.

## Week 1 — record plane (Postgres)

**You build (in `core` + `actions`):**
- [ ] Models: `Tenant`, `Membership(role)`, `AuditEvent`, `Incident`, `Alert`,
      `Action(type,target,level,status,blast_radius,rollback_plan)`, `ProvenanceStep`,
      `AutonomyPolicy(versioned)` — with tenant-scoped managers.
- [ ] DRF: replace stub internals for `incidents`, `actions` (+`/trace`, `/rollback`),
      `policies`, `members`, `invoices`. Keep serializer fields matching mock shapes exactly.
- [ ] Policy gate as a pure function: `resolve_level(action_type, target_criticality, policy)` —
      unit-test it hard; it's the heart of the demo.
- [ ] Seed command: `manage.py seed_demo` → PayKraft tenant with the INC-042 dataset.

**Milestone (Jul 17):** login with a real JWT → Command Deck incidents, Provenance replay +
rollback (state actually flips), Autonomy Console edits persist a new policy version.

## Week 2 — graph plane (Neo4j + ingestion)

**You build (in `ontology` + `connectors`):**
- [ ] Neo4j driver layer; upsert Objects/Links with `tenant_id`; the blast-radius Cypher
      (ARCHITECTURE §4) as a tested function.
- [ ] **Synthetic log generator** (`connectors/synthetic.py`): baseline traffic + the INC-042
      attack chain in Workspace/CloudTrail/GitHub JSONL formats. This is the most leveraged
      code in the project — it feeds demo, ML training, and purple team.
- [ ] Celery ingestion pipeline: `POST /ingest/replay` → normalize → entity-resolve → Neo4j +
      Redis event stream.
- [ ] **GitHub real connector:** webhook receiver (HMAC-verified) + audit-log poll for PAT events
      on a throwaway org.
- [ ] Endpoints: `ontology/graph`, `inventory`, `connectors`, criticality PUT.

**Milestone (Jul 24):** wipe Neo4j → replay JSONL → Ontology Explorer renders the graph from
Cypher, crown jewels tagged from onboarding, a real GitHub webhook creates a node live.

## Week 3 — intelligence plane (ML + agents)

**You build (in `detection` + `orchestrator/`):**
- [ ] Train on synthetic data: Isolation Forest (login anomaly), XGBoost (alert scoring),
      HDBSCAN (noise-gate). Notebook → `joblib` → `detection` scoring task on the event stream.
- [ ] LangGraph orchestrator: state machine per ARCHITECTURE §6. Core four agents —
      **Ontology Sync** (wraps the Week-2 pipeline), **Detection** (wraps scoring),
      **Investigation** (graph walk + MITRE map + Qdrant recall), **Response Commander**
      (proposes Actions via internal API). Then **Verification Critic** if on schedule.
- [ ] Governed executor in `actions`: precondition checks → execute (synthetic-world API) →
      provenance write → L3 auto-rollback timer (Celery countdown).
- [ ] Django Channels: tenant stream group; emit `feed_line`/`action_update`/`agent_status`.

**Milestone (Jul 31):** one command replays the attack → agents detect, investigate, verify,
respond **unattended** → Command Deck streams it live → L4 proposal waits for your click.
This is demo step §14.3–5 of CLAUDE.md working for real.

## Week 4 — explanation & proof plane + freeze

**You build (in `reports` + jobs):**
- [ ] LLM adapter (`GroqProvider` default, `OllamaProvider` behind tenant setting) + grounded
      narrative endpoint (`?lang=en|hi|gu&mode=technical|founder`); IndicTrans2 render step
      (reuse CrimeGPT pipeline); Founder-Mode ₹ figures computed in Python, not by the LLM.
- [ ] Purple team: Celery beat nightly job replaying scenarios against the live pipeline;
      detection/containment timers → readiness score endpoint.
- [ ] One compliance artifact done properly: **CERT-In incident report** (the 6 mandated fields
      from provenance, EN + HI, PDF).
- [ ] Risk endpoints (trend/entities) from stored scores.

**Hardening (both of us):** `seed_demo --reset` one-command demo reset · rehearse the §14 viva
script twice end-to-end · **feature freeze Aug 5** · tag `v1.0.0` → build/scan/deploy workflows
green → 3 days of buffer for the unknown-unknowns.

---

## Drop order when (not if) something slips

Cut from the bottom, never the top:

1. Ollama sovereign toggle (keep the adapter + slide)
2. RBI / SOC 2 packs (keep DPDP + CERT-In)
3. Threat-Prediction agent (keep as scheduled scoring job)
4. Gujarati (keep Hindi + English)
5. HDBSCAN noise-gate ML (keep rule-based dedup; keep IF + XGBoost)
6. Verification Critic agent (keep confidence threshold gate)

**Never cut:** governed Action lifecycle, provenance + rollback, ontology graph, the INC-042
end-to-end run, seed reset. That spine *is* the project.

## Working agreements

- Branches: `feature/*` → PR → `develop` (staging) → `main` (tag-released) — per CLAUDE.md §10.
- CI must be green before merge; a red `develop` blocks everyone.
- Every endpoint lands with: serializer matching `mock.ts`, one happy-path test, one
  tenant-isolation test.
- Claude reviews every backend PR (`/code-review`); Yuvraj reviews every frontend flip.
