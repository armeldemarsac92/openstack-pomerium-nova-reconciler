from __future__ import annotations

from typing import Sequence

from mustelinet_reconciler.domain.models.openstack import Instance, Project
from mustelinet_reconciler.domain.models.pomerium import ManagedSSHRoute


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


class MemoryPomeriumRouteRepository:
    def __init__(self, routes: Sequence[ManagedSSHRoute] = ()) -> None:
        self.routes = {route.identity: route for route in routes}

    def list_managed_routes(self, managed_by: str) -> Sequence[ManagedSSHRoute]:
        return tuple(route for route in self.routes.values() if route.managed_by == managed_by)

    def upsert_route(self, route: ManagedSSHRoute) -> None:
        self.routes[route.identity] = route

    def delete_route(self, route: ManagedSSHRoute) -> None:
        self.routes.pop(route.identity, None)
