"""
Celery tasks for the reports app.

Nightly purple-team rotation + readiness recompute, driven by
``CELERY_BEAT_SCHEDULE`` (daily 02:30 IST).
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def nightly_readiness():
    """Run every purple-team scenario for every tenant and refresh readiness.

    Delegates to ``reports.purple.run_all_scenarios`` when present; a missing
    implementation is a no-op so the beat schedule installs safely. Per-tenant
    failures are logged and isolated — one broken tenant never aborts the run.
    """
    try:
        from reports.purple import run_all_scenarios
    except (ImportError, AttributeError):
        logger.debug("run_all_scenarios not available — skipping nightly readiness")
        return {"tenants": 0, "skipped": True}

    from core.models import Tenant

    tenants = 0
    for tenant in Tenant.objects.all().only("id", "slug"):
        try:
            run_all_scenarios(tenant)
            tenants += 1
        except Exception as exc:  # noqa: BLE001 — isolate per-tenant failures
            logger.warning("nightly readiness failed for tenant %s: %s", tenant.slug, exc)
    logger.info("nightly_readiness completed for %s tenant(s)", tenants)
    return {"tenants": tenants}
