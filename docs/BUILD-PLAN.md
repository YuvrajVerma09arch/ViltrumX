# ViltrumX — 4-Week Backend & Agents Build Plan

> Companion to [`ARCHITECTURE.md`](./ARCHITECTURE.md). Written to be followed step by step —
> if a week feels dense, you only ever need the *current* week's checklist. Assumes: viva in
> ~4 weeks, full stack must run live, you're comfortable with Django + DRF, LLM = Groq (local
> Ollama optional). The agents are the one genuinely new bit — there's a plain-language primer
> for them before Week 3, read it early so it's not a cold start.

---

## The one-paragraph version

The frontend is already built and reads from fake data. The backend's whole job over 4 weeks is
to make that fake data real, one screen at a time. We do it in the order things depend on each
other: first the plain database stuff (Week 1), then the graph of your company's assets (Week 2),
then the smart part — ML + agents (Week 3), then the explanations and reports (Week 4). Claude
already built you a running server that serves the fake data through real, logged-in API calls —
so from day one the app works end to end, and each week you're just swapping fake internals for
real ones without the frontend noticing.

## Why Django first, agents last (not the other way round)

It's tempting to build the exciting AI agents first. Don't — here's the concrete reason. An agent
like "Investigation" has to *walk your company's asset graph* (that lives in Neo4j, built Week 2)
and "Response Commander" has to *create a governed action* (that's a Django model + the policy
gate, built Week 1). If you build agents in Week 1, they'd have nothing real to act on — you'd
fake the graph, fake the actions, then throw all that fakery away in Week 3. Building the
foundation first means when you get to agents, they plug into things that already work.

Also: the rubric grades Django + DRF + "it runs in production." That's the foundation. The agents
make the *pitch* shine, but the foundation earns the *marks*. If time gets tight, agent scope can
shrink (there's a drop-list at the bottom); the foundation can't.

## The plan on one line per week

| Week | Nickname | What you're really building | Screens that turn "real" |
|---|---|---|---|
| 1 | **The ledger** | Database tables for incidents, actions, the autonomy dial + login | Command Deck, Provenance, Autonomy, Settings |
| 2 | **The map** | Your company's assets as a graph in Neo4j + the fake-log generator | Ontology Explorer, Inventory, Onboarding |
| 3 | **The brain** | ML models that score events + the agents that act on them | Investigation, Risk, live Command Deck |
| 4 | **The voice** | Plain-language + Hindi explanations, nightly self-tests, compliance PDFs | Narratives, Purple Team, Reports |

Every week ends the same way: **CI green · `seed_demo` works · click through the new screens once.**
If those three are true, you're on track. If not, fix that before starting the next week.

## Who does what

- **Claude:** built the server shell + fake-data APIs (done ✓). Going forward: the frontend
  wiring that flips each screen from fake to live, keeping CI green, reviewing your code, and
  seed/test tooling. Ask Claude to pair on any step below — especially the agent wiring.
- **You:** the real logic — the database models, the connectors, training the ML, and the
  agents. Claude reviews every piece. **This is your rule and it stands** — but "you write it"
  doesn't mean "alone in the dark." Use Claude as the person you rubber-duck and debug with.

---

## Week 0 — setup ✓ DONE

- [x] Docker Desktop installed, `docker compose up -d` brings up Postgres/Neo4j/Qdrant/Redis.
- [x] Groq API key in `.env`.
- [x] Neo4j browser reachable at `localhost:7474`.
- [x] **Claude built the shell:** Django project (settings split), 7 apps, JWT login, every v1
      endpoint serving PayKraft fixtures, 11 passing tests, backend CI wired. Run it with the
      commands in `backend/README.md`.

**You can already do this right now:** `cd backend`, run the server, log in as
`arjun.mehta@paykraft.in / viltrumx-demo`, and hit the API. That's your starting line.

---

## Week 1 — the ledger (Postgres)  ·  target Jul 17

**Goal in plain terms:** right now incidents, actions, and the autonomy dial are Python
dictionaries in a file. Turn them into real database tables you can query and change.

**Step by step, in `core/` and `actions/`:**

1. [ ] **Write the models** (`models.py`). Start simple — one `tenant` ForeignKey on each so
       data is separated per company:
   - `Tenant`, `Membership` (links a user to a tenant with a `role`: Owner/Admin/Analyst/Viewer)
   - `Incident`, `Alert`
   - `Action` (fields: `type`, `target`, `level` L1–L4, `status`, `blast_radius`, `rollback_plan`)
   - `ProvenanceStep` (the numbered trace rows, ForeignKey to Action)
   - `AutonomyPolicy` (the dial — one row per action-type, with a version number)
   - `AuditEvent` (append-only: who did what, when)
2. [ ] **The policy gate** — one pure function, the single most important piece of the whole
       backend: `resolve_level(action_type, target_criticality, policy) -> "L1".."L4"`. It looks
       up the dial, then bumps the level up if the target is a crown jewel. Write it, then write
       5–6 unit tests for it *first* (this is worth doing test-first — it's small and critical).
3. [ ] **Swap the stub views for real ones.** In `core/views.py` each view has a `# WEEK 1:` note
       telling you exactly what to do. Replace the fixture return with a real queryset + a DRF
       serializer. **Keep the JSON field names identical** (`blastRadius`, not `blast_radius`) —
       the built frontend depends on them. The existing tests will tell you if you drift.
4. [ ] **Upgrade `seed_demo`** to create the PayKraft tenant + the INC-042 incident and its
       actions as real rows (right now it only makes the login user).

**How you'll know Week 1 is done (the milestone):** log in from the real frontend → Command Deck
shows incidents from the database → open Provenance, hit rollback, and the action's status
actually flips and persists → change the dial in Autonomy Console and it saves a new policy
version. All four screens now real, no fixtures behind them.

---

## Week 2 — the map (Neo4j + fake logs)  ·  target Jul 24

**Goal in plain terms:** build the graph of PayKraft's world (users, keys, repos, cloud buckets
and how they connect), and build the tool that generates fake security logs to populate it.

**Step by step, in `ontology/` and `connectors/`:**

1. [ ] **Neo4j connection layer** — a small module that opens a driver and runs Cypher. Write two
       functions: `upsert_node(...)` and `upsert_edge(...)`, both stamping `tenant_id`.
2. [ ] **The blast-radius query** — copy the Cypher from ARCHITECTURE §4 into a function and test
       it returns a number. This is what makes "crown jewel nearby → force L4" real.
3. [ ] **The fake-log generator** (`connectors/synthetic.py`) — ⭐ **the highest-value code in the
       project.** It writes out (a) weeks of normal-looking activity and (b) the INC-042 attack
       as a sequence of log lines in real Google-Workspace / AWS-CloudTrail / GitHub formats.
       Why it's so valuable: the *same* file feeds your demo, trains your ML in Week 3, AND runs
       the nightly purple-team test in Week 4. Build it well.
4. [ ] **Ingestion pipeline** (a Celery task): read those logs → figure out which asset each line
       refers to → upsert nodes/edges into Neo4j → drop an event onto Redis. Wire it to
       `POST /ingest/replay`.
5. [ ] **The one real connector — GitHub:** a webhook endpoint (verify the signature) plus a
       poller for personal-access-token events, pointed at a throwaway test org.
6. [ ] Make the `ontology/graph`, `inventory`, and `connectors` endpoints real (read from Neo4j).

**Milestone:** wipe Neo4j, run the replay, and the Ontology Explorer draws PayKraft's real graph
with crown jewels highlighted — and creating a PAT in your test GitHub org makes a node appear.

---

## Week 3 — the brain (ML + agents)  ·  target Jul 31

This is the new-territory week. **Read the primer below before you start** — it removes most of
the mystery. Do the ML first (it's familiar scikit-learn), then the agents.

**Part A — the ML models (`detection/`), ~2 days.** This is ordinary supervised/unsupervised ML,
nothing exotic:
1. [ ] In a Jupyter notebook, load the fake logs from Week 2. Train three small models:
   - **Isolation Forest** → flags weird logins (the impossible-travel one scores high)
   - **XGBoost** → given an alert, predicts "real threat vs noise"
   - **HDBSCAN** → groups near-duplicate alerts so you show 1 instead of 50
2. [ ] Save each with `joblib.dump()`. In `detection/`, write a function `score_event(event)` that
       loads them and returns scores. Wire it to run (via Celery) on each event from the stream.
3. [ ] `pip install -r requirements-ml.txt` for these (kept separate so earlier weeks stay light).

**Part B — the agents (`orchestrator/`), ~3 days.** See the primer. Build them one at a time and
test each alone before connecting them.

### 🧠 Primer: what a "LangGraph agent" actually is

Forget the sci-fi. In this project an **agent is just a Python function** that takes a shared
dictionary (the "state"), does one job, and returns the dictionary with its findings added. That's
it. LangGraph is just the thing that calls these functions in the right order and passes the
dictionary along — like a relay race where the baton is a Python dict.

```python
# This is a complete, real agent. No magic.
def detection_agent(state: dict) -> dict:
    event = state["event"]
    scores = score_event(event)                 # your Week-3A ML function
    state["anomaly_score"] = scores["isolation_forest"]
    state["is_suspicious"] = scores["isolation_forest"] > 0.8
    return state
```

LangGraph's job is only this:

```python
graph.add_node("detect", detection_agent)
graph.add_node("investigate", investigation_agent)
graph.add_edge("detect", "investigate")         # after detect, run investigate
# "if not suspicious, stop early" is a conditional edge — that's the whole framework
```

So an "8-agent system" is 8 functions and a diagram of who-runs-after-whom. The two things that
make *some* agents feel AI-ish:
- **The Investigation agent uses tools** — meaning it calls your own functions (query the Neo4j
  graph, look up a MITRE technique, search Qdrant for similar past incidents) and assembles the
  answer. Still just functions calling functions.
- **The Explainability agent (Week 4) calls the LLM** — the *only* place a language model is
  involved. Every other agent is plain Python + your ML. Detection never touches the LLM.

That's the whole idea. If you can write a Python function that reads a dict and returns a dict, you
can write every agent here.

### The 4 core agents to build (in this order)

1. [ ] **Ontology Sync** — wraps the Week-2 ingestion. Input: raw log. Output: graph updated.
       (You basically already wrote this in Week 2; here you just wrap it as a node.)
2. [ ] **Detection** — wraps your Week-3A `score_event`. The example above *is* this agent.
3. [ ] **Investigation** — the "detective." Given a suspicious event, it walks the Neo4j graph
       outward to build the attack chain, tags each step with its MITRE technique, and asks Qdrant
       "have we seen this before?" Output: the 5-step chain the Investigation screen shows.
4. [ ] **Response Commander** — decides what to *do*. For each step, it proposes an `Action`, then
       calls your Week-1 policy gate to get the level. L1–L3 it executes; L4 it just proposes and
       stops for a human. It talks to Django through the API (so every action still goes through
       your governed lifecycle — the agent gets no special backdoor).

   *(Stretch, same week if going well: **Verification Critic** — a 5th node between Investigation
   and Response that tries to argue the finding is a false alarm; only if it fails does Response
   run. It's a nice "we double-check ourselves" beat in the demo.)*

**Part C — make it live (~1 day):**
- [ ] **Governed executor** in `actions/`: the code Response Commander calls — check preconditions
      → do the action against the fake world → write the provenance trace → for L3, set a Celery
      timer to auto-undo in an hour.
- [ ] **Live updates:** Django Channels pushes each agent step to the Command Deck over WebSocket
      so the examiner watches it happen in real time. (Claude can pair with you on the Channels
      wiring — it's fiddly and not the interesting part.)

**Milestone (the big one):** run one command to replay the attack, and *without you touching
anything*, the agents detect it, investigate it, build the chain, and fire the safe actions —
streaming live on the Command Deck — then stop at the L4 "disable the CTO's account?" proposal and
wait for your click. That's the heart of the whole demo (CLAUDE.md §14 steps 3–5) working for real.

---

## Week 4 — the voice (LLM, Hindi, purple team, compliance)  ·  freeze Aug 5

**Goal in plain terms:** turn the raw findings into something a non-technical founder understands,
prove the system works, and produce the compliance paperwork.

**Step by step, in `reports/` + scheduled jobs:**

1. [ ] **LLM explanation layer** — the Explainability agent. One small adapter class with two
       backends: `GroqProvider` (default) and `OllamaProvider` (local, optional). It takes the
       *verified facts* (the attack chain, the actions taken) and writes the plain-English
       narrative. **Rule: it only ever describes facts you hand it — it never decides anything.**
2. [ ] **Hindi/Gujarati** — run the English narrative through the IndicTrans2 pipeline you already
       built for CrimeGPT. (You're reusing existing code here, not building translation from
       scratch.) Founder-Mode rupee figures are computed in Python, not written by the LLM.
3. [ ] **Purple team** — a nightly scheduled job (Celery beat) that replays an attack scenario
       against the live pipeline and records how fast it was caught → the readiness score.
4. [ ] **One compliance PDF done properly** — the **CERT-In incident report** (the 6 legally
       required fields, pulled from the provenance trace, in English + Hindi). One done well beats
       four done shallow.
5. [ ] Make the Risk dashboard endpoints real from stored scores.

**Then both of us, final week:** a one-command `seed_demo --reset` so you can re-run the demo
cleanly · rehearse the full §14 script twice end to end · **freeze features Aug 5** · tag
`v1.0.0` and watch the build/scan/deploy workflows go green · leave 3 days of buffer for surprises.

---

## When time gets tight — cut in this exact order

Cut from the top of this list first. Everything here is designed to be *removable without
breaking the demo*:

1. Local Ollama option (keep Groq + the "we can self-host" slide)
2. RBI and SOC-2 compliance packs (keep DPDP + CERT-In)
3. Threat-Prediction agent (keep it as a simple scheduled score, not an agent)
4. Gujarati (keep Hindi + English)
5. The HDBSCAN noise-grouping model (keep simple rule-based dedup; keep Isolation Forest + XGBoost)
6. The Verification Critic agent (keep a plain confidence-threshold check instead)

**Never cut, whatever happens:** the governed action lifecycle, provenance + one-click rollback,
the Neo4j asset graph, the one end-to-end INC-042 run, and the demo reset command. That set *is*
the project — everything else is enhancement.

## House rules

- Branch `feature/*` → PR into `develop` → tag onto `main`. Never commit straight to `main`.
- Don't merge anything red. A broken `develop` blocks both of us.
- Every new endpoint ships with: field names matching `mock.ts`, one "happy path" test, and one
  "another tenant can't see this" test.
- Push to GitHub only when you say so. Claude commits locally and waits for your go.
