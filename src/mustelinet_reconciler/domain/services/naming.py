from __future__ import annotations

import re


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "unknown"


def qualified_hostname(instance_name: str, project_name: str, region: str) -> str:
    return f"{slugify(instance_name)}--{slugify(project_name)}--{slugify(region)}"


def project_role_name(project_name: str, role: str) -> str:
    return f"mustelinet-project-{slugify(project_name)}-{slugify(role)}"


def project_group_name(project_name: str, role: str) -> str:
    return f"project-{slugify(project_name)}-{slugify(role)}"
