from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OpenStackSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    cloud: str = "admin"
    regions: tuple[str, ...] = ()
    sync_statuses: tuple[str, ...] = ("ACTIVE",)
    address_family: str = "ipv4"

    @field_validator("sync_statuses", mode="after")
    @classmethod
    def normalize_statuses(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(status.upper() for status in value)

    @field_validator("address_family", mode="after")
    @classmethod
    def validate_address_family(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"ipv4", "ipv6", "any"}:
            raise ValueError("address_family must be one of: ipv4, ipv6, any")
        return normalized


class ControllerSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    poll_interval_seconds: int = Field(default=15, ge=1)
    dry_run: bool = False


class TeleportSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    helper_path: str = "mustelinet-teleport-helper"
    proxy_addr: str = ""
    identity_file: str = ""
    oidc_connector_name: str = "authentik"
    managed_by: str = "openstack-teleport-reconciler"
    role_name_prefix: str = "mustelinet-project-"
    default_logins: tuple[str, ...] = ("ubuntu",)
    delete_stale_nodes: bool = True
    delete_stale_roles: bool = True


class ObservabilitySettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    log_level: str = "INFO"
    http_addr: str = "0.0.0.0:8080"


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    openstack: OpenStackSettings = Field(default_factory=OpenStackSettings)
    controller: ControllerSettings = Field(default_factory=ControllerSettings)
    teleport: TeleportSettings = Field(default_factory=TeleportSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
