from __future__ import annotations

from typing import Any

import openstack


def create_connection(cloud: str) -> Any:
    return openstack.connect(cloud=cloud)
