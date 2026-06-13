from __future__ import annotations

import unittest

from mustelinet_reconciler.config.settings import TeleportSettings
from mustelinet_reconciler.domain.models.openstack import Instance, NetworkAddress, Project
from mustelinet_reconciler.domain.models.teleport import ManagedNode
from mustelinet_reconciler.domain.services.node_builder import TeleportNodeBuilder
from mustelinet_reconciler.domain.services.reconciliation_planner import ReconciliationPlanner


class ReconciliationPlannerTests(unittest.TestCase):
    def test_plans_upsert_for_missing_active_instance(self) -> None:
        planner = _planner()
        plan = planner.plan(
            projects=[Project(id="p1", name="otterlab")],
            instances=[
                Instance(
                    id="vm1",
                    name="web01",
                    project_id="p1",
                    status="ACTIVE",
                    region="par1",
                    addresses=(NetworkAddress("private", "10.0.0.10", 4, "fixed"),),
                    metadata={"environment": "production"},
                )
            ],
            current_nodes=[],
        )

        self.assertEqual(1, len(plan.upserts))
        node = plan.upserts[0].node
        self.assertEqual("par1:vm1", node.identity)
        self.assertEqual("web01", node.name)
        self.assertEqual("10.0.0.10", node.address)
        self.assertEqual("p1", node.labels["mustelinet.io/project-id"])
        self.assertEqual("production", node.labels["openstack.instance-metadata/environment"])

    def test_plans_delete_for_stale_managed_node(self) -> None:
        stale = ManagedNode(
            name="old01",
            source_id="vm-old",
            project_id="p1",
            project_name="otterlab",
            region="par1",
            labels={"mustelinet.io/managed-by": "openstack-teleport-reconciler"},
        )

        plan = _planner().plan(projects=[], instances=[], current_nodes=[stale])

        self.assertEqual(1, len(plan.deletes))

    def test_can_disable_stale_deletes(self) -> None:
        settings = TeleportSettings(delete_stale_nodes=False)
        planner = ReconciliationPlanner(settings, TeleportNodeBuilder(settings))
        stale = ManagedNode(
            name="old01",
            source_id="vm-old",
            project_id="p1",
            project_name="otterlab",
            region="par1",
            labels={"mustelinet.io/managed-by": "openstack-teleport-reconciler"},
        )

        plan = planner.plan(projects=[], instances=[], current_nodes=[stale])

        self.assertEqual(0, len(plan.deletes))

    def test_skips_instances_without_enabled_active_project(self) -> None:
        plan = _planner().plan(
            projects=[Project(id="p1", name="otterlab", enabled=False)],
            instances=[
                Instance(id="vm1", name="web01", project_id="p1", status="ACTIVE", region="par1"),
                Instance(id="vm2", name="db01", project_id="missing", status="ACTIVE", region="par1"),
                Instance(id="vm3", name="stopped01", project_id="p1", status="SHUTOFF", region="par1"),
            ],
            current_nodes=[],
        )

        self.assertEqual(0, len(plan.actions))
        self.assertEqual(
            ["disabled-project", "missing-project", "disabled-project"],
            [skipped.reason for skipped in plan.skipped],
        )


def _planner() -> ReconciliationPlanner:
    settings = TeleportSettings()
    return ReconciliationPlanner(settings, TeleportNodeBuilder(settings))


if __name__ == "__main__":
    unittest.main()
