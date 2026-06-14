from __future__ import annotations

from dataclasses import dataclass

from mustelinet_reconciler.application.ports.instance_repository import InstanceRepository
from mustelinet_reconciler.application.ports.pomerium_route_repository import PomeriumRouteRepository
from mustelinet_reconciler.application.ports.project_repository import ProjectRepository
from mustelinet_reconciler.config.settings import PomeriumSettings
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
    routes: PomeriumRouteRepository
    planner: ReconciliationPlanner
    pomerium_settings: PomeriumSettings

    def plan(self) -> ReconciliationPlan:
        return self.planner.plan(
            projects=self.projects.list_projects(),
            instances=self.instances.list_instances(),
            current_routes=self.routes.list_managed_routes(self.pomerium_settings.managed_by),
        )

    def reconcile(self, *, dry_run: bool = False) -> ReconciliationPlan:
        plan = self.plan()
        if dry_run:
            return plan

        for action in plan.actions:
            if action.resource_kind == ResourceKind.SSH_ROUTE:
                if action.kind == ActionKind.UPSERT:
                    self.routes.upsert_route(action.route)
                elif action.kind == ActionKind.DELETE:
                    self.routes.delete_route(action.route)

        return plan
