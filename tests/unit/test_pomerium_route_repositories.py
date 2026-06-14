from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from mustelinet_reconciler.domain.models.pomerium import ManagedSSHRoute
from mustelinet_reconciler.infrastructure.pomerium.config_repository import (
    PomeriumConfigRouteRepository,
)
from mustelinet_reconciler.infrastructure.pomerium.json_route_repository import (
    JsonPomeriumRouteRepository,
)


class JsonPomeriumRouteRepositoryTests(unittest.TestCase):
    def test_upserts_and_deletes_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonPomeriumRouteRepository(Path(directory) / "state.json")
            route = _route()

            repository.upsert_route(route)
            routes = repository.list_managed_routes("openstack-pomerium-nova-reconciler")
            self.assertEqual(("par1:vm1",), tuple(item.identity for item in routes))

            repository.delete_route(route)
            self.assertEqual((), repository.list_managed_routes("openstack-pomerium-nova-reconciler"))


class PomeriumConfigRouteRepositoryTests(unittest.TestCase):
    def test_upserts_routes_without_dropping_unmanaged_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                yaml.safe_dump(
                    {
                        "authenticate_service_url": "https://authenticate.example.com",
                        "routes": [
                            {
                                "from": "https://console.example.com",
                                "to": "http://console:8080",
                                "allow_any_authenticated_user": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            repository = PomeriumConfigRouteRepository(path)

            repository.upsert_route(_route())

            config = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(2, len(config["routes"]))
            managed = [
                item for item in config["routes"] if item["from"] == "ssh://web01-otterlab"
            ][0]
            self.assertEqual("ssh://10.0.0.10:22", managed["to"])
            self.assertEqual(
                "openstack:otterlab:member",
                managed["policy"][1]["allow"]["and"][0]["claim/groups"],
            )
            self.assertEqual("root", managed["policy"][0]["deny"]["and"][0]["ssh_username"]["is"])
            self.assertTrue(
                any(item["from"] == "https://console.example.com" for item in config["routes"])
            )

    def test_reads_and_deletes_managed_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            repository = PomeriumConfigRouteRepository(path)
            route = _route()
            repository.upsert_route(route)

            self.assertEqual(
                ("par1:vm1",),
                tuple(item.identity for item in repository.list_managed_routes(route.managed_by or "")),
            )

            repository.delete_route(route)

            self.assertEqual((), repository.list_managed_routes(route.managed_by or ""))


def _route() -> ManagedSSHRoute:
    return ManagedSSHRoute(
        name="route-id",
        route_name="web01-otterlab",
        source_id="vm1",
        project_id="p1",
        project_name="otterlab",
        region="par1",
        group_claim="groups",
        allowed_groups=("openstack:otterlab:member",),
        forbidden_logins=("root",),
        labels={"mustelinet.io/managed-by": "openstack-pomerium-nova-reconciler"},
        address="10.0.0.10",
    )


if __name__ == "__main__":
    unittest.main()
