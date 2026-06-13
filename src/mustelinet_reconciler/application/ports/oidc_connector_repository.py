from __future__ import annotations

from typing import Protocol

from mustelinet_reconciler.domain.models.teleport import OIDCConnectorMappings


class OIDCConnectorRepository(Protocol):
    def get_managed_mappings(
        self,
        connector_name: str,
        managed_role_prefix: str,
    ) -> OIDCConnectorMappings | None:
        """Return managed claims-to-roles mappings for an OIDC connector."""

    def upsert_managed_mappings(
        self,
        mappings: OIDCConnectorMappings,
        managed_role_prefix: str,
    ) -> None:
        """Merge generated mappings into an OIDC connector without dropping unmanaged mappings."""
