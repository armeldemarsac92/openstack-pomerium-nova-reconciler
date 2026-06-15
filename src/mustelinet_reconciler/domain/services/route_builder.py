from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from mustelinet_reconciler.config.settings import OpenStackSettings, PomeriumSettings
from mustelinet_reconciler.domain.models.openstack import Instance, Project
from mustelinet_reconciler.domain.models.pomerium import ManagedSSHRoute, stable_route_uuid
from mustelinet_reconciler.domain.services.naming import project_group_value, slugify


@dataclass(frozen=True, slots=True)
class PomeriumRouteBuilder:
    openstack_settings: OpenStackSettings
    pomerium_settings: PomeriumSettings

    def build(self, project: Project, instance: Instance, route_name: str) -> ManagedSSHRoute:
        identity = f"{instance.region}:{instance.id}"
        labels = {
            "mustelinet.io/managed-by": self.pomerium_settings.managed_by,
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

        return ManagedSSHRoute(
            name=stable_route_uuid(identity),
            route_name=f"{self.pomerium_settings.route_name_prefix}{route_name}",
            source_id=instance.id,
            project_id=project.id,
            project_name=project.name,
            region=instance.region,
            group_claim=self.pomerium_settings.group_claim,
            allowed_groups=tuple(
                project_group_value(project.name, role, self.pomerium_settings.group_value_template)
                for role in self.pomerium_settings.project_roles
            ),
            forbidden_logins=self.pomerium_settings.forbidden_logins,
            timeout=self.pomerium_settings.route_timeout,
            idle_timeout=self.pomerium_settings.route_idle_timeout,
            labels=labels,
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
