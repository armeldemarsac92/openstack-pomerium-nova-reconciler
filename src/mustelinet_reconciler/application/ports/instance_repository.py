from __future__ import annotations

from typing import Protocol, Sequence

from mustelinet_reconciler.domain.models.openstack import Instance


class InstanceRepository(Protocol):
    def list_instances(self) -> Sequence[Instance]:
        """Return OpenStack instances visible to the reconciler."""
