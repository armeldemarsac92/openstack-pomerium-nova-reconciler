from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from mustelinet_reconciler.config.settings import TeleportSettings
from mustelinet_reconciler.domain.models.openstack import Instance, Project
from mustelinet_reconciler.domain.models.teleport import ManagedNode


@dataclass(frozen=True, slots=True)
class TeleportNodeBuilder:
    settings: TeleportSettings

    def build(self, project: Project, instance: Instance) -> ManagedNode:
        labels = {
            "mustelinet.io/managed-by": self.settings.managed_by,
            "mustelinet.io/source": "openstack",
            "mustelinet.io/source-id": instance.id,
            "mustelinet.io/project-id": project.id,
            "mustelinet.io/project-name": project.name,
            "mustelinet.io/region": instance.region,
            "mustelinet.io/instance-name": instance.name,
            "mustelinet.io/status": instance.status,
        }
        if instance.availability_zone:
            labels["mustelinet.io/availability-zone"] = instance.availability_zone

        labels.update(_metadata_labels(project.metadata.items(), "openstack.project-metadata/"))
        labels.update(_metadata_labels(instance.metadata.items(), "openstack.instance-metadata/"))

        return ManagedNode(
            name=instance.name,
            source_id=instance.id,
            project_id=project.id,
            project_name=project.name,
            region=instance.region,
            labels=labels,
            logins=self.settings.default_logins,
            address=instance.preferred_ssh_address(),
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
