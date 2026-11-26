"""
Core system-of-record models (Week 1 — "the ledger").

Every tenant-owned row carries a `tenant` FK; views must always filter
through it (docs/ARCHITECTURE.md §11 — row-scoped tenancy, not schemas).
"""

import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import models
from django.utils import timezone

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
    # ── Per-tenant service surface (flexibility) ──────────────────────────────
    # Which product modules this tenant's plan/contract includes. The UI and
    # API read these to show only the surfaces a client actually bought — two
    # customers can sit on the same platform with different modules. An empty
    # list means "all default modules" (so existing tenants are unaffected).
    enabled_modules = models.JSONField(default=list, blank=True)
    # Connector ids this tenant is entitled to configure (e.g. ["gh","gw","aws"]).
    enabled_connectors = models.JSONField(default=list, blank=True)
    # ── Startup verification (P4) ─────────────────────────────────────────────
    # A real customer proves control of their company domain (DNS TXT) and,
    # optionally, their GSTIN. Until domain-verified the tenant is an
    # unactivated trial (no live data ingest). No plaintext secret stored.
    domain = models.CharField(max_length=253, blank=True, default="")  # "acme.in"
    domain_token = models.CharField(max_length=80, blank=True, default="")  # TXT value
    domain_verified_at = models.DateTimeField(null=True, blank=True)
    gstin = models.CharField(max_length=15, blank=True, default="")
    gstin_legal_name = models.CharField(max_length=200, blank=True, default="")
    gstin_verified_at = models.DateTimeField(null=True, blank=True)
    verification_status = models.CharField(
        max_length=20, default="pending_domain",
        choices=[
            ("pending_domain", "Pending domain"),
            ("domain_verified", "Domain verified"),
            ("fully_verified", "Fully verified"),
            ("rejected", "Rejected"),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Default module surface for every new tenant unless overridden.
    DEFAULT_MODULES = [
        "command_deck", "ontology", "investigation", "autonomy", "provenance",
        "risk", "inventory", "purple", "compliance",
    ]

    def __str__(self):
        return self.slug

    def has_module(self, module: str) -> bool:
        """True when this tenant is entitled to ``module``.

        An empty ``enabled_modules`` means "all defaults", so a tenant that
        never customised gets the full product.
        """
        if not self.enabled_modules:
            return module in self.DEFAULT_MODULES
        return module in self.enabled_modules

    def connector_enabled(self, connector_id: str) -> bool:
        """True when this tenant may configure ``connector_id``."""
        if not self.enabled_connectors:
            return True  # no explicit restriction → all available
        return connector_id in self.enabled_connectors

    @property
    def domain_verified(self) -> bool:
        return self.domain_verified_at is not None


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


class VerificationCode(models.Model):
    """A short-lived, hashed, single-use email code for signup / owner login.

    Only ``code_hash`` is ever persisted — the plaintext 6-digit code exists just
    long enough to be emailed. Issuing a new code supersedes any still-pending
    one for the same email + purpose, so an older code can never be replayed.
    """

    PURPOSE_CHOICES = [
        ("signup", "Signup"),
        ("login", "Login"),
    ]

    challenge_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=255)
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    attempts = models.PositiveSmallIntegerField(default=0)
    resend_count = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["email", "purpose", "-created_at"])]

    def __str__(self):
        return f"{self.purpose} code for {self.email}"

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    @property
    def is_locked(self) -> bool:
        return self.attempts >= settings.VERIFICATION_MAX_ATTEMPTS

    def check_code(self, raw_code: str) -> bool:
        """Constant-time-ish verify against the stored hash (never store plaintext)."""
        return check_password(str(raw_code), self.code_hash)
