"""
Postgres mirror of the ontology graph.

Neo4j is the analytical home of the graph (blast radius, attack paths — see
ontology/neo.py). This mirror is the transactional record and the read path
for the API, so the product keeps working when Neo4j is down and tests don't
need a graph database. Writes go to both (ontology/graph.py).
"""

from django.db import models

from core.models import CRITICALITY_CHOICES, Tenant


class OntologyNode(models.Model):
    TYPE_CHOICES = [
        ("user", "User"),
        ("service", "Service account"),
        ("apikey", "API key"),
        ("device", "Device"),
        ("cloud", "Cloud resource"),
        ("repo", "Repo"),
        ("saas", "SaaS app"),
        ("data", "Data asset"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="ontology_nodes")
    external_id = models.CharField(max_length=60)  # "u-priya"
    label = models.CharField(max_length=120)
    node_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    criticality = models.CharField(max_length=12, choices=CRITICALITY_CHOICES, default="medium")
    compromised = models.BooleanField(default=False)
    meta = models.CharField(max_length=200, blank=True, default="")
    risk_score = models.FloatField(default=0.0)
    # layout hints for the built Ontology Explorer
    x = models.IntegerField(default=0)
    y = models.IntegerField(default=0)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tenant", "external_id")]

    def __str__(self):
        return f"{self.label} [{self.node_type}]"


class OntologyEdge(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="ontology_edges")
    external_id = models.CharField(max_length=60)  # "e1"
    source = models.ForeignKey(
        OntologyNode, on_delete=models.CASCADE, related_name="outgoing_edges"
    )
    target = models.ForeignKey(
        OntologyNode, on_delete=models.CASCADE, related_name="incoming_edges"
    )
    label = models.CharField(max_length=40)  # "has_access_to"
    attack = models.BooleanField(default=False)  # part of the highlighted attack path

    class Meta:
        unique_together = [("tenant", "external_id")]

    def __str__(self):
        return f"{self.source.label} -{self.label}-> {self.target.label}"
