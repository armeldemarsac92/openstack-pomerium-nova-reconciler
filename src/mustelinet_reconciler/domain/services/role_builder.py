from __future__ import annotations

from dataclasses import dataclass

from mustelinet_reconciler.config.settings import TeleportSettings
from mustelinet_reconciler.domain.models.openstack import Project
from mustelinet_reconciler.domain.models.teleport import ManagedRole, OIDCConnectorMappings, OIDCMapping
from mustelinet_reconciler.domain.services.naming import project_group_name, project_role_name

PROJECT_ROLES = ("admin", "member")


@dataclass(frozen=True, slots=True)
class TeleportRoleBuilder:
    settings: TeleportSettings

    def build_roles(self, project: Project) -> tuple[ManagedRole, ...]:
        return tuple(self._build_role(project, role) for role in PROJECT_ROLES)

    def build_oidc_mappings(self, projects: list[Project]) -> OIDCConnectorMappings:
        mappings: list[OIDCMapping] = []
        for project in sorted(projects, key=lambda item: item.name):
            for role in PROJECT_ROLES:
                mappings.append(
                    OIDCMapping(
                        claim="groups",
                        value=project_group_name(project.name, role),
                        roles=(project_role_name(project.name, role),),
                    )
                )
        return OIDCConnectorMappings(self.settings.oidc_connector_name, tuple(mappings))

    def _build_role(self, project: Project, role: str) -> ManagedRole:
        return ManagedRole(
            name=project_role_name(project.name, role),
            project_id=project.id,
            project_name=project.name,
            project_role=role,
            logins=self.settings.default_logins,
            node_labels={"mustelinet.io/project-id": project.id},
            managed_by=self.settings.managed_by,
        )
