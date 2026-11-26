from django.db import models

from core.models import Tenant


class OAuthState(models.Model):
    """Short-lived OAuth state tokens (used instead of session to survive
    cross-site GitHub redirects). Created during OAuth start, consumed
    during callback, expired via `expires_at`."""
    state = models.CharField(max_length=128, unique=True)
    tenant_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["expires_at"])]

    def __str__(self):
        return f"OAuthState({self.state[:12]}… → tenant {self.tenant_id})"


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
    # Multi-source provider + generic secret material. ``credentials`` holds
    # per-provider tokens / service-account JSON refs — NEVER log this field.
    provider = models.CharField(max_length=20, blank=True, default="")
    credentials = models.JSONField(default=dict, blank=True)
    last_polled_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    # GitHub OAuth fields
    github_installation_id = models.BigIntegerField(null=True, blank=True)
    github_access_token = models.TextField(blank=True, default="")  # encrypted in production
    github_app_id = models.CharField(max_length=60, blank=True, default="")
    github_org_login = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        unique_together = [("tenant", "connector_id")]

    def __str__(self):
        return f"{self.name} [{self.status}]"


class PollCursor(models.Model):
    """Per-connector incremental polling position (e.g. last GitHub audit id)."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="poll_cursors")
    connector_id = models.CharField(max_length=20)
    cursor_key = models.CharField(max_length=60)
    cursor_value = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tenant", "connector_id", "cursor_key")]

    def __str__(self):
        return f"{self.connector_id}:{self.cursor_key}={self.cursor_value[:24]}"


class IngestedEvent(models.Model):
    """Dedupe ledger — guarantees a provider event is ingested at most once."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="ingested_events")
    source = models.CharField(max_length=30)
    external_id = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("tenant", "source", "external_id")]

    def __str__(self):
        return f"{self.source}:{self.external_id}"


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


class TrackedSession(models.Model):
    """A live external session we may later revoke (P3 actuation).

    Populated by provider pollers from real login/session events, so
    ``revoke_session`` acts on a concrete provider session id rather than a
    free-text principal. Empty for the demo tenant unless seeded.
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="sessions")
    provider = models.CharField(max_length=20)  # github | workspace | aws
    principal = models.CharField(max_length=200)
    external_session_id = models.CharField(max_length=200)  # provider's own id
    ip = models.GenericIPAddressField(null=True, blank=True)
    geo = models.CharField(max_length=60, blank=True, default="")
    created_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_error = models.TextField(blank=True, default="")

    class Meta:
        unique_together = [("tenant", "provider", "external_session_id")]
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "principal", "revoked_at"])]

    def __str__(self):
        return f"{self.provider}:{self.principal} ({'active' if self.active else 'revoked'})"

    @property
    def active(self) -> bool:
        return self.revoked_at is None
