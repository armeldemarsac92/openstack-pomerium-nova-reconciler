from __future__ import annotations

from dataclasses import dataclass

from mustelinet_reconciler.application.ports.instance_repository import InstanceRepository
from mustelinet_reconciler.application.ports.oidc_connector_repository import OIDCConnectorRepository
from mustelinet_reconciler.application.ports.project_repository import ProjectRepository
from mustelinet_reconciler.application.ports.teleport_node_repository import TeleportNodeRepository
from mustelinet_reconciler.application.ports.teleport_role_repository import TeleportRoleRepository
from mustelinet_reconciler.config.settings import TeleportSettings
from mustelinet_reconciler.domain.models.reconciliation_plan import (
    ActionKind,
    ReconciliationPlan,
    ResourceKind,
)
from mustelinet_reconciler.domain.services.reconciliation_planner import ReconciliationPlanner


@dataclass(slots=True)
class ReconciliationService:
    projects: ProjectRepository
    instances: InstanceRepository
    nodes: TeleportNodeRepository
    roles: TeleportRoleRepository
    oidc: OIDCConnectorRepository
    planner: ReconciliationPlanner
    teleport_settings: TeleportSettings

    def plan(self) -> ReconciliationPlan:
        return self.planner.plan(
            projects=self.projects.list_projects(),
            instances=self.instances.list_instances(),
            current_nodes=self.nodes.list_managed_nodes(self.teleport_settings.managed_by),
            current_roles=self.roles.list_managed_roles(self.teleport_settings.managed_by),
            current_oidc_mappings=self.oidc.get_managed_mappings(
                self.teleport_settings.oidc_connector_name,
                self.teleport_settings.role_name_prefix,
            ),
        )

    def reconcile(self, *, dry_run: bool = False) -> ReconciliationPlan:
        plan = self.plan()
        if dry_run:
            return plan

        for action in plan.actions:
            if action.resource_kind == ResourceKind.NODE:
                if action.kind == ActionKind.UPSERT:
                    self.nodes.upsert_node(action.node)
                elif action.kind == ActionKind.DELETE:
                    self.nodes.delete_node(action.node)
            elif action.resource_kind == ResourceKind.ROLE:
                if action.kind == ActionKind.UPSERT:
                    self.roles.upsert_role(action.role)
                elif action.kind == ActionKind.DELETE:
                    self.roles.delete_role(action.role)
            elif action.resource_kind == ResourceKind.OIDC_MAPPINGS:
                if action.kind == ActionKind.UPSERT:
                    self.oidc.upsert_managed_mappings(
                        action.oidc_mappings,
                        self.teleport_settings.role_name_prefix,
                    )

        return plan
