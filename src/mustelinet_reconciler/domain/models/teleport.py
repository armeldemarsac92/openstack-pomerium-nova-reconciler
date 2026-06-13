from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5


def freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


def stringify_labels(value: Mapping[str, Any]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for key, item in value.items():
        if item is None:
            continue
        labels[str(key)] = str(item)
    return labels


@dataclass(frozen=True, slots=True)
class ManagedNode:
    name: str
    hostname: str
    source_id: str
    project_id: str
    project_name: str
    region: str
    labels: Mapping[str, str] = field(default_factory=dict)
    logins: tuple[str, ...] = ("ubuntu",)
    address: str | None = None
    port: int = 22

    def __post_init__(self) -> None:
        object.__setattr__(self, "labels", freeze_mapping(stringify_labels(self.labels)))
        object.__setattr__(self, "logins", tuple(self.logins))

    @property
    def identity(self) -> str:
        return f"{self.region}:{self.source_id}"

    @property
    def managed_by(self) -> str | None:
        return self.labels.get("mustelinet.io/managed-by")

    def fingerprint(self) -> tuple[Any, ...]:
        return (
            self.name,
            self.hostname,
            self.source_id,
            self.project_id,
            self.project_name,
            self.region,
            tuple(sorted(self.labels.items())),
            self.logins,
            self.address,
            self.port,
        )

    @property
    def addr(self) -> str | None:
        if self.address is None:
            return None
        return f"{self.address}:{self.port}"


@dataclass(frozen=True, slots=True)
class ManagedRole:
    name: str
    project_id: str
    project_name: str
    project_role: str
    logins: tuple[str, ...]
    node_labels: Mapping[str, str]
    managed_by: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_role", self.project_role.lower())
        object.__setattr__(self, "logins", tuple(self.logins))
        object.__setattr__(self, "node_labels", freeze_mapping(stringify_labels(self.node_labels)))

    @property
    def identity(self) -> str:
        return self.name

    def fingerprint(self) -> tuple[Any, ...]:
        return (
            self.name,
            self.project_id,
            self.project_name,
            self.project_role,
            self.logins,
            tuple(sorted(self.node_labels.items())),
            self.managed_by,
        )


@dataclass(frozen=True, slots=True)
class OIDCMapping:
    claim: str
    value: str
    roles: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "roles", tuple(self.roles))

    @property
    def identity(self) -> tuple[str, str]:
        return (self.claim, self.value)

    def fingerprint(self) -> tuple[str, str, tuple[str, ...]]:
        return (self.claim, self.value, tuple(sorted(self.roles)))


@dataclass(frozen=True, slots=True)
class OIDCConnectorMappings:
    name: str
    mappings: tuple[OIDCMapping, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "mappings", tuple(self.mappings))

    @property
    def identity(self) -> str:
        return self.name

    def fingerprint(self) -> tuple[Any, ...]:
        return (self.name, tuple(sorted(mapping.fingerprint() for mapping in self.mappings)))


def stable_node_uuid(identity: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"mustelinet:openstack:{identity}"))
