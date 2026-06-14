from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from mustelinet_reconciler.domain.models.openstack import Instance, NetworkAddress, Project


class SnapshotProjectRepository:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def list_projects(self) -> Sequence[Project]:
        return tuple(_project_from_json(item) for item in _load(self._path).get("projects", []))


class SnapshotInstanceRepository:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def list_instances(self) -> Sequence[Instance]:
        return tuple(_instance_from_json(item) for item in _load(self._path).get("instances", []))


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError("OpenStack snapshot must be an object")
    return cast(dict[str, Any], loaded)


def _project_from_json(value: dict[str, Any]) -> Project:
    return Project(
        id=str(value["id"]),
        name=str(value["name"]),
        domain_id=str(value.get("domain_id", "")),
        enabled=bool(value.get("enabled", True)),
        metadata=value.get("metadata", {}),
    )


def _instance_from_json(value: dict[str, Any]) -> Instance:
    return Instance(
        id=str(value["id"]),
        name=str(value["name"]),
        project_id=str(value["project_id"]),
        status=str(value.get("status", "UNKNOWN")),
        region=str(value.get("region", "")),
        availability_zone=str(value.get("availability_zone", "")),
        addresses=tuple(_address_from_json(item) for item in value.get("addresses", [])),
        metadata=value.get("metadata", {}),
    )


def _address_from_json(value: dict[str, Any]) -> NetworkAddress:
    family = value.get("family")
    return NetworkAddress(
        network=str(value.get("network", "")),
        address=str(value["address"]),
        family=int(family) if family is not None else None,
        type=str(value.get("type", "")),
    )
