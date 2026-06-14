from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from mustelinet_reconciler.domain.models.openstack import Instance


class InstanceRepository(Protocol):
    def list_instances(self) -> Sequence[Instance]:
        """Return OpenStack instances visible to the reconciler."""
