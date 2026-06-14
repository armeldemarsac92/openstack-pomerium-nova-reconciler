from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from mustelinet_reconciler.domain.models.pomerium import ManagedSSHRoute

MANAGED_DESCRIPTION_PREFIX = "mustelinet-managed:"


class PomeriumConfigRouteRepository:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def list_managed_routes(self, managed_by: str) -> Sequence[ManagedSSHRoute]:
        routes = (_route_from_config(item) for item in self._load_routes())
        return tuple(route for route in routes if route is not None and route.managed_by == managed_by)

    def upsert_route(self, route: ManagedSSHRoute) -> None:
        config = self._load()
        routes = [_coerce_route(item) for item in config.get("routes", [])]
        updated = [
            current
            for current in routes
            if _managed_route_identity(current) not in {route.identity, None}
            or _managed_route_identity(current) is None
        ]
        updated.append(_route_to_config(route))
        config["routes"] = sorted(updated, key=lambda item: str(item.get("from", "")))
        self._save(config)

    def delete_route(self, route: ManagedSSHRoute) -> None:
        config = self._load()
        routes = [_coerce_route(item) for item in config.get("routes", [])]
        config["routes"] = [
            current for current in routes if _managed_route_identity(current) != route.identity
        ]
        self._save(config)

    def _load_routes(self) -> Sequence[Mapping[str, Any]]:
        return tuple(_coerce_route(item) for item in self._load().get("routes", []))

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"routes": []}
        with self._path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        if not isinstance(loaded, dict):
            raise PomeriumConfigError("Pomerium config must be a YAML mapping")
        routes = loaded.get("routes", [])
        if not isinstance(routes, list):
            raise PomeriumConfigError("Pomerium config routes must be a list")
        return dict(loaded)

    def _save(self, config: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(config, handle, sort_keys=False)
        temporary.replace(self._path)


class PomeriumConfigError(RuntimeError):
    pass


def _route_to_config(route: ManagedSSHRoute) -> dict[str, Any]:
    if route.to_url is None:
        raise PomeriumConfigError(f"route {route.identity} has no upstream SSH address")
    return {
        "from": route.from_url,
        "to": route.to_url,
        "description": _description_from_route(route),
        "policy": _plain_value(route.policy),
    }


def _route_from_config(value: Mapping[str, Any]) -> ManagedSSHRoute | None:
    metadata = _metadata_from_description(str(value.get("description", "")))
    if metadata is None:
        return None

    route_name = _route_name_from_url(str(value.get("from", metadata.get("route_name", ""))))
    address, port = _address_port_from_url(str(value.get("to", "")))
    group_claim, allowed_groups, forbidden_logins = _policy_parts(value.get("policy"))
    return ManagedSSHRoute(
        name=str(metadata["name"]),
        route_name=route_name or str(metadata["route_name"]),
        source_id=str(metadata["source_id"]),
        project_id=str(metadata["project_id"]),
        project_name=str(metadata["project_name"]),
        region=str(metadata["region"]),
        group_claim=group_claim or str(metadata["group_claim"]),
        allowed_groups=allowed_groups or tuple(str(item) for item in metadata["allowed_groups"]),
        forbidden_logins=forbidden_logins
        or tuple(str(item) for item in metadata.get("forbidden_logins", [])),
        labels={str(key): str(item) for key, item in metadata.get("labels", {}).items()},
        address=address or metadata.get("address"),
        port=port or int(metadata.get("port", 22)),
    )


def _description_from_route(route: ManagedSSHRoute) -> str:
    metadata = {
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
    return f"{MANAGED_DESCRIPTION_PREFIX}{json.dumps(metadata, separators=(',', ':'), sort_keys=True)}"


def _metadata_from_description(description: str) -> dict[str, Any] | None:
    if not description.startswith(MANAGED_DESCRIPTION_PREFIX):
        return None
    payload = description[len(MANAGED_DESCRIPTION_PREFIX) :]
    try:
        metadata = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PomeriumConfigError("managed route description contains invalid JSON") from exc
    if not isinstance(metadata, dict):
        raise PomeriumConfigError("managed route description metadata must be an object")
    return metadata


def _managed_route_identity(value: Mapping[str, Any]) -> str | None:
    route = _route_from_config(value)
    return None if route is None else route.identity


def _coerce_route(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PomeriumConfigError("Pomerium route entries must be YAML mappings")
    return value


def _route_name_from_url(value: str) -> str:
    if value.startswith("ssh://"):
        return value[len("ssh://") :].split("/", 1)[0]
    return value


def _address_port_from_url(value: str) -> tuple[str | None, int | None]:
    if not value.startswith("ssh://"):
        return None, None
    host_port = value[len("ssh://") :].split("/", 1)[0]
    if host_port.startswith("["):
        host, _, port_value = host_port[1:].partition("]:")
    else:
        host, _, port_value = host_port.rpartition(":")
    if not host or not port_value:
        return None, None
    try:
        return host, int(port_value)
    except ValueError:
        return None, None


def _policy_parts(value: Any) -> tuple[str | None, tuple[str, ...], tuple[str, ...]]:
    if not isinstance(value, list):
        return None, (), ()

    group_claim: str | None = None
    groups: set[str] = set()
    forbidden_logins: set[str] = set()

    for rule in value:
        if not isinstance(rule, dict):
            continue
        action = "deny" if "deny" in rule else "allow"
        policy_action = rule.get(action)
        if not isinstance(policy_action, dict):
            continue
        conditions = policy_action.get("and", [])
        if not isinstance(conditions, list):
            continue
        for condition in conditions:
            if not isinstance(condition, dict):
                continue
            for key, item in condition.items():
                if key.startswith("claim/"):
                    group_claim = key[len("claim/") :]
                    groups.add(str(item))
                elif action == "deny" and key == "ssh_username" and isinstance(item, dict):
                    if "is" in item:
                        forbidden_logins.add(str(item["is"]))
                    if isinstance(item.get("in"), list):
                        forbidden_logins.update(str(login) for login in item["in"])

    return group_claim, tuple(sorted(groups)), tuple(sorted(forbidden_logins))


def _plain_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain_value(item) for item in value]
    if isinstance(value, list):
        return [_plain_value(item) for item in value]
    return value
