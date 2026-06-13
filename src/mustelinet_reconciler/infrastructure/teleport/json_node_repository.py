from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from mustelinet_reconciler.domain.models.teleport import ManagedNode


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
        "source_id": node.source_id,
        "project_id": node.project_id,
        "project_name": node.project_name,
        "region": node.region,
        "labels": dict(node.labels),
        "logins": list(node.logins),
        "address": node.address,
        "port": node.port,
    }
