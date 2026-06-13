from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from mustelinet_reconciler.domain.models.teleport import (
    ManagedNode,
    ManagedRole,
    OIDCConnectorMappings,
    OIDCMapping,
)


class JsonTeleportNodeRepository:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def list_managed_nodes(self, managed_by: str) -> Sequence[ManagedNode]:
        nodes = (_node_from_json(item) for item in self._load().get("nodes", []))
        return tuple(node for node in nodes if node.managed_by == managed_by)

    def upsert_node(self, node: ManagedNode) -> None:
        state = self._load()
        nodes = [_node_from_json(item) for item in state.get("nodes", [])]
        updated = [current for current in nodes if current.identity != node.identity]
        updated.append(node)
        state["nodes"] = [_node_to_json(item) for item in sorted(updated, key=lambda item: item.identity)]
        self._save(state)

    def delete_node(self, node: ManagedNode) -> None:
        state = self._load()
        nodes = [_node_from_json(item) for item in state.get("nodes", [])]
        state["nodes"] = [
            _node_to_json(current) for current in nodes if current.identity != node.identity
        ]
        self._save(state)

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"nodes": []}
        with self._path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save(self, state: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        temporary.replace(self._path)


def _node_from_json(value: dict[str, Any]) -> ManagedNode:
    return ManagedNode(
        name=str(value["name"]),
        hostname=str(value.get("hostname", value["name"])),
        source_id=str(value["source_id"]),
        project_id=str(value["project_id"]),
        project_name=str(value["project_name"]),
        region=str(value["region"]),
        labels={str(key): str(item) for key, item in value.get("labels", {}).items()},
        logins=tuple(str(item) for item in value.get("logins", ["ubuntu"])),
        address=value.get("address"),
        port=int(value.get("port", 22)),
    )


def _node_to_json(node: ManagedNode) -> dict[str, Any]:
    return {
        "name": node.name,
        "hostname": node.hostname,
        "source_id": node.source_id,
        "project_id": node.project_id,
        "project_name": node.project_name,
        "region": node.region,
        "labels": dict(node.labels),
        "logins": list(node.logins),
        "address": node.address,
        "port": node.port,
    }


class JsonTeleportRoleRepository:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def list_managed_roles(self, managed_by: str) -> Sequence[ManagedRole]:
        roles = (_role_from_json(item) for item in self._load().get("roles", []))
        return tuple(role for role in roles if role.managed_by == managed_by)

    def upsert_role(self, role: ManagedRole) -> None:
        state = self._load()
        roles = [_role_from_json(item) for item in state.get("roles", [])]
        updated = [current for current in roles if current.identity != role.identity]
        updated.append(role)
        state["roles"] = [_role_to_json(item) for item in sorted(updated, key=lambda item: item.identity)]
        self._save(state)

    def delete_role(self, role: ManagedRole) -> None:
        state = self._load()
        roles = [_role_from_json(item) for item in state.get("roles", [])]
        state["roles"] = [
            _role_to_json(current) for current in roles if current.identity != role.identity
        ]
        self._save(state)

    def _load(self) -> dict[str, Any]:
        return _load_state(self._path)

    def _save(self, state: dict[str, Any]) -> None:
        _save_state(self._path, state)


class JsonOIDCConnectorRepository:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def get_managed_mappings(
        self,
        connector_name: str,
        managed_role_prefix: str,
    ) -> OIDCConnectorMappings | None:
        connector = self._load().get("oidc_connectors", {}).get(connector_name)
        if connector is None:
            return None
        mappings = _oidc_mappings_from_json(connector_name, connector)
        return _filter_managed_mappings(mappings, managed_role_prefix)

    def upsert_managed_mappings(
        self,
        mappings: OIDCConnectorMappings,
        managed_role_prefix: str,
    ) -> None:
        state = self._load()
        connectors = state.setdefault("oidc_connectors", {})
        existing = connectors.get(mappings.name, {"mappings": []})
        existing_mappings = _oidc_mappings_from_json(mappings.name, existing)
        unmanaged = tuple(
            mapping
            for mapping in existing_mappings.mappings
            if not all(role.startswith(managed_role_prefix) for role in mapping.roles)
        )
        connectors[mappings.name] = _oidc_mappings_to_json(
            OIDCConnectorMappings(mappings.name, unmanaged + mappings.mappings)
        )
        self._save(state)

    def _load(self) -> dict[str, Any]:
        return _load_state(self._path)

    def _save(self, state: dict[str, Any]) -> None:
        _save_state(self._path, state)


def _role_from_json(value: dict[str, Any]) -> ManagedRole:
    return ManagedRole(
        name=str(value["name"]),
        project_id=str(value["project_id"]),
        project_name=str(value["project_name"]),
        project_role=str(value["project_role"]),
        logins=tuple(str(item) for item in value.get("logins", ["ubuntu"])),
        node_labels={str(key): str(item) for key, item in value.get("node_labels", {}).items()},
        managed_by=str(value["managed_by"]),
    )


def _role_to_json(role: ManagedRole) -> dict[str, Any]:
    return {
        "name": role.name,
        "project_id": role.project_id,
        "project_name": role.project_name,
        "project_role": role.project_role,
        "logins": list(role.logins),
        "node_labels": dict(role.node_labels),
        "managed_by": role.managed_by,
    }


def _oidc_mappings_from_json(name: str, value: dict[str, Any]) -> OIDCConnectorMappings:
    return OIDCConnectorMappings(
        name,
        tuple(
            OIDCMapping(
                claim=str(item["claim"]),
                value=str(item["value"]),
                roles=tuple(str(role) for role in item.get("roles", [])),
            )
            for item in value.get("mappings", [])
        ),
    )


def _oidc_mappings_to_json(mappings: OIDCConnectorMappings) -> dict[str, Any]:
    return {
        "mappings": [
            {
                "claim": mapping.claim,
                "value": mapping.value,
                "roles": list(mapping.roles),
            }
            for mapping in mappings.mappings
        ]
    }


def _filter_managed_mappings(
    mappings: OIDCConnectorMappings,
    managed_role_prefix: str,
) -> OIDCConnectorMappings:
    return OIDCConnectorMappings(
        mappings.name,
        tuple(
            mapping
            for mapping in mappings.mappings
            if all(role.startswith(managed_role_prefix) for role in mapping.roles)
        ),
    )


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"nodes": [], "roles": [], "oidc_connectors": {}}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(path)
