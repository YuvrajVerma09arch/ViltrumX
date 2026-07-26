from django.db import models

from core.models import Tenant


class IncidentNarrative(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="narratives")
    incident_external_id = models.CharField(max_length=20)
    lang = models.CharField(max_length=5)  # "en" | "hi" | "gu"
    technical = models.TextField()
    founder = models.TextField()
    impact = models.JSONField(default=list)
    decision = models.CharField(max_length=300)
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tenant", "incident_external_id", "lang")]

    def __str__(self):
        return f"{self.incident_external_id} [{self.lang}]"


class ReadinessScore(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="readiness_scores")
    week_label = models.CharField(max_length=10)
    score = models.IntegerField()

    class Meta:
        ordering = ["id"]
        unique_together = [("tenant", "week_label")]

    def __str__(self):
        return f"{self.week_label}: {self.score}"


class PurpleScenario(models.Model):
    RESULT_CHOICES = [
        ("passed", "Passed"),
        ("warning", "Warning"),
        ("failed", "Failed"),
        ("scheduled", "Scheduled"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="purple_scenarios")
    external_id = models.CharField(max_length=10)  # "PT-01"
    name = models.CharField(max_length=100)
    desc = models.CharField(max_length=300)
    last_run_label = models.CharField(max_length=60)
    result = models.CharField(max_length=10, choices=RESULT_CHOICES, default="scheduled")
    detection_label = models.CharField(max_length=20, default="—")
    containment_label = models.CharField(max_length=20, default="—")
    detection_seconds = models.IntegerField(null=True, blank=True)
    containment_seconds = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = [("tenant", "external_id")]
        ordering = ["external_id"]

    def __str__(self):
        return f"{self.external_id} {self.name} [{self.result}]"


class ComplianceExport(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="compliance_exports")
    framework_id = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=60)
    when_label = models.CharField(max_length=40)
    content = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.framework_id})"
