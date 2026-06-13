from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mustelinet_reconciler.domain.models.teleport import ManagedNode


class ActionKind(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class ReconciliationAction:
    kind: ActionKind
    node: ManagedNode
    reason: str


@dataclass(frozen=True, slots=True)
class SkippedInstance:
    instance_id: str
    project_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class ReconciliationPlan:
    actions: tuple[ReconciliationAction, ...]
    skipped: tuple[SkippedInstance, ...]

    @property
    def upserts(self) -> tuple[ReconciliationAction, ...]:
        return tuple(action for action in self.actions if action.kind == ActionKind.UPSERT)

    @property
    def deletes(self) -> tuple[ReconciliationAction, ...]:
        return tuple(action for action in self.actions if action.kind == ActionKind.DELETE)

    @property
    def is_empty(self) -> bool:
        return not self.actions
