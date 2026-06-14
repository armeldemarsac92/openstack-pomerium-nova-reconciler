from __future__ import annotations

from typing import Any, Sequence

from mustelinet_reconciler.domain.models.openstack import Instance, NetworkAddress


class NovaInstanceRepository:
    def __init__(self, connection: Any, regions: Sequence[str] = ()) -> None:
        self._connection = connection
        self._regions = tuple(regions)

    def list_instances(self) -> Sequence[Instance]:
        connections = (
            [self._connection.connect_as(region_name=region) for region in self._regions]
            if self._regions
            else [self._connection]
        )
        instances: list[Instance] = []
        for connection in connections:
            region = str(getattr(connection.config, "region_name", "") or "")
            for server in connection.compute.servers(all_projects=True):
                instances.append(_instance_from_resource(server, region))
        return tuple(instances)


def _instance_from_resource(resource: Any, region: str) -> Instance:
    addresses = tuple(_addresses_from_resource(getattr(resource, "addresses", {}) or {}))
    metadata = dict(getattr(resource, "metadata", {}) or {})
    return Instance(
        id=str(resource.id),
        name=str(resource.name),
        project_id=str(getattr(resource, "project_id", getattr(resource, "tenant_id", ""))),
        status=str(getattr(resource, "status", "UNKNOWN")),
        region=region,
        availability_zone=str(getattr(resource, "availability_zone", "")),
        addresses=addresses,
        metadata=metadata,
    )


def _addresses_from_resource(addresses: dict[str, Any]) -> list[NetworkAddress]:
    result: list[NetworkAddress] = []
    for network, values in addresses.items():
        for value in values:
            result.append(
                NetworkAddress(
                    network=str(network),
                    address=str(value.get("addr", value.get("address", ""))),
                    family=value.get("version"),
                    type=value.get("OS-EXT-IPS:type"),
                )
            )
    return result
