from __future__ import annotations

from typing import Sequence

from mustelinet_reconciler.domain.models.openstack import Instance, Project
from mustelinet_reconciler.domain.models.teleport import (
    ManagedNode,
    ManagedRole,
    OIDCConnectorMappings,
)


class MemoryProjectRepository:
    def __init__(self, projects: Sequence[Project]) -> None:
        self._projects = tuple(projects)

    def list_projects(self) -> Sequence[Project]:
        return self._projects


class MemoryInstanceRepository:
    def __init__(self, instances: Sequence[Instance]) -> None:
        self._instances = tuple(instances)

    def list_instances(self) -> Sequence[Instance]:
        return self._instances


class MemoryTeleportNodeRepository:
    def __init__(self, nodes: Sequence[ManagedNode] = ()) -> None:
        self.nodes = {node.identity: node for node in nodes}

    def list_managed_nodes(self, managed_by: str) -> Sequence[ManagedNode]:
        return tuple(node for node in self.nodes.values() if node.managed_by == managed_by)

    def upsert_node(self, node: ManagedNode) -> None:
        self.nodes[node.identity] = node

    def delete_node(self, node: ManagedNode) -> None:
        self.nodes.pop(node.identity, None)


class MemoryTeleportRoleRepository:
    def __init__(self, roles: Sequence[ManagedRole] = ()) -> None:
        self.roles = {role.identity: role for role in roles}

    def list_managed_roles(self, managed_by: str) -> Sequence[ManagedRole]:
        return tuple(role for role in self.roles.values() if role.managed_by == managed_by)

    def upsert_role(self, role: ManagedRole) -> None:
        self.roles[role.identity] = role

    def delete_role(self, role: ManagedRole) -> None:
        self.roles.pop(role.identity, None)


class MemoryOIDCConnectorRepository:
    def __init__(self, mappings: OIDCConnectorMappings | None = None) -> None:
        self.mappings = mappings

    def get_managed_mappings(
        self,
        connector_name: str,
        managed_role_prefix: str,
    ) -> OIDCConnectorMappings | None:
        if self.mappings is None or self.mappings.name != connector_name:
            return None
        return _filter_managed_mappings(self.mappings, managed_role_prefix)

    def upsert_managed_mappings(
        self,
        mappings: OIDCConnectorMappings,
        managed_role_prefix: str,
    ) -> None:
        existing = self.mappings
        if existing is None or existing.name != mappings.name:
            self.mappings = mappings
            return

        unmanaged = tuple(
            mapping
            for mapping in existing.mappings
            if not all(role.startswith(managed_role_prefix) for role in mapping.roles)
        )
        self.mappings = OIDCConnectorMappings(mappings.name, unmanaged + mappings.mappings)


def _filter_managed_mappings(
    mappings: OIDCConnectorMappings,
    managed_role_prefix: str,
) -> OIDCConnectorMappings:
    return OIDCConnectorMappings(
        mappings.name,
        tuple(
            mapping
            for mapping in mappings.mappings
            if all(role.startswith(managed_role_prefix) for role in mapping.roles)
        ),
    )
