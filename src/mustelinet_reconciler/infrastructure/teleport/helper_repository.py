from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Sequence

from mustelinet_reconciler.domain.models.teleport import (
    ManagedNode,
    ManagedRole,
    OIDCConnectorMappings,
    OIDCMapping,
)


class TeleportHelperRepository:
    def __init__(
        self,
        *,
        helper_path: str,
        proxy_addr: str,
        identity_file: str,
        managed_by: str,
        managed_role_prefix: str,
        connector_name: str,
        timeout_seconds: int = 30,
    ) -> None:
        self._helper_path = helper_path
        self._proxy_addr = proxy_addr
        self._identity_file = identity_file
        self._managed_by = managed_by
        self._managed_role_prefix = managed_role_prefix
        self._connector_name = connector_name
        self._timeout_seconds = timeout_seconds

    def list_managed_nodes(self, managed_by: str) -> Sequence[ManagedNode]:
        response = self._call("list-nodes", managed_by=managed_by)
        return tuple(_node_from_payload(item) for item in response.get("nodes", []))

    def upsert_node(self, node: ManagedNode) -> None:
        self._call("upsert-node", node=_node_to_payload(node))

    def delete_node(self, node: ManagedNode) -> None:
        self._call("delete-node", node=_node_to_payload(node))

    def list_managed_roles(self, managed_by: str) -> Sequence[ManagedRole]:
        response = self._call("list-roles", managed_by=managed_by)
        return tuple(_role_from_payload(item) for item in response.get("roles", []))

    def upsert_role(self, role: ManagedRole) -> None:
        self._call("upsert-role", role=_role_to_payload(role))

    def delete_role(self, role: ManagedRole) -> None:
        self._call("delete-role", role=_role_to_payload(role))

    def get_managed_mappings(
        self,
        connector_name: str,
        managed_role_prefix: str,
    ) -> OIDCConnectorMappings | None:
        response = self._call(
            "get-oidc-connector",
            connector_name=connector_name,
            managed_role_prefix=managed_role_prefix,
        )
        payload = response.get("oidc_mappings")
        if payload is None:
            return None
        return _oidc_from_payload(payload)

    def upsert_managed_mappings(
        self,
        mappings: OIDCConnectorMappings,
        managed_role_prefix: str,
    ) -> None:
        self._call(
            "upsert-oidc-connector",
            oidc_mappings=_oidc_to_payload(mappings),
            managed_role_prefix=managed_role_prefix,
        )

    def health(self) -> None:
        self._call("health", include_auth=False)

    def _call(self, command: str, include_auth: bool = True, **payload: Any) -> dict[str, Any]:
        request = {
            "command": command,
            **payload,
        }
        if include_auth:
            request.update(
                {
                    "proxy_addr": self._proxy_addr,
                    "identity_file": self._identity_file,
                    "managed_by": self._managed_by,
                    "managed_role_prefix": self._managed_role_prefix,
                    "connector_name": self._connector_name,
                }
            )

        result = subprocess.run(
            [self._helper_path],
            input=json.dumps(request),
            text=True,
            capture_output=True,
            timeout=self._timeout_seconds,
            check=False,
        )
        response = _decode_response(result.stdout)
        if result.returncode != 0 or not response.get("ok", False):
            error = response.get("error") or result.stderr.strip() or f"helper exited {result.returncode}"
            raise TeleportHelperError(error)
        return response


class TeleportHelperError(RuntimeError):
    pass


def _decode_response(stdout: str) -> dict[str, Any]:
    if not stdout.strip():
        return {}
    try:
        loaded = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise TeleportHelperError(f"invalid helper response: {exc}") from exc
    if not isinstance(loaded, dict):
        raise TeleportHelperError("invalid helper response: expected object")
    return loaded


def _node_to_payload(node: ManagedNode) -> dict[str, Any]:
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


def _node_from_payload(payload: dict[str, Any]) -> ManagedNode:
    return ManagedNode(
        name=str(payload["name"]),
        hostname=str(payload["hostname"]),
        source_id=str(payload["source_id"]),
        project_id=str(payload["project_id"]),
        project_name=str(payload["project_name"]),
        region=str(payload["region"]),
        labels={str(key): str(value) for key, value in payload.get("labels", {}).items()},
        logins=tuple(str(item) for item in payload.get("logins", ["ubuntu"])),
        address=payload.get("address"),
        port=int(payload.get("port", 22)),
    )


def _role_to_payload(role: ManagedRole) -> dict[str, Any]:
    return {
        "name": role.name,
        "project_id": role.project_id,
        "project_name": role.project_name,
        "project_role": role.project_role,
        "logins": list(role.logins),
        "node_labels": dict(role.node_labels),
        "managed_by": role.managed_by,
    }


def _role_from_payload(payload: dict[str, Any]) -> ManagedRole:
    return ManagedRole(
        name=str(payload["name"]),
        project_id=str(payload["project_id"]),
        project_name=str(payload["project_name"]),
        project_role=str(payload["project_role"]),
        logins=tuple(str(item) for item in payload.get("logins", ["ubuntu"])),
        node_labels={str(key): str(value) for key, value in payload.get("node_labels", {}).items()},
        managed_by=str(payload["managed_by"]),
    )


def _oidc_to_payload(mappings: OIDCConnectorMappings) -> dict[str, Any]:
    return {
        "name": mappings.name,
        "mappings": [
            {
                "claim": mapping.claim,
                "value": mapping.value,
                "roles": list(mapping.roles),
            }
            for mapping in mappings.mappings
        ],
    }


def _oidc_from_payload(payload: dict[str, Any]) -> OIDCConnectorMappings:
    return OIDCConnectorMappings(
        name=str(payload["name"]),
        mappings=tuple(
            OIDCMapping(
                claim=str(item["claim"]),
                value=str(item["value"]),
                roles=tuple(str(role) for role in item.get("roles", [])),
            )
            for item in payload.get("mappings", [])
        ),
    )


def helper_exists(path: str) -> bool:
    return Path(path).exists()
