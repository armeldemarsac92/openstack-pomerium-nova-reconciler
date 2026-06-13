from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from mustelinet_reconciler.config.settings import OpenStackSettings, TeleportSettings
from mustelinet_reconciler.domain.models.openstack import Instance, Project
from mustelinet_reconciler.domain.models.reconciliation_plan import (
    ActionKind,
    ReconciliationAction,
    ReconciliationPlan,
    ResourceKind,
    SkippedInstance,
)
from mustelinet_reconciler.domain.models.teleport import ManagedNode, ManagedRole, OIDCConnectorMappings
from mustelinet_reconciler.domain.services.naming import qualified_hostname, slugify
from mustelinet_reconciler.domain.services.node_builder import TeleportNodeBuilder
from mustelinet_reconciler.domain.services.role_builder import TeleportRoleBuilder


@dataclass(frozen=True, slots=True)
class ReconciliationPlanner:
    openstack_settings: OpenStackSettings
    teleport_settings: TeleportSettings
    node_builder: TeleportNodeBuilder
    role_builder: TeleportRoleBuilder

    def plan(
        self,
        *,
        projects: Sequence[Project],
        instances: Sequence[Instance],
        current_nodes: Sequence[ManagedNode],
        current_roles: Sequence[ManagedRole] = (),
        current_oidc_mappings: OIDCConnectorMappings | None = None,
    ) -> ReconciliationPlan:
        enabled_projects = tuple(project for project in projects if project.enabled)
        desired_nodes, skipped = self._desired_nodes(projects, instances)
        desired_roles = self._desired_roles(enabled_projects)
        desired_oidc_mappings = self.role_builder.build_oidc_mappings(list(enabled_projects))

        actions: list[ReconciliationAction] = []
        actions.extend(self._plan_nodes(desired_nodes, current_nodes))
        actions.extend(self._plan_roles(desired_roles, current_roles))
        actions.extend(self._plan_oidc_mappings(desired_oidc_mappings, current_oidc_mappings))

        return ReconciliationPlan(tuple(actions), skipped)

    def _plan_nodes(
        self,
        desired_nodes: tuple[ManagedNode, ...],
        current_nodes: Sequence[ManagedNode],
    ) -> list[ReconciliationAction]:
        desired_by_id = {node.identity: node for node in desired_nodes}
        current_by_id = {node.identity: node for node in current_nodes}

        actions: list[ReconciliationAction] = []
        for identity, desired_node in sorted(desired_by_id.items()):
            current_node = current_by_id.get(identity)
            if current_node is None:
                actions.append(
                    ReconciliationAction(ActionKind.UPSERT, ResourceKind.NODE, desired_node, "missing")
                )
            elif current_node.fingerprint() != desired_node.fingerprint():
                actions.append(
                    ReconciliationAction(ActionKind.UPSERT, ResourceKind.NODE, desired_node, "drift")
                )

        if self.teleport_settings.delete_stale_nodes:
            for identity, current_node in sorted(current_by_id.items()):
                if identity not in desired_by_id:
                    actions.append(
                        ReconciliationAction(ActionKind.DELETE, ResourceKind.NODE, current_node, "stale")
                    )

        return actions

    def _plan_roles(
        self,
        desired_roles: tuple[ManagedRole, ...],
        current_roles: Sequence[ManagedRole],
    ) -> list[ReconciliationAction]:
        desired_by_id = {role.identity: role for role in desired_roles}
        current_by_id = {role.identity: role for role in current_roles}

        actions: list[ReconciliationAction] = []
        for identity, desired_role in sorted(desired_by_id.items()):
            current_role = current_by_id.get(identity)
            if current_role is None:
                actions.append(
                    ReconciliationAction(ActionKind.UPSERT, ResourceKind.ROLE, desired_role, "missing")
                )
            elif current_role.fingerprint() != desired_role.fingerprint():
                actions.append(
                    ReconciliationAction(ActionKind.UPSERT, ResourceKind.ROLE, desired_role, "drift")
                )

        if self.teleport_settings.delete_stale_roles:
            for identity, current_role in sorted(current_by_id.items()):
                if identity not in desired_by_id:
                    actions.append(
                        ReconciliationAction(ActionKind.DELETE, ResourceKind.ROLE, current_role, "stale")
                    )

        return actions

    def _plan_oidc_mappings(
        self,
        desired: OIDCConnectorMappings,
        current: OIDCConnectorMappings | None,
    ) -> list[ReconciliationAction]:
        if not desired.mappings:
            return []
        if current is not None and current.fingerprint() == desired.fingerprint():
            return []
        return [ReconciliationAction(ActionKind.UPSERT, ResourceKind.OIDC_MAPPINGS, desired, "drift")]

    def _desired_nodes(
        self,
        projects: Sequence[Project],
        instances: Sequence[Instance],
    ) -> tuple[tuple[ManagedNode, ...], tuple[SkippedInstance, ...]]:
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

        names = [slugify(instance.name) for _, instance in candidates]
        colliding_names = {name for name in names if names.count(name) > 1}
        desired = [
            self.node_builder.build(
                project,
                instance,
                hostname=(
                    qualified_hostname(instance.name, project.name, instance.region)
                    if slugify(instance.name) in colliding_names
                    else slugify(instance.name)
                ),
            )
            for project, instance in candidates
        ]

        return tuple(desired), tuple(skipped)

    def _desired_roles(self, projects: Sequence[Project]) -> tuple[ManagedRole, ...]:
        roles: list[ManagedRole] = []
        for project in projects:
            roles.extend(self.role_builder.build_roles(project))
        return tuple(roles)
