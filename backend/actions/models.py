"""
Governed Action lifecycle models (Week 1 — "the ledger").

State machine (docs/ARCHITECTURE.md §5):
proposed → (L4: human approves/vetoes) → executing → executed → rolled-back
The API surface exposes: proposed | executed | rolled-back | failed | vetoed.
"""

from django.db import models

from core.models import Incident, Tenant

LEVEL_CHOICES = [("L1", "L1"), ("L2", "L2"), ("L3", "L3"), ("L4", "L4")]


class AutonomyPolicy(models.Model):
    """One immutable version of the autonomy dial. PUT /policies creates a new one."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="policies")
    version = models.PositiveIntegerField()
    created_by = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("tenant", "version")]
        ordering = ["-version"]

    def __str__(self):
        return f"{self.tenant.slug} policy v{self.version}"

    @classmethod
    def current_for(cls, tenant):
        return cls.objects.filter(tenant=tenant).order_by("-version").first()

    def as_rows(self):
        return [
            {
                "actionType": r.action_type,
                "level": r.level,
                "crownJewelOverride": r.crown_jewel_override,
            }
            for r in self.rules.all()
        ]


class PolicyRule(models.Model):
    policy = models.ForeignKey(AutonomyPolicy, on_delete=models.CASCADE, related_name="rules")
    action_type = models.CharField(max_length=40)
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES)
    crown_jewel_override = models.CharField(max_length=2, choices=LEVEL_CHOICES)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        unique_together = [("policy", "action_type")]

    def __str__(self):
        return f"{self.action_type}: {self.level} (cj {self.crown_jewel_override})"


class Action(models.Model):
    STATUS_CHOICES = [
        ("proposed", "Proposed"),  # L4 awaiting human decision
        ("executed", "Executed"),
        ("rolled-back", "Rolled back"),
        ("failed", "Failed"),
        ("vetoed", "Vetoed"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="actions")
    incident = models.ForeignKey(
        Incident, on_delete=models.SET_NULL, null=True, blank=True, related_name="actions"
    )
    external_id = models.CharField(max_length=20)  # "ACT-2213"
    action_type = models.CharField(max_length=40)
    target = models.CharField(max_length=200)
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="proposed")
    blast_radius = models.FloatField(default=0.0)
    time_label = models.CharField(max_length=60)
    rollback_plan = models.CharField(max_length=300)
    policy_version = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    auto_rollback_at = models.DateTimeField(null=True, blank=True)  # L3 timer

    class Meta:
        unique_together = [("tenant", "external_id")]
        ordering = ["-created_at", "-external_id"]

    def __str__(self):
        return f"{self.external_id} {self.action_type} → {self.target}"

    @classmethod
    def next_external_id(cls, tenant) -> str:
        last = 2200
        for eid in cls.objects.filter(tenant=tenant).values_list("external_id", flat=True):
            try:
                last = max(last, int(eid.split("-")[1]))
            except (IndexError, ValueError):
                continue
        return f"ACT-{last + 1}"


class ProvenanceStep(models.Model):
    """Append-only decision trace. Rollbacks append new steps, never rewrite."""

    action = models.ForeignKey(Action, on_delete=models.CASCADE, related_name="trace")
    order = models.PositiveSmallIntegerField()
    step = models.CharField(max_length=120)
    detail = models.TextField()
    ok = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]
        unique_together = [("action", "order")]

    def __str__(self):
        return f"{self.action.external_id} #{self.order} {self.step}"
