from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from mustelinet_reconciler.config.settings import OpenStackSettings, TeleportSettings
from mustelinet_reconciler.domain.models.openstack import Instance, Project
from mustelinet_reconciler.domain.models.teleport import ManagedNode, stable_node_uuid
from mustelinet_reconciler.domain.services.naming import slugify


@dataclass(frozen=True, slots=True)
class TeleportNodeBuilder:
    openstack_settings: OpenStackSettings
    teleport_settings: TeleportSettings

    def build(self, project: Project, instance: Instance, hostname: str) -> ManagedNode:
        identity = f"{instance.region}:{instance.id}"
        labels = {
            "mustelinet.io/managed-by": self.teleport_settings.managed_by,
            "mustelinet.io/source": "openstack",
            "mustelinet.io/source-id": instance.id,
            "mustelinet.io/project-id": project.id,
            "mustelinet.io/project-name": project.name,
            "mustelinet.io/project-slug": slugify(project.name),
            "mustelinet.io/region": instance.region,
            "mustelinet.io/instance-name": instance.name,
            "mustelinet.io/status": instance.status,
        }
        if instance.availability_zone:
            labels["mustelinet.io/availability-zone"] = instance.availability_zone

        labels.update(_metadata_labels(project.metadata.items(), "openstack.project-metadata/"))
        labels.update(_metadata_labels(instance.metadata.items(), "openstack.instance-metadata/"))

        return ManagedNode(
            name=stable_node_uuid(identity),
            hostname=hostname,
            source_id=instance.id,
            project_id=project.id,
            project_name=project.name,
            region=instance.region,
            labels=labels,
            logins=self.teleport_settings.default_logins,
            address=instance.preferred_ssh_address(self.openstack_settings.address_family),
        )


def _metadata_labels(items: Iterable[tuple[str, object]], prefix: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    for key, value in items:
        if value is None or isinstance(value, (dict, list, tuple, set)):
            continue
        safe_key = str(key).strip().replace(" ", "-").lower()
        if safe_key:
            labels[f"{prefix}{safe_key}"] = str(value)
    return labels
