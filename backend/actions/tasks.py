"""
Celery tasks for the actions app.

Scheduled housekeeping that lives outside the executor so the executor stays a
pure library. Beat calls ``sweep_auto_rollbacks`` every minute (see
``CELERY_BEAT_SCHEDULE`` in settings).
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def sweep_auto_rollbacks():
    """Revert every L3 action whose auto-rollback timer has expired.

    Delegates to ``actions.executor.apply_due_auto_rollbacks`` when present;
    a missing implementation is a no-op, never an error, so the beat schedule
    is safe to install before the executor grows that capability.
    """
    try:
        from actions.executor import apply_due_auto_rollbacks
    except (ImportError, AttributeError):
        logger.debug("apply_due_auto_rollbacks not available — skipping sweep")
        return {"reverted": 0, "skipped": True}

    reverted = apply_due_auto_rollbacks()
    count = len(reverted) if reverted is not None else 0
    if count:
        logger.info("auto-rollback sweep reverted %s action(s)", count)
    return {"reverted": count}
