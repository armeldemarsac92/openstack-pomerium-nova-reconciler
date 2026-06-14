from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mustelinet_reconciler.domain.models.pomerium import ManagedSSHRoute


class ActionKind(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


class ResourceKind(StrEnum):
    SSH_ROUTE = "ssh_route"


ManagedResource = ManagedSSHRoute


@dataclass(frozen=True, slots=True)
class ReconciliationAction:
    kind: ActionKind
    resource_kind: ResourceKind
    resource: ManagedResource
    reason: str

    @property
    def route(self) -> ManagedSSHRoute:
        if not isinstance(self.resource, ManagedSSHRoute):
            raise TypeError("action resource is not an SSH route")
        return self.resource


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
    def route_upserts(self) -> tuple[ReconciliationAction, ...]:
        return tuple(
            action
            for action in self.actions
            if action.kind == ActionKind.UPSERT and action.resource_kind == ResourceKind.SSH_ROUTE
        )

    @property
    def route_deletes(self) -> tuple[ReconciliationAction, ...]:
        return tuple(
            action
            for action in self.actions
            if action.kind == ActionKind.DELETE and action.resource_kind == ResourceKind.SSH_ROUTE
        )

    @property
    def is_empty(self) -> bool:
        return not self.actions
