from __future__ import annotations

from typing import Protocol, Sequence

from mustelinet_reconciler.domain.models.teleport import ManagedRole


class TeleportRoleRepository(Protocol):
    def list_managed_roles(self, managed_by: str) -> Sequence[ManagedRole]:
        """Return Teleport roles managed by this reconciler."""

    def upsert_role(self, role: ManagedRole) -> None:
        """Create or update a Teleport role."""

    def delete_role(self, role: ManagedRole) -> None:
        """Delete a Teleport role."""
