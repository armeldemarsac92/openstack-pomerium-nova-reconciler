from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


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
            self.source_id,
            self.project_id,
            self.project_name,
            self.region,
            tuple(sorted(self.labels.items())),
            self.logins,
            self.address,
            self.port,
        )
