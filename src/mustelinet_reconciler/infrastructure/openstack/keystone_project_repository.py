from __future__ import annotations

from typing import Any, Sequence

from mustelinet_reconciler.domain.models.openstack import Project


class KeystoneProjectRepository:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def list_projects(self) -> Sequence[Project]:
        projects = self._connection.identity.projects()
        return tuple(_project_from_resource(project) for project in projects)


def _project_from_resource(resource: Any) -> Project:
    return Project(
        id=str(resource.id),
        name=str(resource.name),
        domain_id=str(getattr(resource, "domain_id", "")),
        enabled=bool(getattr(resource, "is_enabled", getattr(resource, "enabled", True))),
        metadata=dict(getattr(resource, "extra", {}) or {}),
    )
