from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from mustelinet_reconciler.config.settings import TeleportSettings
from mustelinet_reconciler.domain.models.openstack import Instance, Project
from mustelinet_reconciler.domain.models.reconciliation_plan import (
    ActionKind,
    ReconciliationAction,
    ReconciliationPlan,
    SkippedInstance,
)
from mustelinet_reconciler.domain.models.teleport import ManagedNode
from mustelinet_reconciler.domain.services.node_builder import TeleportNodeBuilder


@dataclass(frozen=True, slots=True)
class ReconciliationPlanner:
    settings: TeleportSettings
    node_builder: TeleportNodeBuilder

    def plan(
        self,
        *,
        projects: Sequence[Project],
        instances: Sequence[Instance],
        current_nodes: Sequence[ManagedNode],
    ) -> ReconciliationPlan:
        desired, skipped = self._desired_nodes(projects, instances)

        desired_by_id = {node.identity: node for node in desired}
        current_by_id = {node.identity: node for node in current_nodes}

        actions: list[ReconciliationAction] = []
        for identity, desired_node in sorted(desired_by_id.items()):
            current_node = current_by_id.get(identity)
            if current_node is None:
                actions.append(ReconciliationAction(ActionKind.UPSERT, desired_node, "missing"))
            elif current_node.fingerprint() != desired_node.fingerprint():
                actions.append(ReconciliationAction(ActionKind.UPSERT, desired_node, "drift"))

        if self.settings.delete_stale_nodes:
            for identity, current_node in sorted(current_by_id.items()):
                if identity not in desired_by_id:
                    actions.append(ReconciliationAction(ActionKind.DELETE, current_node, "stale"))

        return ReconciliationPlan(tuple(actions), skipped)

    def _desired_nodes(
        self,
        projects: Sequence[Project],
        instances: Sequence[Instance],
    ) -> tuple[tuple[ManagedNode, ...], tuple[SkippedInstance, ...]]:
        project_by_id = {project.id: project for project in projects}
        desired: list[ManagedNode] = []
        skipped: list[SkippedInstance] = []

        for instance in instances:
            project = project_by_id.get(instance.project_id)
            if project is None:
                skipped.append(SkippedInstance(instance.id, instance.project_id, "missing-project"))
                continue
            if not project.enabled:
                skipped.append(SkippedInstance(instance.id, instance.project_id, "disabled-project"))
                continue
            if instance.status not in self.settings.sync_statuses:
                skipped.append(
                    SkippedInstance(
                        instance.id,
                        instance.project_id,
                        f"unsupported-status:{instance.status}",
                    )
                )
                continue
            desired.append(self.node_builder.build(project, instance))

        return tuple(desired), tuple(skipped)
