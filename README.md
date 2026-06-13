# openstack-teleport-reconciler

`openstack-teleport-reconciler` is a polling controller for Mustelinet. It
discovers OpenStack projects and Nova instances, then maintains generated
Teleport SSH access resources.

OpenStack projects and VMs are the source of truth. Teleport resources are
generated state.

```text
Keystone projects + Nova instances
  -> openstack-teleport-reconciler
  -> Teleport node resources and labels
  -> tsh login / tsh ssh ubuntu@web01
```

## Goals

- Let users run `tsh login` and `tsh ssh ubuntu@web01`.
- Avoid public IPv4 addresses, user-managed SSH keys, and manual bastions.
- Derive access from Authentik groups, Teleport roles, and OpenStack project
  membership.
- Keep OpenStack as the resource source of truth.
- Make reconciliation deterministic, auditable, and safe to run repeatedly.

## Architecture

The project follows the same layered shape as the companion
`openstack-fip-dns-reconciler` project:

```text
endpoints/        CLI and worker loop
application/      use cases and repository ports
domain/           pure models, label generation, planning rules
infrastructure/   OpenStack, Teleport, file, and memory adapters
config/           typed settings and YAML loading
observability/    logging setup
```

Application services depend on repository protocols, not OpenStack SDK or
Teleport client classes. Infrastructure adapters map provider resources into
domain models.

## Repository Layout

```text
src/mustelinet_reconciler/
  application/
  config/
  domain/
  endpoints/
  infrastructure/
  observability/
deploy/
docker/
docs/
  architecture.md
examples/
  snapshot.json
tests/
```

## Configuration

Start from:

```bash
cp config.example.yaml config.yaml
```

Minimal local example:

```yaml
openstack:
  cloud: admin

controller:
  poll_interval_seconds: 15
  dry_run: false

teleport:
  managed_by: openstack-teleport-reconciler
  default_logins:
    - ubuntu
  sync_statuses:
    - ACTIVE
  delete_stale_nodes: true
```

OpenStack credentials are loaded by `openstacksdk`, so both `clouds.yaml` and
`OS_*` environment variables are supported.

## Local Usage

Run one dry pass from a local OpenStack snapshot and a local JSON Teleport state
file:

```bash
PYTHONPATH=src python -m mustelinet_reconciler \
  --config config.example.yaml \
  --snapshot examples/snapshot.json \
  --state /tmp/mustelinet-teleport-state.json \
  --once \
  --dry-run
```

Apply the plan into the local JSON Teleport state adapter:

```bash
PYTHONPATH=src python -m mustelinet_reconciler \
  --config config.example.yaml \
  --snapshot examples/snapshot.json \
  --state /tmp/mustelinet-teleport-state.json \
  --once
```

Run tests and checks:

```bash
PYTHONPATH=src python -m unittest discover -s tests
ruff check .
ruff format --check .
mypy
```

## Production Adapter Direction

The OpenStack infrastructure adapter reads Keystone projects and Nova instances
through OpenStack application credentials. The Teleport production adapter
should be the only place that knows whether the deployment uses Teleport API
resources, `tctl`, Kubernetes custom resources, or another deployment-specific
mechanism.

See [docs/architecture.md](docs/architecture.md) for the full architecture and
operational design.
