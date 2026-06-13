from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from mustelinet_reconciler.application.services.reconciliation_service import ReconciliationService
from mustelinet_reconciler.config.loader import load_settings
from mustelinet_reconciler.domain.models.reconciliation_plan import (
    ReconciliationAction,
    ReconciliationPlan,
    SkippedInstance,
)
from mustelinet_reconciler.domain.services.node_builder import TeleportNodeBuilder
from mustelinet_reconciler.domain.services.reconciliation_planner import ReconciliationPlanner
from mustelinet_reconciler.endpoints.worker import run_worker
from mustelinet_reconciler.infrastructure.openstack.connection_factory import create_connection
from mustelinet_reconciler.infrastructure.openstack.keystone_project_repository import (
    KeystoneProjectRepository,
)
from mustelinet_reconciler.infrastructure.openstack.nova_instance_repository import (
    NovaInstanceRepository,
)
from mustelinet_reconciler.infrastructure.snapshot import (
    SnapshotInstanceRepository,
    SnapshotProjectRepository,
)
from mustelinet_reconciler.infrastructure.teleport.json_node_repository import (
    JsonOIDCConnectorRepository,
    JsonTeleportNodeRepository,
    JsonTeleportRoleRepository,
)
from mustelinet_reconciler.observability.logging_config import configure_logging
from mustelinet_reconciler.domain.services.role_builder import TeleportRoleBuilder


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = load_settings(args.config)
    configure_logging(settings.observability.log_level)

    dry_run = settings.controller.dry_run or args.dry_run
    service = _build_service(args, settings)

    if args.once:
        plan = service.reconcile(dry_run=dry_run)
        _print_plan(plan, output=args.output, dry_run=dry_run)
        return 0

    run_worker(
        service=service,
        poll_interval_seconds=settings.controller.poll_interval_seconds,
        dry_run=dry_run,
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mustelinet-reconciler")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--once", action="store_true", help="Run one reconciliation pass and exit")
    parser.add_argument("--dry-run", action="store_true", help="Plan without applying changes")
    parser.add_argument("--snapshot", type=Path, help="JSON OpenStack inventory snapshot")
    parser.add_argument("--state", type=Path, help="JSON Teleport inventory state file")
    parser.add_argument("--output", choices=("text", "json"), default="text")
    return parser


def _build_service(args: argparse.Namespace, settings: Any) -> ReconciliationService:
    if args.snapshot is None:
        connection = create_connection(settings.openstack.cloud)
        projects = KeystoneProjectRepository(connection)
        instances = NovaInstanceRepository(connection, settings.openstack.regions)
    else:
        projects = SnapshotProjectRepository(args.snapshot)
        instances = SnapshotInstanceRepository(args.snapshot)

    if args.state is None:
        raise SystemExit("--state is required until the production Teleport adapter is configured")

    nodes = JsonTeleportNodeRepository(args.state)
    roles = JsonTeleportRoleRepository(args.state)
    oidc = JsonOIDCConnectorRepository(args.state)
    node_builder = TeleportNodeBuilder(settings.openstack, settings.teleport)
    role_builder = TeleportRoleBuilder(settings.teleport)
    planner = ReconciliationPlanner(settings.openstack, settings.teleport, node_builder, role_builder)
    return ReconciliationService(projects, instances, nodes, roles, oidc, planner, settings.teleport)


def _print_plan(plan: ReconciliationPlan, *, output: str, dry_run: bool) -> None:
    if output == "json":
        print(json.dumps(_plan_to_json(plan), indent=2, sort_keys=True))
        return

    verb = "planned" if dry_run else "applied"
    lines = [f"{verb}: {len(plan.actions)} action(s), {len(plan.skipped)} skipped instance(s)"]
    for action in plan.actions:
        identity = action.resource.identity
        lines.append(f"- {action.kind}: {action.resource_kind} {identity} ({action.reason})")
    for skipped in plan.skipped:
        lines.append(f"- skip: {skipped.instance_id} project={skipped.project_id} ({skipped.reason})")
    print("\n".join(lines))


def _plan_to_json(plan: ReconciliationPlan) -> dict[str, Any]:
    return {
        "actions": [_action_to_json(action) for action in plan.actions],
        "skipped": [_skipped_to_json(skipped) for skipped in plan.skipped],
    }


def _action_to_json(action: ReconciliationAction) -> dict[str, Any]:
    resource = asdict(action.resource)
    if hasattr(action.resource, "labels"):
        resource["labels"] = dict(action.resource.labels)
    if hasattr(action.resource, "node_labels"):
        resource["node_labels"] = dict(action.resource.node_labels)
    if hasattr(action.resource, "logins"):
        resource["logins"] = list(action.resource.logins)
    return {
        "kind": action.kind.value,
        "resource_kind": action.resource_kind.value,
        "reason": action.reason,
        "resource": resource,
    }


def _skipped_to_json(skipped: SkippedInstance) -> dict[str, str]:
    return {
        "instance_id": skipped.instance_id,
        "project_id": skipped.project_id,
        "reason": skipped.reason,
    }
