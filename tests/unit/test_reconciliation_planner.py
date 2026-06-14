from __future__ import annotations

import unittest

from mustelinet_reconciler.config.settings import OpenStackSettings, PomeriumSettings
from mustelinet_reconciler.domain.models.openstack import Instance, NetworkAddress, Project
from mustelinet_reconciler.domain.models.pomerium import ManagedSSHRoute
from mustelinet_reconciler.domain.services.reconciliation_planner import ReconciliationPlanner
from mustelinet_reconciler.domain.services.route_builder import PomeriumRouteBuilder


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
            current_routes=[],
        )

        self.assertEqual(1, len(plan.route_upserts))
        route = plan.route_upserts[0].route
        self.assertEqual("par1:vm1", route.identity)
        self.assertEqual("web01-otterlab", route.route_name)
        self.assertEqual("ssh://web01-otterlab", route.from_url)
        self.assertEqual("10.0.0.10", route.address)
        self.assertEqual("ssh://10.0.0.10:22", route.to_url)
        self.assertEqual("p1", route.labels["mustelinet.io/project-id"])
        self.assertEqual("production", route.labels["openstack.instance-metadata/environment"])
        self.assertEqual(
            ("openstack:otterlab:admin", "openstack:otterlab:member"),
            route.allowed_groups,
        )

    def test_generates_pomerium_policy_from_project_groups_and_logins(self) -> None:
        plan = _planner().plan(
            projects=[Project(id="p1", name="Otter Lab")],
            instances=[
                Instance(
                    id="vm1",
                    name="web01",
                    project_id="p1",
                    status="ACTIVE",
                    region="par1",
                    addresses=(NetworkAddress("private", "10.0.0.10", 4, "fixed"),),
                )
            ],
            current_routes=[],
        )

        policy = plan.route_upserts[0].route.policy

        self.assertEqual(
            (
                {
                    "deny": {
                        "and": [
                            {"ssh_username": {"is": "root"}},
                        ]
                    }
                },
                {
                    "allow": {
                        "and": [
                            {"claim/groups": "openstack:otter-lab:admin"},
                        ]
                    }
                },
                {
                    "allow": {
                        "and": [
                            {"claim/groups": "openstack:otter-lab:member"},
                        ]
                    }
                },
            ),
            policy,
        )

    def test_route_names_always_include_project_name(self) -> None:
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
            current_routes=[],
        )

        self.assertEqual(
            ["web01-otter-lab", "web01-seal-lab"],
            sorted(action.route.route_name for action in plan.route_upserts),
        )

    def test_plans_delete_for_stale_managed_route(self) -> None:
        stale = _route()

        plan = _planner().plan(projects=[], instances=[], current_routes=[stale])

        self.assertEqual(1, len(plan.route_deletes))

    def test_can_disable_stale_deletes(self) -> None:
        settings = PomeriumSettings(delete_stale_routes=False)
        openstack_settings = OpenStackSettings()
        planner = ReconciliationPlanner(
            openstack_settings,
            settings,
            PomeriumRouteBuilder(openstack_settings, settings),
        )

        plan = planner.plan(projects=[], instances=[], current_routes=[_route()])

        self.assertEqual(0, len(plan.route_deletes))

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
            current_routes=[],
        )

        self.assertEqual(0, len(plan.route_upserts))
        self.assertEqual(["missing-ssh-address"], [skipped.reason for skipped in plan.skipped])

    def test_skips_instances_without_enabled_active_project(self) -> None:
        plan = _planner().plan(
            projects=[Project(id="p1", name="otterlab", enabled=False)],
            instances=[
                Instance(id="vm1", name="web01", project_id="p1", status="ACTIVE", region="par1"),
                Instance(
                    id="vm2",
                    name="db01",
                    project_id="missing",
                    status="ACTIVE",
                    region="par1",
                ),
                Instance(
                    id="vm3",
                    name="stopped01",
                    project_id="p1",
                    status="SHUTOFF",
                    region="par1",
                ),
            ],
            current_routes=[],
        )

        self.assertEqual(0, len(plan.actions))
        self.assertEqual(
            ["disabled-project", "missing-project", "disabled-project"],
            [skipped.reason for skipped in plan.skipped],
        )


def _planner() -> ReconciliationPlanner:
    openstack_settings = OpenStackSettings()
    pomerium_settings = PomeriumSettings()
    return ReconciliationPlanner(
        openstack_settings,
        pomerium_settings,
        PomeriumRouteBuilder(openstack_settings, pomerium_settings),
    )


def _route() -> ManagedSSHRoute:
    return ManagedSSHRoute(
        name="old01",
        route_name="old01",
        source_id="vm-old",
        project_id="p1",
        project_name="otterlab",
        region="par1",
        group_claim="groups",
        allowed_groups=("openstack:otterlab:member",),
        forbidden_logins=("root",),
        labels={"mustelinet.io/managed-by": "openstack-pomerium-nova-reconciler"},
        address="10.0.0.10",
    )


if __name__ == "__main__":
    unittest.main()
