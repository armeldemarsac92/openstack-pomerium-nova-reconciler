from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mustelinet_reconciler.config.loader import load_settings


class ConfigLoaderTests(unittest.TestCase):
    def test_loads_yaml_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                """
openstack:
  cloud: reconciler
  sync_statuses:
    - active
pomerium:
  group_value_template: "openstack:{project}:{role}"
  allowed_logins:
    - ubuntu
    - debian
  project_roles:
    - admin
    - member
""",
                encoding="utf-8",
            )

            settings = load_settings(path)

            self.assertEqual("reconciler", settings.openstack.cloud)
            self.assertEqual("openstack:{project}:{role}", settings.pomerium.group_value_template)
            self.assertEqual(("ubuntu", "debian"), settings.pomerium.allowed_logins)
            self.assertEqual(("admin", "member"), settings.pomerium.project_roles)
            self.assertEqual(("ACTIVE",), settings.openstack.sync_statuses)


if __name__ == "__main__":
    unittest.main()
