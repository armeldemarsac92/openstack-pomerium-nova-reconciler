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
  cookie_expire: 12h
  route_timeout: 0s
  route_idle_timeout: 0s
  group_value_template: "openstack:{project}:{role}"
  forbidden_logins:
    - root
  project_roles:
    - admin
    - member
""",
                encoding="utf-8",
            )

            settings = load_settings(path)

            self.assertEqual("reconciler", settings.openstack.cloud)
            self.assertEqual("12h", settings.pomerium.cookie_expire)
            self.assertEqual("0s", settings.pomerium.route_timeout)
            self.assertEqual("0s", settings.pomerium.route_idle_timeout)
            self.assertEqual("openstack:{project}:{role}", settings.pomerium.group_value_template)
            self.assertEqual(("root",), settings.pomerium.forbidden_logins)
            self.assertEqual(("admin", "member"), settings.pomerium.project_roles)
            self.assertEqual(("ACTIVE",), settings.openstack.sync_statuses)


if __name__ == "__main__":
    unittest.main()
