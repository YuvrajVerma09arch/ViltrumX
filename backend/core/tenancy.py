"""
Row-scoped tenancy + role-based access control (docs/ARCHITECTURE.md §11).

Every authenticated request resolves to exactly one tenant via Membership.
Views must go through `tenant_for(request)` — never query tenant-owned
models unscoped. Write endpoints additionally call `require_role(...)` so a
Viewer cannot approve containment, edit the policy, or connect a source.
"""

from rest_framework.exceptions import PermissionDenied

from core.models import Membership, Tenant

# Role hierarchy: higher integer = more privilege. An endpoint declares the
# minimum role it needs; the caller must be at or above it.
ROLE_RANK = {"Viewer": 0, "Analyst": 1, "Admin": 2, "Owner": 3}


def tenant_for(request) -> Tenant:
    membership = (
        Membership.objects.filter(user=request.user).select_related("tenant").first()
    )
    if membership is None:
        raise PermissionDenied("User has no tenant membership.")
    return membership.tenant


def membership_for(request, tenant: Tenant) -> Membership | None:
    return Membership.objects.filter(user=request.user, tenant=tenant).first()


def role_for(request, tenant: Tenant) -> str:
    m = membership_for(request, tenant)
    return m.role if m else "Viewer"


def has_role(request, tenant: Tenant, min_role: str) -> bool:
    return ROLE_RANK.get(role_for(request, tenant), -1) >= ROLE_RANK.get(min_role, 99)


def require_role(request, tenant: Tenant, min_role: str) -> None:
    """Raise PermissionDenied unless the caller holds at least ``min_role``.

    Used by every write endpoint. The service-token orchestrator is an Analyst
    (see service_auth), so it can propose/investigate but NOT approve L4
    actions, edit the policy, or connect sources — those stay human-admin work.
    """
    if not has_role(request, tenant, min_role):
        raise PermissionDenied(
            f"This action requires the {min_role} role or higher."
        )
