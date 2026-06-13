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
teleport:
  default_logins:
    - ubuntu
    - debian
""",
                encoding="utf-8",
            )

            settings = load_settings(path)

            self.assertEqual("reconciler", settings.openstack.cloud)
            self.assertEqual(("ubuntu", "debian"), settings.teleport.default_logins)
            self.assertEqual(("ACTIVE",), settings.openstack.sync_statuses)


if __name__ == "__main__":
    unittest.main()
