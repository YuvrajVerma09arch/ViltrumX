"""
Orchestrator entrypoint (the Dockerfile's CMD).

Two modes:

  worker  (default)  — subscribe to the Redis event stream the backend's
                       ingestion task publishes to, and run the agent graph
                       per event. This is what the container runs.

  replay             — pull a synthetic scenario's events straight from the
                       backend and push them through the graph one by one.
                       This is the demo driver (CLAUDE.md §14 steps 3–5).

Usage:
    python main.py                      # worker, tenant from ORCHESTRATOR_TENANT_ID
    python main.py replay --scenario inc-042 --tenant 1
    python main.py selftest             # prove the graph runs with no services

Every run degrades gracefully: if Redis or the backend is unreachable the
process logs and exits non-zero rather than crashing mid-incident.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("orchestrator")

# The agent modules import each other as top-level packages (`from agents import
# ...`), so the orchestrator directory must be importable as the root.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_TENANT = int(os.environ.get("ORCHESTRATOR_TENANT_ID", "1"))
STREAM_KEY = os.environ.get("ORCHESTRATOR_STREAM", "viltrumx:events")


def _summarise(state: dict) -> str:
    """One-line result of a graph run, for the console and the feed."""
    bits = []
    if state.get("suppressed"):
        bits.append("suppressed by noise-gate")
    else:
        if state.get("anomaly_score") is not None:
            bits.append(f"anomaly={state['anomaly_score']:.2f}")
        bits.append(f"suspicious={state.get('is_suspicious', False)}")
        if state.get("attack_chain"):
            bits.append(f"chain={len(state['attack_chain'])} steps")
        if state.get("incident_id"):
            bits.append(f"incident={state['incident_id']}")
        if state.get("critic_passed") is not None and state.get("attack_chain"):
            bits.append(
                f"critic={'passed' if state.get('critic_passed') else 'refuted'}"
                f"@{state.get('critic_confidence', 0):.2f}"
            )
        actions = state.get("actions_proposed") or []
        if actions:
            levels = ", ".join(
                f"{a.get('id', '?')}:{a.get('level', '?')}/{a.get('status', '?')}"
                for a in actions
                if isinstance(a, dict)
            )
            bits.append(f"actions=[{levels}]")
    return " · ".join(bits) or "no-op"


def run_one(tenant_id: int, raw_event: dict, event_id: int | None = None) -> dict:
    from graph import run_event

    started = time.time()
    state = run_event(tenant_id, raw_event, event_id=event_id)
    took = (time.time() - started) * 1000
    logger.info(
        "event %s (%s) → %s  [%.0f ms]",
        event_id if event_id is not None else "-",
        raw_event.get("event_type") or raw_event.get("name") or "?",
        _summarise(state),
        took,
    )
    return state


# ── modes ────────────────────────────────────────────────────────────────────
def cmd_selftest(args) -> int:
    """Prove the graph is wired without needing Redis, Neo4j, or the backend.

    Every agent degrades gracefully when the backend is unreachable, so this
    exercises the real topology — it just won't produce findings.
    """
    from graph import build_graph

    graph = build_graph()
    nodes = sorted(n for n in graph.get_graph().nodes if not n.startswith("__"))
    logger.info("graph compiled with %d agents: %s", len(nodes), ", ".join(nodes))

    event = {
        "source": "workspace",
        "event_type": "login_success",
        "principal": "priya.sharma@paykraft.in",
        "ip": "185.220.101.34",
        "geo": "Moscow, RU",
        "attack": True,
    }
    state = run_one(args.tenant, event)
    logger.info("selftest complete — graph ran end to end")
    if args.verbose:
        print(json.dumps({k: v for k, v in state.items() if v}, indent=2, default=str))
    return 0


def cmd_replay(args) -> int:
    """Drive the demo: ask the backend for a scenario's events, run each."""
    from tools.django_client import get

    payload = get(f"ingest/scenario/{args.scenario}") or {}
    events = payload.get("events") or []
    if not events:
        logger.error(
            "no events for scenario %r — is the backend up and the service "
            "token set? (ORCHESTRATOR_SERVICE_TOKEN)",
            args.scenario,
        )
        return 1

    logger.info("replaying %s — %d events", args.scenario, len(events))
    findings = 0
    for item in events:
        raw = item.get("raw", item)
        state = run_one(args.tenant, raw, event_id=item.get("id"))
        if state.get("actions_proposed"):
            findings += 1
        if args.delay:
            time.sleep(args.delay)
    logger.info("replay complete — %d event(s) produced governed actions", findings)
    return 0


def cmd_worker(args) -> int:
    """Consume the backend's Redis event stream and run the graph per event."""
    try:
        import redis
    except ImportError:
        logger.error("redis package missing — pip install -r requirements.txt")
        return 1

    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        client = redis.Redis.from_url(url, decode_responses=True)
        client.ping()
    except Exception as exc:  # noqa: BLE001
        logger.error("cannot reach Redis at %s: %s", url, exc)
        return 1

    pubsub = client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(STREAM_KEY)
    logger.info("worker listening on %s (tenant %s)", STREAM_KEY, args.tenant)

    try:
        for message in pubsub.listen():
            try:
                body = json.loads(message["data"])
            except (TypeError, ValueError):
                logger.warning("skipping non-JSON message")
                continue
            run_one(
                body.get("tenant_id", args.tenant),
                body.get("raw_event", body),
                event_id=body.get("event_id"),
            )
    except KeyboardInterrupt:
        logger.info("worker stopped")
    finally:
        pubsub.close()
        from tools.django_client import close

        close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orchestrator", description=__doc__)
    parser.add_argument(
        "--tenant", type=int, default=DEFAULT_TENANT, help="tenant id (default: env)"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="mode")

    sub.add_parser("worker", help="consume the Redis event stream (default)")
    sub.add_parser("selftest", help="run one synthetic event through the graph")

    replay = sub.add_parser("replay", help="replay a synthetic scenario")
    replay.add_argument("--scenario", default="inc-042")
    replay.add_argument(
        "--delay", type=float, default=0.0, help="seconds between events (demo pacing)"
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    handler = {
        "replay": cmd_replay,
        "selftest": cmd_selftest,
        "worker": cmd_worker,
        None: cmd_worker,
    }[args.mode]
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
