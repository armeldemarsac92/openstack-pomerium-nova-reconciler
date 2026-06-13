from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OpenStackSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    cloud: str = "admin"
    regions: tuple[str, ...] = ()


class ControllerSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    poll_interval_seconds: int = Field(default=15, ge=1)
    dry_run: bool = False


class TeleportSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    managed_by: str = "openstack-teleport-reconciler"
    default_logins: tuple[str, ...] = ("ubuntu",)
    sync_statuses: tuple[str, ...] = ("ACTIVE",)
    delete_stale_nodes: bool = True

    @field_validator("sync_statuses", mode="after")
    @classmethod
    def normalize_statuses(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(status.upper() for status in value)


class ObservabilitySettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    log_level: str = "INFO"


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    openstack: OpenStackSettings = Field(default_factory=OpenStackSettings)
    controller: ControllerSettings = Field(default_factory=ControllerSettings)
    teleport: TeleportSettings = Field(default_factory=TeleportSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
