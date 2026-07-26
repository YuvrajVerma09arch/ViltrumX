"""
Service-token authentication (ARCH §6).

Allows the orchestrator to call the governed Django API without a JWT. The
token is in settings.ORCHESTRATOR_SERVICE_TOKEN (env-sourced, never in the
repo). When present and matching, the caller is impersonated as a synthetic
service User tied to the 'system:orchestrator' actor — so AuditEvent rows
record the agent, not a human.

This class is added to REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] so
the entire v1 router accepts EITHER a JWT (regular users) OR a service
token (the orchestrator). The permission model per-view is unchanged.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication


class ServiceTokenAuthentication(BaseAuthentication):
    """Accept `Authorization: Bearer <token>` where token matches the
    orchestrator service token, authenticating as the synthetic orchestrator
    service user."""

    keyword = "Bearer"

    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith(f"{self.keyword} "):
            return None

        token = header[len(self.keyword) + 1:].strip()
        expected = getattr(settings, "ORCHESTRATOR_SERVICE_TOKEN", "")
        if not expected or token != expected:
            return None

        User = get_user_model()
        user, _ = User.objects.get_or_create(
            username="system:orchestrator",
            defaults={
                "is_staff": True,
                "is_active": True,
                "email": "orchestrator@viltrumx.internal",
            },
        )
        self._ensure_membership(user, request)
        return (user, None)

    @staticmethod
    def _ensure_membership(user, request):
        """Bind the service user to a tenant.

        Every tenant-scoped view resolves through `core.tenancy.tenant_for`,
        which reads Membership — so without one the orchestrator would 403 on
        every call. The tenant comes from the `X-Tenant` header when supplied
        (multi-tenant deployments), otherwise the single/first tenant.

        Role is Analyst, not Owner, on purpose: the agent may propose and
        investigate, but approving its own L4 action stays a human's job.
        """
        from core.models import Membership, Tenant

        if Membership.objects.filter(user=user).exists():
            return

        slug = request.META.get("HTTP_X_TENANT", "")
        tenant = (
            Tenant.objects.filter(slug=slug).first()
            if slug
            else Tenant.objects.order_by("id").first()
        )
        if tenant is None:
            return  # no tenants yet — tenant_for() will raise, which is correct

        Membership.objects.get_or_create(
            user=user,
            tenant=tenant,
            defaults={"role": "Analyst", "display_name": "ViltrumX Orchestrator"},
        )

    def authenticate_header(self, request):
        return self.keyword
