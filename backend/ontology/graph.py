"""
Ontology read/write facade.

Writes go to the Postgres mirror (transactional record) and to Neo4j
(graph analytics) in one call. Reads for the API come from the mirror;
blast radius prefers Neo4j and falls back to a BFS over the mirror.
"""

from collections import deque

from ontology import neo
from ontology.models import OntologyEdge, OntologyNode

TRAVERSAL_LABELS = {"has_access_to", "authenticates_to", "owns", "leaked_in_history"}

CRITICALITY_WEIGHT = {"crown-jewel": 1.0, "high": 0.5, "medium": 0.2, "low": 0.05}


def upsert_node(tenant, external_id, label, node_type, *, criticality="medium",
                compromised=False, meta="", x=0, y=0):
    node, _ = OntologyNode.objects.update_or_create(
        tenant=tenant, external_id=external_id,
        defaults={
            "label": label, "node_type": node_type, "criticality": criticality,
            "compromised": compromised, "meta": meta,
            **({"x": x, "y": y} if x or y else {}),
        },
    )
    neo.upsert_node(
        tenant.id, external_id, label, node_type,
        criticality=criticality, compromised=compromised, meta=meta,
    )
    return node


def upsert_edge(tenant, external_id, source_id, target_id, label, *, attack=False):
    source = OntologyNode.objects.get(tenant=tenant, external_id=source_id)
    target = OntologyNode.objects.get(tenant=tenant, external_id=target_id)
    edge, _ = OntologyEdge.objects.update_or_create(
        tenant=tenant, external_id=external_id,
        defaults={"source": source, "target": target, "label": label, "attack": attack},
    )
    neo.upsert_edge(tenant.id, source_id, target_id, label, attack=attack)
    return edge


def get_graph(tenant) -> dict:
    nodes = [
        {
            "id": n.external_id, "label": n.label, "type": n.node_type,
            "criticality": n.criticality, "x": n.x, "y": n.y, "meta": n.meta,
            **({"compromised": True} if n.compromised else {}),
        }
        for n in OntologyNode.objects.filter(tenant=tenant).order_by("id")
    ]
    edges = [
        {
            "id": e.external_id, "source": e.source.external_id,
            "target": e.target.external_id, "label": e.label,
            **({"attack": True} if e.attack else {}),
        }
        for e in OntologyEdge.objects.filter(tenant=tenant).select_related("source", "target")
    ]
    return {"nodes": nodes, "edges": edges}


# Inventory categories are views over node types (+ risk scores from detection)
_CATEGORY_TYPES = {
    "identities": ["user", "service"],
    "cloud": ["cloud"],
    "repos": ["repo"],
    "saas": ["saas"],
}


def get_inventory(tenant, category):
    if category not in _CATEGORY_TYPES:
        return None
    from core import demo_data

    fixture_rows = {
        "identities": demo_data.INV_IDENTITIES,
        "cloud": demo_data.INV_CLOUD,
        "repos": demo_data.INV_REPOS,
        "saas": demo_data.INV_SAAS,
    }[category]
    nodes = OntologyNode.objects.filter(
        tenant=tenant, node_type__in=_CATEGORY_TYPES[category]
    ).order_by("id")
    if not nodes.exists():
        return fixture_rows

    # posture/kind columns come from curated fixture text keyed by entity name;
    # risk + criticality are live from the graph
    fixture_by_name = {}
    for row in fixture_rows:
        key = row["name"].split("@")[0].replace("s3://", "").lower()
        fixture_by_name[key] = row

    rows = []
    for n in nodes:
        key = n.label.split("@")[0].replace("s3://", "").lower()
        fixture = fixture_by_name.get(key, {})
        base = {
            "name": fixture.get("name", n.label),
            "kind": fixture.get("kind", n.get_node_type_display()),
            "risk": int(round(n.risk_score)) if n.risk_score else fixture.get("risk", 10),
            "criticality": n.criticality,
        }
        if category == "identities":
            base["mfa"] = fixture.get("mfa", True)
        else:
            base["posture"] = fixture.get("posture", "baseline posture")
        rows.append(base)
    return rows


def blast_radius(tenant, target_external_id) -> dict:
    """Neo4j first; if unavailable, BFS over the Postgres mirror (same weights)."""
    if neo.is_available():
        return neo.blast_radius(tenant.id, target_external_id)

    start = OntologyNode.objects.filter(tenant=tenant, external_id=target_external_id).first()
    if start is None:
        return {"score": 0.0, "crown_jewel_within_2_hops": False}

    adjacency = {}
    edges = OntologyEdge.objects.filter(
        tenant=tenant, label__in=TRAVERSAL_LABELS
    ).select_related("source", "target")
    for e in edges:
        adjacency.setdefault(e.source.external_id, []).append(e.target)

    raw, cj_near, seen = 0.0, False, {start.external_id: 0}
    queue = deque([(start, 0)])
    while queue:
        node, hops = queue.popleft()
        if hops >= 4:
            continue
        for neighbor in adjacency.get(node.external_id, []):
            if neighbor.external_id in seen:
                continue
            seen[neighbor.external_id] = hops + 1
            raw += CRITICALITY_WEIGHT.get(neighbor.criticality, 0.05) / (hops + 1)
            if neighbor.criticality == "crown-jewel" and hops + 1 <= 2:
                cj_near = True
            queue.append((neighbor, hops + 1))
    return {"score": round(raw / (raw + 1.0), 2), "crown_jewel_within_2_hops": cj_near}


def resolve_entity(tenant, name_or_id):
    """Best-effort entity resolution from a log principal to an ontology node."""
    name = (name_or_id or "").split("@")[0].lower()
    node = OntologyNode.objects.filter(tenant=tenant, external_id=name_or_id).first()
    if node:
        return node
    for n in OntologyNode.objects.filter(tenant=tenant):
        if name and name in n.label.lower():
            return n
    return None
