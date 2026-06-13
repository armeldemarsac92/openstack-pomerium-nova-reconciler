from __future__ import annotations

from dataclasses import dataclass

from mustelinet_reconciler.application.ports.instance_repository import InstanceRepository
from mustelinet_reconciler.application.ports.project_repository import ProjectRepository
from mustelinet_reconciler.application.ports.teleport_node_repository import TeleportNodeRepository
from mustelinet_reconciler.config.settings import TeleportSettings
from mustelinet_reconciler.domain.models.reconciliation_plan import ActionKind, ReconciliationPlan
from mustelinet_reconciler.domain.services.reconciliation_planner import ReconciliationPlanner


@dataclass(slots=True)
class ReconciliationService:
    projects: ProjectRepository
    instances: InstanceRepository
    nodes: TeleportNodeRepository
    planner: ReconciliationPlanner
    teleport_settings: TeleportSettings

    def plan(self) -> ReconciliationPlan:
        return self.planner.plan(
            projects=self.projects.list_projects(),
            instances=self.instances.list_instances(),
            current_nodes=self.nodes.list_managed_nodes(self.teleport_settings.managed_by),
        )

    def reconcile(self, *, dry_run: bool = False) -> ReconciliationPlan:
        plan = self.plan()
        if dry_run:
            return plan

        for action in plan.actions:
            if action.kind == ActionKind.UPSERT:
                self.nodes.upsert_node(action.node)
            elif action.kind == ActionKind.DELETE:
                self.nodes.delete_node(action.node)

        return plan
