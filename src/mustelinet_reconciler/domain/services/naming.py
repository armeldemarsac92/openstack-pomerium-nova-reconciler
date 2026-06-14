from __future__ import annotations

import re


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "unknown"


def project_route_name(instance_name: str, project_name: str) -> str:
    return f"{slugify(instance_name)}-{slugify(project_name)}"


def project_role_name(project_name: str, role: str, prefix: str = "mustelinet-project-") -> str:
    return f"{prefix}{slugify(project_name)}-{slugify(role)}"


def project_group_value(project_name: str, role: str, template: str) -> str:
    return template.format(
        project=slugify(project_name),
        project_name=project_name,
        role=slugify(role),
    )
