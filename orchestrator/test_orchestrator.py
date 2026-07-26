def test_imports():
    """Smoke test: all agent modules import without error."""
    from agents import (  # noqa: F401
        critic,
        detect,
        explain,
        investigate,
        noisegate,
        predict,
        respond,
        sync,
    )


def test_graph_builds():
    """The LangGraph compiles with all 8 agent nodes."""
    from graph import build_graph

    graph = build_graph()
    nodes = set(
        n for n in graph.get_graph().nodes if not n.startswith("__")
    )
    expected = {
        "sync",
        "noisegate",
        "predict",
        "detect",
        "investigate",
        "critic",
        "respond",
        "explain",
    }
    assert nodes == expected


def test_state_schema():
    """State dict has all required keys with correct defaults."""
    from state import fresh_state

    state = fresh_state(
        tenant_id=1,
        raw_event={"event_type": "login_success", "principal": "test@test.com"},
        event_id=1,
    )  # noqa: E501
    assert state["tenant_id"] == 1
    assert state["anomaly_score"] is None
    assert state["suppressed"] is False
    assert state["attack_chain"] == []
    assert state["actions_proposed"] == []