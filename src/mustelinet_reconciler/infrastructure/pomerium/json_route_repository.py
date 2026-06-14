from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from mustelinet_reconciler.domain.models.pomerium import ManagedSSHRoute


class JsonPomeriumRouteRepository:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def list_managed_routes(self, managed_by: str) -> Sequence[ManagedSSHRoute]:
        routes = (_route_from_json(item) for item in self._load().get("routes", []))
        return tuple(route for route in routes if route.managed_by == managed_by)

    def upsert_route(self, route: ManagedSSHRoute) -> None:
        state = self._load()
        routes = [_route_from_json(item) for item in state.get("routes", [])]
        updated = [current for current in routes if current.identity != route.identity]
        updated.append(route)
        state["routes"] = [
            _route_to_json(item) for item in sorted(updated, key=lambda item: item.identity)
        ]
        self._save(state)

    def delete_route(self, route: ManagedSSHRoute) -> None:
        state = self._load()
        routes = [_route_from_json(item) for item in state.get("routes", [])]
        state["routes"] = [
            _route_to_json(current) for current in routes if current.identity != route.identity
        ]
        self._save(state)

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"routes": []}
        with self._path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save(self, state: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        temporary.replace(self._path)


def _route_from_json(value: dict[str, Any]) -> ManagedSSHRoute:
    return ManagedSSHRoute(
        name=str(value["name"]),
        route_name=str(value["route_name"]),
        source_id=str(value["source_id"]),
        project_id=str(value["project_id"]),
        project_name=str(value["project_name"]),
        region=str(value["region"]),
        group_claim=str(value.get("group_claim", "groups")),
        allowed_groups=tuple(str(item) for item in value.get("allowed_groups", [])),
        forbidden_logins=tuple(str(item) for item in value.get("forbidden_logins", [])),
        labels={str(key): str(item) for key, item in value.get("labels", {}).items()},
        address=value.get("address"),
        port=int(value.get("port", 22)),
    )


def _route_to_json(route: ManagedSSHRoute) -> dict[str, Any]:
    return {
        "name": route.name,
        "route_name": route.route_name,
        "source_id": route.source_id,
        "project_id": route.project_id,
        "project_name": route.project_name,
        "region": route.region,
        "group_claim": route.group_claim,
        "allowed_groups": list(route.allowed_groups),
        "forbidden_logins": list(route.forbidden_logins),
        "labels": dict(route.labels),
        "address": route.address,
        "port": route.port,
    }
