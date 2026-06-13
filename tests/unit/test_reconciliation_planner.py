from __future__ import annotations

import unittest

from mustelinet_reconciler.config.settings import OpenStackSettings, TeleportSettings
from mustelinet_reconciler.domain.models.openstack import Instance, NetworkAddress, Project
from mustelinet_reconciler.domain.models.reconciliation_plan import ResourceKind
from mustelinet_reconciler.domain.models.teleport import (
    ManagedNode,
    ManagedRole,
    OIDCConnectorMappings,
    OIDCMapping,
)
from mustelinet_reconciler.domain.services.node_builder import TeleportNodeBuilder
from mustelinet_reconciler.domain.services.reconciliation_planner import ReconciliationPlanner
from mustelinet_reconciler.domain.services.role_builder import TeleportRoleBuilder


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

        self.assertEqual(1, len(plan.node_upserts))
        node = plan.node_upserts[0].node
        self.assertEqual("par1:vm1", node.identity)
        self.assertEqual("web01", node.hostname)
        self.assertEqual("69dadb62-67d4-57b8-8760-2e36655d7f6d", node.name)
        self.assertEqual("10.0.0.10", node.address)
        self.assertEqual("10.0.0.10:22", node.addr)
        self.assertEqual("p1", node.labels["mustelinet.io/project-id"])
        self.assertEqual("production", node.labels["openstack.instance-metadata/environment"])

    def test_plans_roles_and_oidc_mappings_for_enabled_projects(self) -> None:
        plan = _planner().plan(
            projects=[Project(id="p1", name="Otter Lab")],
            instances=[],
            current_nodes=[],
        )

        self.assertEqual(
            ["mustelinet-project-otter-lab-admin", "mustelinet-project-otter-lab-member"],
            sorted(action.role.name for action in plan.role_upserts),
        )
        oidc_actions = [
            action for action in plan.upserts if action.resource_kind == ResourceKind.OIDC_MAPPINGS
        ]
        self.assertEqual(1, len(oidc_actions))
        self.assertEqual(
            ["project-otter-lab-admin", "project-otter-lab-member"],
            [mapping.value for mapping in oidc_actions[0].oidc_mappings.mappings],
        )

    def test_qualifies_colliding_hostnames(self) -> None:
        plan = _planner().plan(
            projects=[
                Project(id="p1", name="Otter Lab"),
                Project(id="p2", name="Seal Lab"),
            ],
            instances=[
                Instance(
                    id="vm1",
                    name="web01",
                    project_id="p1",
                    status="ACTIVE",
                    region="par1",
                    addresses=(NetworkAddress("private", "10.0.0.10", 4, "fixed"),),
                ),
                Instance(
                    id="vm2",
                    name="web01",
                    project_id="p2",
                    status="ACTIVE",
                    region="par1",
                    addresses=(NetworkAddress("private", "10.0.0.11", 4, "fixed"),),
                ),
            ],
            current_nodes=[],
        )

        self.assertEqual(
            ["web01--otter-lab--par1", "web01--seal-lab--par1"],
            sorted(action.node.hostname for action in plan.node_upserts),
        )

    def test_plans_delete_for_stale_managed_node(self) -> None:
        stale = ManagedNode(
            name="old01",
            hostname="old01",
            source_id="vm-old",
            project_id="p1",
            project_name="otterlab",
            region="par1",
            labels={"mustelinet.io/managed-by": "openstack-teleport-reconciler"},
        )

        plan = _planner().plan(projects=[], instances=[], current_nodes=[stale])

        self.assertEqual(1, len(plan.node_deletes))

    def test_can_disable_stale_deletes(self) -> None:
        settings = TeleportSettings(delete_stale_nodes=False)
        openstack_settings = OpenStackSettings()
        planner = ReconciliationPlanner(
            openstack_settings,
            settings,
            TeleportNodeBuilder(openstack_settings, settings),
            TeleportRoleBuilder(settings),
        )
        stale = ManagedNode(
            name="old01",
            hostname="old01",
            source_id="vm-old",
            project_id="p1",
            project_name="otterlab",
            region="par1",
            labels={"mustelinet.io/managed-by": "openstack-teleport-reconciler"},
        )

        plan = planner.plan(projects=[], instances=[], current_nodes=[stale])

        self.assertEqual(0, len(plan.node_deletes))

    def test_deletes_stale_project_roles(self) -> None:
        stale = ManagedRole(
            name="mustelinet-project-old-member",
            project_id="p-old",
            project_name="old",
            project_role="member",
            logins=("ubuntu",),
            node_labels={"mustelinet.io/project-id": "p-old"},
            managed_by="openstack-teleport-reconciler",
        )

        plan = _planner().plan(
            projects=[],
            instances=[],
            current_nodes=[],
            current_roles=[stale],
        )

        self.assertEqual(1, len(plan.role_deletes))

    def test_skips_active_instances_without_selected_address(self) -> None:
        plan = _planner().plan(
            projects=[Project(id="p1", name="otterlab")],
            instances=[
                Instance(
                    id="vm1",
                    name="web01",
                    project_id="p1",
                    status="ACTIVE",
                    region="par1",
                    addresses=(NetworkAddress("private", "fd00::1", 6, "fixed"),),
                ),
            ],
            current_nodes=[],
        )

        self.assertEqual(0, len(plan.node_upserts))
        self.assertEqual(["missing-ssh-address"], [skipped.reason for skipped in plan.skipped])

    def test_does_not_upsert_oidc_when_managed_mappings_match(self) -> None:
        current = OIDCConnectorMappings(
            name="authentik",
            mappings=(
                OIDCMapping(
                    claim="groups",
                    value="project-otterlab-admin",
                    roles=("mustelinet-project-otterlab-admin",),
                ),
                OIDCMapping(
                    claim="groups",
                    value="project-otterlab-member",
                    roles=("mustelinet-project-otterlab-member",),
                ),
            ),
        )

        plan = _planner().plan(
            projects=[Project(id="p1", name="otterlab")],
            instances=[],
            current_nodes=[],
            current_oidc_mappings=current,
        )

        self.assertEqual(
            [],
            [action for action in plan.upserts if action.resource_kind == ResourceKind.OIDC_MAPPINGS],
        )

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
    openstack_settings = OpenStackSettings()
    teleport_settings = TeleportSettings()
    return ReconciliationPlanner(
        openstack_settings,
        teleport_settings,
        TeleportNodeBuilder(openstack_settings, teleport_settings),
        TeleportRoleBuilder(teleport_settings),
    )


if __name__ == "__main__":
    unittest.main()
