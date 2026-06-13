from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


def freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True, slots=True)
class Project:
    id: str
    name: str
    domain_id: str = ""
    enabled: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class NetworkAddress:
    network: str
    address: str
    family: int | None = None
    type: str | None = None

    @property
    def is_fixed(self) -> bool:
        return self.type in (None, "", "fixed")


@dataclass(frozen=True, slots=True)
class Instance:
    id: str
    name: str
    project_id: str
    status: str
    region: str
    availability_zone: str = ""
    addresses: tuple[NetworkAddress, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", self.status.upper())
        object.__setattr__(self, "addresses", tuple(self.addresses))
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata))

    def preferred_ssh_address(self, address_family: str = "ipv4") -> str | None:
        fixed = [address for address in self.addresses if address.is_fixed]
        ipv4 = [address for address in fixed if address.family == 4]
        ipv6 = [address for address in fixed if address.family == 6]

        if address_family == "ipv4":
            selected = ipv4
        elif address_family == "ipv6":
            selected = ipv6
        else:
            selected = ipv4 or ipv6 or fixed or list(self.addresses)

        if not selected:
            return None
        return selected[0].address
