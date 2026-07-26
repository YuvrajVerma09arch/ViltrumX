from django.db import models

from core.models import Tenant


class RiskSnapshot(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="risk_snapshots")
    day_label = models.CharField(max_length=20)
    org_score = models.IntegerField(null=True, blank=True)
    forecast = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        unique_together = [("tenant", "day_label")]

    def __str__(self):
        return f"{self.day_label}: org {self.org_score}"


class EntityRisk(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="entity_risks")
    entity = models.CharField(max_length=200)
    entity_type = models.CharField(max_length=40)
    score = models.IntegerField(default=0)
    trend = models.CharField(max_length=20, blank=True, default="")
    reason = models.CharField(max_length=300, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-score"]
        unique_together = [("tenant", "entity")]

    def __str__(self):
        return f"{self.entity}: {self.score}"
