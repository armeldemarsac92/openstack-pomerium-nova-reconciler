# openstack-teleport-reconciler

`openstack-teleport-reconciler` is a polling controller for Mustelinet. It
discovers OpenStack projects and Nova instances, then maintains generated
Teleport SSH access resources.

OpenStack projects and VMs are the source of truth. Teleport resources are
generated state.

```text
Keystone projects + Nova instances
  -> openstack-teleport-reconciler
  -> Teleport OpenSSH node resources, roles, and OIDC mappings
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
teleport-helper/  native Go bridge for Teleport API resource CRUD
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
docker/
docs/
  architecture.md
  implementation-plan.md
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
  sync_statuses:
    - ACTIVE
  address_family: ipv4

controller:
  poll_interval_seconds: 15
  dry_run: false

teleport:
  helper_path: /usr/local/bin/mustelinet-teleport-helper
  proxy_addr: teleport.example.com:443
  identity_file: /etc/openstack-teleport-reconciler/teleport-identity
  oidc_connector_name: authentik
  managed_by: openstack-teleport-reconciler
  role_name_prefix: mustelinet-project-
  default_logins:
    - ubuntu
  delete_stale_nodes: true
  delete_stale_roles: true
```

OpenStack credentials are loaded by `openstacksdk`, so both `clouds.yaml` and
`OS_*` environment variables are supported.

The Teleport identity file must be a Teleport identity with permissions to read
and write managed OpenSSH node resources, managed roles, and the configured OIDC
connector.

## Local Usage

Run one dry pass from a local OpenStack snapshot and a local JSON Teleport state
file:

```bash
PYTHONPATH=src python -m mustelinet_reconciler \
  plan \
  --config config.example.yaml \
  --snapshot examples/snapshot.json \
  --state /tmp/mustelinet-teleport-state.json
```

Apply the plan into the local JSON Teleport state adapter:

```bash
PYTHONPATH=src python -m mustelinet_reconciler \
  reconcile \
  --config config.example.yaml \
  --snapshot examples/snapshot.json \
  --state /tmp/mustelinet-teleport-state.json
```

Run in Docker against real OpenStack and Teleport:

```bash
docker run --rm \
  -v "$PWD/config.yaml:/etc/openstack-teleport-reconciler/config.yaml:ro" \
  -v "$HOME/.config/openstack/clouds.yaml:/root/.config/openstack/clouds.yaml:ro" \
  -v "$PWD/teleport-identity:/etc/openstack-teleport-reconciler/teleport-identity:ro" \
  -p 8080:8080 \
  openstack-teleport-reconciler:latest
```

Run tests and checks:

```bash
PYTHONPATH=src python -m unittest discover -s tests
cd teleport-helper && GOTOOLCHAIN=auto go test ./...
ruff check .
ruff format --check .
mypy
```

## Production Behavior

The OpenStack infrastructure adapter reads Keystone projects and Nova instances
through OpenStack application credentials. The Teleport production adapter uses
the bundled Go helper to call Teleport's native Go API.

VM bootstrap is intentionally out of scope for this reconciler. VMs must already
run OpenSSH, trust the Teleport OpenSSH CA, and be reachable by Teleport Proxy on
their selected fixed IP and port 22.

See [docs/architecture.md](docs/architecture.md) for the full architecture and
operational design.
