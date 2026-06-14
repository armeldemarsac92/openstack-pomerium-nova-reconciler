from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import fields
from pathlib import Path
from typing import Any

from mustelinet_reconciler.application.ports.instance_repository import InstanceRepository
from mustelinet_reconciler.application.ports.pomerium_route_repository import (
    PomeriumRouteRepository,
)
from mustelinet_reconciler.application.ports.project_repository import ProjectRepository
from mustelinet_reconciler.application.services.reconciliation_service import ReconciliationService
from mustelinet_reconciler.config.loader import load_settings
from mustelinet_reconciler.domain.models.reconciliation_plan import (
    ReconciliationAction,
    ReconciliationPlan,
    SkippedInstance,
)
from mustelinet_reconciler.domain.services.reconciliation_planner import ReconciliationPlanner
from mustelinet_reconciler.domain.services.route_builder import PomeriumRouteBuilder
from mustelinet_reconciler.endpoints.worker import RuntimeState, run_worker, start_http_server
from mustelinet_reconciler.infrastructure.openstack.connection_factory import create_connection
from mustelinet_reconciler.infrastructure.openstack.keystone_project_repository import (
    KeystoneProjectRepository,
)
from mustelinet_reconciler.infrastructure.openstack.nova_instance_repository import (
    NovaInstanceRepository,
)
from mustelinet_reconciler.infrastructure.pomerium.config_repository import (
    PomeriumConfigRouteRepository,
)
from mustelinet_reconciler.infrastructure.pomerium.json_route_repository import (
    JsonPomeriumRouteRepository,
)
from mustelinet_reconciler.infrastructure.snapshot import (
    SnapshotInstanceRepository,
    SnapshotProjectRepository,
)
from mustelinet_reconciler.observability.logging_config import configure_logging


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = load_settings(args.config)
    configure_logging(settings.observability.log_level)

    service = _build_service(args, settings)

    if args.command == "plan":
        plan = service.plan()
        _print_plan(plan, output=args.output, applied=False)
        return 0

    if args.command == "reconcile":
        dry_run = settings.controller.dry_run or args.dry_run
        plan = service.reconcile(dry_run=dry_run)
        _print_plan(plan, output=args.output, applied=not dry_run)
        return 0

    dry_run = settings.controller.dry_run or args.dry_run
    state = RuntimeState()
    start_http_server(settings.observability.http_addr, state)
    run_worker(
        service=service,
        poll_interval_seconds=settings.controller.poll_interval_seconds,
        dry_run=dry_run,
        state=state,
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mustelinet-reconciler")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "reconcile", "serve"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--config", type=Path, default=Path("config.yaml"))
        subparser.add_argument("--snapshot", type=Path, help="JSON OpenStack inventory snapshot")
        subparser.add_argument("--state", type=Path, help="JSON Pomerium route state file")
        subparser.add_argument(
            "--dry-run",
            action="store_true",
            help="Plan without applying changes",
        )
        subparser.add_argument("--output", choices=("text", "json"), default="text")
    return parser


def _build_service(args: argparse.Namespace, settings: Any) -> ReconciliationService:
    if args.snapshot is None:
        connection = create_connection(settings.openstack.cloud)
        projects: ProjectRepository = KeystoneProjectRepository(connection)
        instances: InstanceRepository = NovaInstanceRepository(
            connection,
            settings.openstack.regions,
        )
    else:
        projects = SnapshotProjectRepository(args.snapshot)
        instances = SnapshotInstanceRepository(args.snapshot)

    if args.state is None:
        routes: PomeriumRouteRepository = PomeriumConfigRouteRepository(
            settings.pomerium.config_path
        )
    else:
        routes = JsonPomeriumRouteRepository(args.state)
    route_builder = PomeriumRouteBuilder(settings.openstack, settings.pomerium)
    planner = ReconciliationPlanner(settings.openstack, settings.pomerium, route_builder)
    return ReconciliationService(projects, instances, routes, planner, settings.pomerium)


def _print_plan(plan: ReconciliationPlan, *, output: str, applied: bool) -> None:
    if output == "json":
        print(json.dumps(_plan_to_json(plan), indent=2, sort_keys=True))
        return

    verb = "applied" if applied else "planned"
    lines = [f"{verb}: {len(plan.actions)} action(s), {len(plan.skipped)} skipped instance(s)"]
    for action in plan.actions:
        identity = action.resource.identity
        lines.append(f"- {action.kind}: {action.resource_kind} {identity} ({action.reason})")
    for skipped in plan.skipped:
        lines.append(
            f"- skip: {skipped.instance_id} project={skipped.project_id} ({skipped.reason})"
        )
    print("\n".join(lines))


def _plan_to_json(plan: ReconciliationPlan) -> dict[str, Any]:
    return {
        "actions": [_action_to_json(action) for action in plan.actions],
        "skipped": [_skipped_to_json(skipped) for skipped in plan.skipped],
    }


def _action_to_json(action: ReconciliationAction) -> dict[str, Any]:
    resource = {
        field.name: _json_value(getattr(action.resource, field.name))
        for field in fields(action.resource)
    }
    if hasattr(action.resource, "from_url"):
        resource["from_url"] = action.resource.from_url
    if hasattr(action.resource, "to_url"):
        resource["to_url"] = action.resource.to_url
    if hasattr(action.resource, "policy"):
        resource["policy"] = _json_value(action.resource.policy)
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


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value
