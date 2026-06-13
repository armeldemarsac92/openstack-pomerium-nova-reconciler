from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mustelinet_reconciler.domain.models.teleport import ManagedNode
from mustelinet_reconciler.infrastructure.teleport.json_node_repository import (
    JsonTeleportNodeRepository,
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


if __name__ == "__main__":
    unittest.main()
