from __future__ import annotations

from typing import Protocol, Sequence

from mustelinet_reconciler.domain.models.teleport import ManagedNode


class TeleportNodeRepository(Protocol):
    def list_managed_nodes(self, managed_by: str) -> Sequence[ManagedNode]:
        """Return Teleport nodes managed by this reconciler."""

    def upsert_node(self, node: ManagedNode) -> None:
        """Create or update a Teleport node resource."""

    def delete_node(self, node: ManagedNode) -> None:
        """Delete a Teleport node resource."""
