from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from mustelinet_reconciler.config.settings import OpenStackSettings, PomeriumSettings
from mustelinet_reconciler.domain.models.openstack import Instance, Project
from mustelinet_reconciler.domain.models.reconciliation_plan import (
    ActionKind,
    ReconciliationAction,
    ReconciliationPlan,
    ResourceKind,
    SkippedInstance,
)
from mustelinet_reconciler.domain.models.pomerium import ManagedSSHRoute
from mustelinet_reconciler.domain.services.naming import project_route_name
from mustelinet_reconciler.domain.services.route_builder import PomeriumRouteBuilder


@dataclass(frozen=True, slots=True)
class ReconciliationPlanner:
    openstack_settings: OpenStackSettings
    pomerium_settings: PomeriumSettings
    route_builder: PomeriumRouteBuilder

    def plan(
        self,
        *,
        projects: Sequence[Project],
        instances: Sequence[Instance],
        current_routes: Sequence[ManagedSSHRoute],
    ) -> ReconciliationPlan:
        desired_routes, skipped = self._desired_routes(projects, instances)

        actions: list[ReconciliationAction] = []
        actions.extend(self._plan_routes(desired_routes, current_routes))

        return ReconciliationPlan(tuple(actions), skipped)

    def _plan_routes(
        self,
        desired_routes: tuple[ManagedSSHRoute, ...],
        current_routes: Sequence[ManagedSSHRoute],
    ) -> list[ReconciliationAction]:
        desired_by_id = {route.identity: route for route in desired_routes}
        current_by_id = {route.identity: route for route in current_routes}

        actions: list[ReconciliationAction] = []
        for identity, desired_route in sorted(desired_by_id.items()):
            current_route = current_by_id.get(identity)
            if current_route is None:
                actions.append(
                    ReconciliationAction(
                        ActionKind.UPSERT,
                        ResourceKind.SSH_ROUTE,
                        desired_route,
                        "missing",
                    )
                )
            elif current_route.fingerprint() != desired_route.fingerprint():
                actions.append(
                    ReconciliationAction(
                        ActionKind.UPSERT,
                        ResourceKind.SSH_ROUTE,
                        desired_route,
                        "drift",
                    )
                )

        if self.pomerium_settings.delete_stale_routes:
            for identity, current_route in sorted(current_by_id.items()):
                if identity not in desired_by_id:
                    actions.append(
                        ReconciliationAction(
                            ActionKind.DELETE,
                            ResourceKind.SSH_ROUTE,
                            current_route,
                            "stale",
                        )
                    )

        return actions

    def _desired_routes(
        self,
        projects: Sequence[Project],
        instances: Sequence[Instance],
    ) -> tuple[tuple[ManagedSSHRoute, ...], tuple[SkippedInstance, ...]]:
        project_by_id = {project.id: project for project in projects}
        candidates: list[tuple[Project, Instance]] = []
        skipped: list[SkippedInstance] = []

        for instance in instances:
            project = project_by_id.get(instance.project_id)
            if project is None:
                skipped.append(SkippedInstance(instance.id, instance.project_id, "missing-project"))
                continue
            if not project.enabled:
                skipped.append(SkippedInstance(instance.id, instance.project_id, "disabled-project"))
                continue
            if instance.status not in self.openstack_settings.sync_statuses:
                skipped.append(
                    SkippedInstance(
                        instance.id,
                        instance.project_id,
                        f"unsupported-status:{instance.status}",
                    )
                )
                continue
            if instance.preferred_ssh_address(self.openstack_settings.address_family) is None:
                skipped.append(SkippedInstance(instance.id, instance.project_id, "missing-ssh-address"))
                continue
            candidates.append((project, instance))

        desired = [
            self.route_builder.build(
                project,
                instance,
                route_name=project_route_name(instance.name, project.name),
            )
            for project, instance in candidates
        ]

        return tuple(desired), tuple(skipped)
