"""
Neo4j connection layer (Week 2 step 1).

Thin, deliberately boring: open a driver, run Cypher, stamp tenant_id on
everything. All failures degrade gracefully — the Postgres mirror keeps the
API alive, and callers treat Neo4j as an accelerator, not a dependency.
"""

import atexit
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_driver = None
_available = None  # tri-state: None = untested, True/False = probe result


def get_driver():
    global _driver
    if _driver is None:
        from neo4j import GraphDatabase

        _driver = GraphDatabase.driver(
            settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        atexit.register(_driver.close)
    return _driver


def is_available() -> bool:
    global _available
    if _available is None:
        try:
            get_driver().verify_connectivity()
            _available = True
        except Exception as exc:  # noqa: BLE001 — any driver error means "not available"
            logger.warning("Neo4j unavailable, using Postgres mirror only: %s", exc)
            _available = False
    return _available


def run(query: str, **params):
    with get_driver().session() as session:
        return list(session.run(query, **params))


def upsert_node(tenant_id, external_id, label, node_type, *, criticality="medium",
                compromised=False, meta=""):
    if not is_available():
        return
    run(
        """
        MERGE (n:Object {tenant_id: $tenant_id, external_id: $external_id})
        SET n.label = $label, n.node_type = $node_type,
            n.business_criticality = $criticality,
            n.compromised = $compromised, n.meta = $meta,
            n.last_seen = datetime()
        FOREACH (_ IN CASE WHEN n.first_seen IS NULL THEN [1] ELSE [] END |
            SET n.first_seen = datetime())
        """,
        tenant_id=tenant_id, external_id=external_id, label=label, node_type=node_type,
        criticality=criticality.upper().replace("-", "_"), compromised=compromised, meta=meta,
    )


def upsert_edge(tenant_id, source_id, target_id, rel_label, *, attack=False):
    if not is_available():
        return
    # rel type must be a literal in Cypher; sanitize to the known vocabulary
    rel = "".join(ch for ch in rel_label.upper() if ch.isalnum() or ch == "_") or "RELATES_TO"
    run(
        f"""
        MATCH (s:Object {{tenant_id: $tenant_id, external_id: $source_id}})
        MATCH (t:Object {{tenant_id: $tenant_id, external_id: $target_id}})
        MERGE (s)-[r:{rel}]->(t)
        SET r.attack = $attack
        """,
        tenant_id=tenant_id, source_id=source_id, target_id=target_id, attack=attack,
    )


def blast_radius(tenant_id, target_external_id) -> dict:
    """
    Reachable crown-jewel weight from a target node (ARCHITECTURE §4).
    Returns {"score": 0..1, "crown_jewel_within_2_hops": bool}.
    """
    if not is_available():
        return {"score": 0.0, "crown_jewel_within_2_hops": False}
    rows = run(
        """
        MATCH (t:Object {external_id: $target, tenant_id: $tid})
        MATCH p = (t)-[:HAS_ACCESS_TO|AUTHENTICATES_TO|OWNS*1..4]->(a:Object)
        WITH a, min(length(p)) AS hops
        RETURN sum( CASE a.business_criticality
                      WHEN 'CROWN_JEWEL' THEN 1.0 WHEN 'HIGH' THEN 0.5
                      WHEN 'MEDIUM' THEN 0.2 ELSE 0.05 END / hops ) AS raw_blast,
               max(CASE WHEN a.business_criticality = 'CROWN_JEWEL' AND hops <= 2
                        THEN 1 ELSE 0 END) AS cj_near
        """,
        target=target_external_id, tid=tenant_id,
    )
    if not rows or rows[0]["raw_blast"] is None:
        return {"score": 0.0, "crown_jewel_within_2_hops": False}
    raw = float(rows[0]["raw_blast"])
    return {
        # squash to 0–1: raw 2.0 (a couple of near crown jewels) ≈ 0.67
        "score": round(raw / (raw + 1.0), 2),
        "crown_jewel_within_2_hops": bool(rows[0]["cj_near"]),
    }


def wipe_tenant(tenant_id):
    if not is_available():
        return
    run("MATCH (n:Object {tenant_id: $tid}) DETACH DELETE n", tid=tenant_id)
