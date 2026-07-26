from django.db import models

from core.models import Tenant


class Connector(models.Model):
    STATUS_CHOICES = [
        ("available", "Available"),
        ("connected", "Connected"),
        ("error", "Error"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="connectors")
    connector_id = models.CharField(max_length=20)  # "gw", "gh", "aws", ...
    name = models.CharField(max_length=60)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="available")
    connected_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tenant", "connector_id")]

    def __str__(self):
        return f"{self.name} [{self.status}]"


class RawEvent(models.Model):
    """Normalized event envelope — every log line lands here before scoring."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="raw_events")
    source = models.CharField(max_length=30)  # workspace | cloudtrail | github
    event_type = models.CharField(max_length=60)
    principal = models.CharField(max_length=200)  # who did it
    target = models.CharField(max_length=200, blank=True, default="")
    ip = models.GenericIPAddressField(null=True, blank=True)
    geo = models.CharField(max_length=60, blank=True, default="")
    occurred_at = models.DateTimeField()
    payload = models.JSONField(default=dict)
    anomaly_score = models.FloatField(null=True, blank=True)  # set by detection
    is_attack = models.BooleanField(default=False)  # synthetic ground-truth label

    class Meta:
        ordering = ["occurred_at"]
        indexes = [models.Index(fields=["tenant", "occurred_at"])]

    def __str__(self):
        return f"{self.event_type} by {self.principal}"
