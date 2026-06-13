from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mustelinet_reconciler.domain.models.teleport import (
    ManagedNode,
    ManagedRole,
    OIDCConnectorMappings,
    OIDCMapping,
)
from mustelinet_reconciler.infrastructure.teleport.json_node_repository import (
    JsonOIDCConnectorRepository,
    JsonTeleportNodeRepository,
    JsonTeleportRoleRepository,
)


class JsonNodeRepositoryTests(unittest.TestCase):
    def test_upserts_and_deletes_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonTeleportNodeRepository(Path(directory) / "state.json")
            node = ManagedNode(
                name="web01",
                hostname="web01",
                source_id="vm1",
                project_id="p1",
                project_name="otterlab",
                region="par1",
                labels={"mustelinet.io/managed-by": "openstack-teleport-reconciler"},
            )

            repository.upsert_node(node)
            nodes = repository.list_managed_nodes("openstack-teleport-reconciler")
            self.assertEqual(("par1:vm1",), tuple(item.identity for item in nodes))

            repository.delete_node(node)
            self.assertEqual((), repository.list_managed_nodes("openstack-teleport-reconciler"))

    def test_upserts_and_deletes_roles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonTeleportRoleRepository(Path(directory) / "state.json")
            role = ManagedRole(
                name="mustelinet-project-otterlab-member",
                project_id="p1",
                project_name="otterlab",
                project_role="member",
                logins=("ubuntu",),
                node_labels={"mustelinet.io/project-id": "p1"},
                managed_by="openstack-teleport-reconciler",
            )

            repository.upsert_role(role)
            roles = repository.list_managed_roles("openstack-teleport-reconciler")
            self.assertEqual(("mustelinet-project-otterlab-member",), tuple(item.name for item in roles))

            repository.delete_role(role)
            self.assertEqual((), repository.list_managed_roles("openstack-teleport-reconciler"))

    def test_upserts_oidc_mappings_without_dropping_unmanaged_mappings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonOIDCConnectorRepository(Path(directory) / "state.json")
            existing = OIDCConnectorMappings(
                name="authentik",
                mappings=(
                    OIDCMapping("groups", "admins", ("access",)),
                    OIDCMapping("groups", "project-old-member", ("mustelinet-project-old-member",)),
                ),
            )
            desired = OIDCConnectorMappings(
                name="authentik",
                mappings=(
                    OIDCMapping(
                        "groups",
                        "project-otterlab-member",
                        ("mustelinet-project-otterlab-member",),
                    ),
                ),
            )

            repository.upsert_managed_mappings(existing, "mustelinet-project-")
            repository.upsert_managed_mappings(desired, "mustelinet-project-")
            mappings = repository.get_managed_mappings("authentik", "mustelinet-project-")

            self.assertIsNotNone(mappings)
            self.assertEqual(("project-otterlab-member",), tuple(item.value for item in mappings.mappings))


if __name__ == "__main__":
    unittest.main()
