from __future__ import annotations

import unittest

from mustelinet_reconciler.application.services.reconciliation_service import ReconciliationService
from mustelinet_reconciler.config.settings import TeleportSettings
from mustelinet_reconciler.domain.models.openstack import Instance, Project
from mustelinet_reconciler.domain.services.node_builder import TeleportNodeBuilder
from mustelinet_reconciler.domain.services.reconciliation_planner import ReconciliationPlanner
from mustelinet_reconciler.infrastructure.memory import (
    MemoryInstanceRepository,
    MemoryProjectRepository,
    MemoryTeleportNodeRepository,
)


class ReconciliationServiceTests(unittest.TestCase):
    def test_reconcile_applies_upserts(self) -> None:
        settings = TeleportSettings()
        nodes = MemoryTeleportNodeRepository()
        service = ReconciliationService(
            projects=MemoryProjectRepository([Project(id="p1", name="otterlab")]),
            instances=MemoryInstanceRepository(
                [Instance(id="vm1", name="web01", project_id="p1", status="ACTIVE", region="par1")]
            ),
            nodes=nodes,
            planner=ReconciliationPlanner(settings, TeleportNodeBuilder(settings)),
            teleport_settings=settings,
        )

        plan = service.reconcile()

        self.assertEqual(1, len(plan.upserts))
        self.assertIn("par1:vm1", nodes.nodes)


if __name__ == "__main__":
    unittest.main()
