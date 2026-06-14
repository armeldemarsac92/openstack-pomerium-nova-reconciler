from __future__ import annotations

import unittest

from mustelinet_reconciler.application.services.reconciliation_service import ReconciliationService
from mustelinet_reconciler.config.settings import OpenStackSettings, PomeriumSettings
from mustelinet_reconciler.domain.models.openstack import Instance, NetworkAddress, Project
from mustelinet_reconciler.domain.services.reconciliation_planner import ReconciliationPlanner
from mustelinet_reconciler.domain.services.route_builder import PomeriumRouteBuilder
from mustelinet_reconciler.infrastructure.memory import (
    MemoryInstanceRepository,
    MemoryPomeriumRouteRepository,
    MemoryProjectRepository,
)


class ReconciliationServiceTests(unittest.TestCase):
    def test_reconcile_applies_route_upserts(self) -> None:
        settings = PomeriumSettings()
        openstack_settings = OpenStackSettings()
        routes = MemoryPomeriumRouteRepository()
        service = ReconciliationService(
            projects=MemoryProjectRepository([Project(id="p1", name="otterlab")]),
            instances=MemoryInstanceRepository(
                [
                    Instance(
                        id="vm1",
                        name="web01",
                        project_id="p1",
                        status="ACTIVE",
                        region="par1",
                        addresses=(NetworkAddress("public", "203.0.113.10", 4, "floating"),),
                    )
                ]
            ),
            routes=routes,
            planner=ReconciliationPlanner(
                openstack_settings,
                settings,
                PomeriumRouteBuilder(openstack_settings, settings),
            ),
            pomerium_settings=settings,
        )

        plan = service.reconcile()

        self.assertEqual(1, len(plan.route_upserts))
        self.assertIn("par1:vm1", routes.routes)
        self.assertEqual("ssh://web01-otterlab", routes.routes["par1:vm1"].from_url)
        self.assertEqual("203.0.113.10", routes.routes["par1:vm1"].address)


if __name__ == "__main__":
    unittest.main()
