from __future__ import annotations

import json
import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from mustelinet_reconciler.domain.models.teleport import ManagedNode
from mustelinet_reconciler.infrastructure.teleport.helper_repository import (
    TeleportHelperError,
    TeleportHelperRepository,
)


class TeleportHelperRepositoryTests(unittest.TestCase):
    def test_invokes_helper_with_auth_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _write_helper(Path(directory), {"ok": True, "nodes": [_node_payload()]})
            repository = _repository(helper)

            nodes = repository.list_managed_nodes("openstack-teleport-reconciler")

            self.assertEqual(("par1:vm1",), tuple(node.identity for node in nodes))
            request = json.loads((Path(directory) / "request.json").read_text(encoding="utf-8"))
            self.assertEqual("list-nodes", request["command"])
            self.assertEqual("proxy.example:443", request["proxy_addr"])
            self.assertEqual("/identity", request["identity_file"])

    def test_raises_helper_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _write_helper(Path(directory), {"ok": False, "error": "boom"}, exit_code=1)
            repository = _repository(helper)

            with self.assertRaisesRegex(TeleportHelperError, "boom"):
                repository.list_managed_nodes("openstack-teleport-reconciler")

    def test_upsert_node_sends_node_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _write_helper(Path(directory), {"ok": True})
            repository = _repository(helper)

            repository.upsert_node(
                ManagedNode(
                    name="node-id",
                    hostname="web01",
                    source_id="vm1",
                    project_id="p1",
                    project_name="otterlab",
                    region="par1",
                    labels={"mustelinet.io/managed-by": "openstack-teleport-reconciler"},
                    address="10.0.0.10",
                )
            )

            request = json.loads((Path(directory) / "request.json").read_text(encoding="utf-8"))
            self.assertEqual("upsert-node", request["command"])
            self.assertEqual("web01", request["node"]["hostname"])


def _repository(helper: Path) -> TeleportHelperRepository:
    return TeleportHelperRepository(
        helper_path=str(helper),
        proxy_addr="proxy.example:443",
        identity_file="/identity",
        managed_by="openstack-teleport-reconciler",
        managed_role_prefix="mustelinet-project-",
        connector_name="authentik",
    )


def _write_helper(directory: Path, response: dict[str, object], exit_code: int = 0) -> Path:
    helper = directory / "helper.py"
    helper.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import json
            import pathlib
            import sys

            pathlib.Path({str(directory / "request.json")!r}).write_text(sys.stdin.read())
            print(json.dumps({response!r}))
            raise SystemExit({exit_code})
            """
        ),
        encoding="utf-8",
    )
    helper.chmod(helper.stat().st_mode | 0o111)
    return helper


def _node_payload() -> dict[str, object]:
    return {
        "name": "node-id",
        "hostname": "web01",
        "source_id": "vm1",
        "project_id": "p1",
        "project_name": "otterlab",
        "region": "par1",
        "labels": {"mustelinet.io/managed-by": "openstack-teleport-reconciler"},
        "address": "10.0.0.10",
        "port": 22,
    }


if __name__ == "__main__":
    unittest.main()
