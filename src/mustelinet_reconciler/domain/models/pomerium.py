from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any
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
class ManagedSSHRoute:
    name: str
    route_name: str
    source_id: str
    project_id: str
    project_name: str
    region: str
    group_claim: str
    allowed_groups: tuple[str, ...]
    forbidden_logins: tuple[str, ...]
    timeout: str | None = None
    idle_timeout: str | None = None
    labels: Mapping[str, str] = field(default_factory=dict)
    address: str | None = None
    port: int = 22

    def __post_init__(self) -> None:
        object.__setattr__(self, "labels", freeze_mapping(stringify_labels(self.labels)))
        object.__setattr__(self, "allowed_groups", tuple(sorted(set(self.allowed_groups))))
        object.__setattr__(self, "forbidden_logins", tuple(sorted(set(self.forbidden_logins))))
        object.__setattr__(self, "group_claim", self.group_claim.strip().strip("/"))
        object.__setattr__(self, "timeout", _clean_optional_duration(self.timeout))
        object.__setattr__(self, "idle_timeout", _clean_optional_duration(self.idle_timeout))

    @property
    def identity(self) -> str:
        return f"{self.region}:{self.source_id}"

    @property
    def managed_by(self) -> str | None:
        return self.labels.get("mustelinet.io/managed-by")

    @property
    def from_url(self) -> str:
        return f"ssh://{self.route_name}"

    @property
    def to_url(self) -> str | None:
        if self.address is None:
            return None
        host = self.address
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"ssh://{host}:{self.port}"

    @property
    def policy(self) -> tuple[Mapping[str, Any], ...]:
        rules: list[Mapping[str, Any]] = []
        username_condition = self._forbidden_username_condition()
        if username_condition is not None:
            rules.append({"deny": {"and": [username_condition]}})
        for group in self.allowed_groups:
            rules.append({"allow": {"and": [{f"claim/{self.group_claim}": group}]}})
        return tuple(freeze_mapping(rule) for rule in rules)

    def fingerprint(self) -> tuple[Any, ...]:
        return (
            self.name,
            self.route_name,
            self.source_id,
            self.project_id,
            self.project_name,
            self.region,
            self.group_claim,
            self.allowed_groups,
            self.forbidden_logins,
            self.timeout,
            self.idle_timeout,
            tuple(sorted(self.labels.items())),
            self.address,
            self.port,
        )

    def _forbidden_username_condition(self) -> Mapping[str, Any] | None:
        if not self.forbidden_logins:
            return None
        if len(self.forbidden_logins) == 1:
            return {"ssh_username": {"is": self.forbidden_logins[0]}}
        return {"ssh_username": {"in": list(self.forbidden_logins)}}


def stable_route_uuid(identity: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"mustelinet:openstack:pomerium-ssh:{identity}"))


def _clean_optional_duration(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized
