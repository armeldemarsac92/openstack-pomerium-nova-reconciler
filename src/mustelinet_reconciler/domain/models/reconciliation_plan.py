from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mustelinet_reconciler.domain.models.teleport import ManagedNode, ManagedRole, OIDCConnectorMappings


class ActionKind(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


class ResourceKind(StrEnum):
    NODE = "node"
    ROLE = "role"
    OIDC_MAPPINGS = "oidc_mappings"


ManagedResource = ManagedNode | ManagedRole | OIDCConnectorMappings


@dataclass(frozen=True, slots=True)
class ReconciliationAction:
    kind: ActionKind
    resource_kind: ResourceKind
    resource: ManagedResource
    reason: str

    @property
    def node(self) -> ManagedNode:
        if not isinstance(self.resource, ManagedNode):
            raise TypeError("action resource is not a node")
        return self.resource

    @property
    def role(self) -> ManagedRole:
        if not isinstance(self.resource, ManagedRole):
            raise TypeError("action resource is not a role")
        return self.resource

    @property
    def oidc_mappings(self) -> OIDCConnectorMappings:
        if not isinstance(self.resource, OIDCConnectorMappings):
            raise TypeError("action resource is not OIDC mappings")
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
    def node_upserts(self) -> tuple[ReconciliationAction, ...]:
        return tuple(
            action
            for action in self.actions
            if action.kind == ActionKind.UPSERT and action.resource_kind == ResourceKind.NODE
        )

    @property
    def node_deletes(self) -> tuple[ReconciliationAction, ...]:
        return tuple(
            action
            for action in self.actions
            if action.kind == ActionKind.DELETE and action.resource_kind == ResourceKind.NODE
        )

    @property
    def role_upserts(self) -> tuple[ReconciliationAction, ...]:
        return tuple(
            action
            for action in self.actions
            if action.kind == ActionKind.UPSERT and action.resource_kind == ResourceKind.ROLE
        )

    @property
    def role_deletes(self) -> tuple[ReconciliationAction, ...]:
        return tuple(
            action
            for action in self.actions
            if action.kind == ActionKind.DELETE and action.resource_kind == ResourceKind.ROLE
        )

    @property
    def is_empty(self) -> bool:
        return not self.actions
