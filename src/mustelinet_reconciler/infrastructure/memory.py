from __future__ import annotations

from typing import Sequence

from mustelinet_reconciler.domain.models.openstack import Instance, Project
from mustelinet_reconciler.domain.models.teleport import ManagedNode


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
