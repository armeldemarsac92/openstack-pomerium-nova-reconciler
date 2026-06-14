from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from mustelinet_reconciler.domain.models.openstack import Project


class ProjectRepository(Protocol):
    def list_projects(self) -> Sequence[Project]:
        """Return OpenStack projects visible to the reconciler."""
