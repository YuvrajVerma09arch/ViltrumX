"""
Row-scoped tenancy helpers (docs/ARCHITECTURE.md §11).

Every authenticated request resolves to exactly one tenant via Membership.
Views must go through `tenant_for(request)` — never query tenant-owned
models unscoped.
"""

from rest_framework.exceptions import PermissionDenied

from core.models import Membership, Tenant


def tenant_for(request) -> Tenant:
    membership = (
        Membership.objects.filter(user=request.user).select_related("tenant").first()
    )
    if membership is None:
        raise PermissionDenied("User has no tenant membership.")
    return membership.tenant


def role_for(request, tenant: Tenant) -> str:
    membership = Membership.objects.filter(user=request.user, tenant=tenant).first()
    return membership.role if membership else "Viewer"
