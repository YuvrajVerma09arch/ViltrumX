# ViltrumX Orchestrator — LangGraph agent graph (skeleton)

> **Status: structure only.** Implementation starts after frontend demo
> sign-off (owner: Yuvraj + Claude pairing). See root `CLAUDE.md` §4.

Coordinates the 8 specialist agents (Ingestion, Noise-Gate, Prediction,
Detection, Investigation, Verification/Critic, Response Commander,
Explainability) over the ontology. Runs as its own service; talks to the
Django backend over internal APIs and to Redis for the event stream.

```
orchestrator/
├── graph.py          # LangGraph state machine wiring the 8 agents
├── agents/           # one module per specialist agent
├── tools/            # MITRE mapping, geo-IP, ontology queries, action proposals
└── main.py           # service entrypoint
```
