"""
Core system-of-record models (Week 1 — "the ledger").

Every tenant-owned row carries a `tenant` FK; views must always filter
through it (docs/ARCHITECTURE.md §11 — row-scoped tenancy, not schemas).
"""

from django.conf import settings
from django.db import models

CRITICALITY_CHOICES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("crown-jewel", "Crown Jewel"),
]

SEVERITY_CHOICES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]


class Tenant(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    # Pillar 5 — sovereign inference: per-tenant explanation-LLM provider.
    llm_provider = models.CharField(
        max_length=20, default="groq", choices=[("groq", "Groq"), ("ollama", "Ollama")]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.slug


class Membership(models.Model):
    ROLE_CHOICES = [
        ("Owner", "Owner"),  # approves L4, edits policy/billing
        ("Admin", "Admin"),  # connectors, criticality, members
        ("Analyst", "Analyst"),  # investigations, proposals
        ("Viewer", "Viewer"),  # read-only
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="Viewer")
    display_name = models.CharField(max_length=120)
    last_label = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        unique_together = [("user", "tenant")]

    def __str__(self):
        return f"{self.display_name} ({self.role} @ {self.tenant.slug})"


class AuditEvent(models.Model):
    """Append-only: who did what, when. Never updated or deleted in code."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="audit_events")
    actor = models.CharField(max_length=200)  # email or "system:<agent>"
    event_type = models.CharField(max_length=60)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.actor} {self.event_type}"


class Incident(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("investigating", "Investigating"),
        ("contained", "Contained"),
        ("resolved", "Resolved"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="incidents")
    external_id = models.CharField(max_length=20)  # "INC-042"
    title = models.CharField(max_length=300)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="open")
    entity = models.CharField(max_length=200)
    time_label = models.CharField(max_length=60)  # display string ("03:31 IST today")
    occurred_at = models.DateTimeField()
    mitre = models.JSONField(default=list)  # ["T1078", ...]
    confidence = models.FloatField(null=True, blank=True)  # critic-verified confidence

    class Meta:
        unique_together = [("tenant", "external_id")]
        ordering = ["-occurred_at"]

    def __str__(self):
        return f"{self.external_id}: {self.title[:40]}"


class AttackStep(models.Model):
    """One hop of an incident's attack chain (Investigation agent output)."""

    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="attack_steps")
    order = models.PositiveSmallIntegerField()
    time_label = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    detail = models.TextField()
    mitre = models.CharField(max_length=20)
    mitre_name = models.CharField(max_length=100)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)

    class Meta:
        ordering = ["order"]
        unique_together = [("incident", "order")]

    def __str__(self):
        return f"{self.incident.external_id} step {self.order}: {self.title[:30]}"


class EvidenceItem(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="evidence_items")
    order = models.PositiveSmallIntegerField()
    external_id = models.CharField(max_length=20)  # "EV-1"
    kind = models.CharField(max_length=60)
    source = models.CharField(max_length=100)
    excerpt = models.TextField()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.external_id} ({self.kind})"


class AgentState(models.Model):
    """Last-known status per specialist agent (Week 3: updated by the pipeline)."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="agent_states")
    agent_id = models.CharField(max_length=20)  # "ingest", "detect", ...
    name = models.CharField(max_length=60)
    role = models.CharField(max_length=60)
    status = models.CharField(max_length=30, default="idle")
    current_task = models.CharField(max_length=200, blank=True, default="")
    stat = models.CharField(max_length=100, blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tenant", "agent_id")]
        ordering = ["order"]

    def __str__(self):
        return f"{self.name} [{self.status}]"


class FeedLine(models.Model):
    """Command Deck activity feed (Week 3: appended live by the pipeline)."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="feed_lines")
    time_label = models.CharField(max_length=20)
    agent = models.CharField(max_length=40)
    line = models.CharField(max_length=300)
    tone = models.CharField(max_length=10, default="info")  # info | ok | warn | action
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.time_label} {self.agent}: {self.line[:40]}"
