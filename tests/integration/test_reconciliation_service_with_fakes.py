from __future__ import annotations

import unittest

from mustelinet_reconciler.application.services.reconciliation_service import ReconciliationService
from mustelinet_reconciler.config.settings import OpenStackSettings, TeleportSettings
from mustelinet_reconciler.domain.models.openstack import Instance, NetworkAddress, Project
from mustelinet_reconciler.domain.services.node_builder import TeleportNodeBuilder
from mustelinet_reconciler.domain.services.reconciliation_planner import ReconciliationPlanner
from mustelinet_reconciler.domain.services.role_builder import TeleportRoleBuilder
from mustelinet_reconciler.infrastructure.memory import (
    MemoryInstanceRepository,
    MemoryOIDCConnectorRepository,
    MemoryProjectRepository,
    MemoryTeleportNodeRepository,
    MemoryTeleportRoleRepository,
)


class ReconciliationServiceTests(unittest.TestCase):
    def test_reconcile_applies_upserts(self) -> None:
        settings = TeleportSettings()
        openstack_settings = OpenStackSettings()
        nodes = MemoryTeleportNodeRepository()
        roles = MemoryTeleportRoleRepository()
        oidc = MemoryOIDCConnectorRepository()
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
                        addresses=(NetworkAddress("private", "10.0.0.10", 4, "fixed"),),
                    )
                ]
            ),
            nodes=nodes,
            roles=roles,
            oidc=oidc,
            planner=ReconciliationPlanner(
                openstack_settings,
                settings,
                TeleportNodeBuilder(openstack_settings, settings),
                TeleportRoleBuilder(settings),
            ),
            teleport_settings=settings,
        )

        plan = service.reconcile()

        self.assertEqual(1, len(plan.node_upserts))
        self.assertIn("par1:vm1", nodes.nodes)
        self.assertEqual(
            {"mustelinet-project-otterlab-admin", "mustelinet-project-otterlab-member"},
            set(roles.roles),
        )
        self.assertIsNotNone(oidc.mappings)


if __name__ == "__main__":
    unittest.main()
