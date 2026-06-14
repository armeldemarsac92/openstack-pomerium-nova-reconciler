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


class PomeriumSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    config_path: str = "/etc/pomerium/config.yaml"
    managed_by: str = "openstack-pomerium-nova-reconciler"
    route_name_prefix: str = ""
    group_claim: str = "groups"
    group_value_template: str = "openstack:{project}:{role}"
    project_roles: tuple[str, ...] = ("admin", "member")
    allowed_logins: tuple[str, ...] = ("ubuntu",)
    delete_stale_routes: bool = True

    @field_validator("project_roles", "allowed_logins", mode="after")
    @classmethod
    def normalize_tuple_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(item.strip().lower() for item in value if item.strip())

    @field_validator("group_claim", mode="after")
    @classmethod
    def normalize_group_claim(cls, value: str) -> str:
        normalized = value.strip().strip("/")
        if not normalized:
            raise ValueError("group_claim must not be empty")
        return normalized

    @field_validator("group_value_template", mode="after")
    @classmethod
    def validate_group_value_template(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("group_value_template must not be empty")
        try:
            rendered = normalized.format(
                project="project-name",
                project_name="Project Name",
                role="member",
            )
        except KeyError as exc:
            raise ValueError(
                "group_value_template supports placeholders: project, project_name, role"
            ) from exc
        if rendered == normalized:
            raise ValueError("group_value_template must contain at least one placeholder")
        return normalized


class ObservabilitySettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    log_level: str = "INFO"
    http_addr: str = "0.0.0.0:8080"


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    openstack: OpenStackSettings = Field(default_factory=OpenStackSettings)
    controller: ControllerSettings = Field(default_factory=ControllerSettings)
    pomerium: PomeriumSettings = Field(default_factory=PomeriumSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
