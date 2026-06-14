from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from mustelinet_reconciler.domain.models.pomerium import ManagedSSHRoute


class PomeriumRouteRepository(Protocol):
    def list_managed_routes(self, managed_by: str) -> Sequence[ManagedSSHRoute]:
        """Return Pomerium SSH routes managed by this reconciler."""

    def upsert_route(self, route: ManagedSSHRoute) -> None:
        """Create or update a managed Pomerium SSH route."""

    def delete_route(self, route: ManagedSSHRoute) -> None:
        """Delete a managed Pomerium SSH route."""
