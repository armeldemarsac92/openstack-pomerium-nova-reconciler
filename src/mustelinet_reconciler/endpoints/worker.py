from __future__ import annotations

import logging
import time

from mustelinet_reconciler.application.services.reconciliation_service import ReconciliationService

LOGGER = logging.getLogger(__name__)


def run_worker(
    *,
    service: ReconciliationService,
    poll_interval_seconds: int,
    dry_run: bool,
) -> None:
    while True:
        plan = service.reconcile(dry_run=dry_run)
        LOGGER.info(
            "reconciliation_pass_complete actions=%s skipped=%s dry_run=%s",
            len(plan.actions),
            len(plan.skipped),
            dry_run,
        )
        time.sleep(poll_interval_seconds)
