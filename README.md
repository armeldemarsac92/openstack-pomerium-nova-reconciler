# openstack-pomerium-nova-reconciler

`openstack-pomerium-nova-reconciler` is a polling controller for Mustelinet. It
discovers OpenStack projects and Nova instances, then maintains generated
Pomerium Native SSH routes.

OpenStack projects and VMs are the source of truth. Pomerium routes are
generated access state.

```text
Keystone projects + Nova instances
  -> mustelinet-reconciler
  -> Pomerium ssh:// routes with Authentik claim policy
  -> ssh ubuntu@web01-otterlab@pomerium.example.com
```

## Goals

- Avoid public VM SSH exposure, user-managed bastions, and per-VM SSH route
  handwork.
- Derive SSH access from Authentik project group claims and OpenStack project
  membership.
- Keep OpenStack as the resource source of truth.
- Generate deterministic Pomerium route configuration that is safe to reconcile
  repeatedly.
- Leave unmanaged Pomerium routes untouched.

## Architecture

The project follows the same layered shape as the companion
`openstack-fip-dns-reconciler` project:

```text
endpoints/        CLI and worker loop
application/      use cases and repository ports
domain/           pure models, route generation, planning rules
infrastructure/   OpenStack, Pomerium config, JSON state, and memory adapters
config/           typed settings and YAML loading
observability/    logging setup
```

Application services depend on repository protocols, not OpenStack SDK or
Pomerium config details. Infrastructure adapters map provider resources into
domain models.

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

pomerium:
  config_path: /etc/pomerium/config.yaml
  managed_by: openstack-pomerium-nova-reconciler
  route_name_prefix: ""
  group_claim: groups
  group_value_template: "openstack:{project}:{role}"
  project_roles:
    - admin
    - member
  allowed_logins:
    - ubuntu
  delete_stale_routes: true
```

OpenStack credentials are loaded by `openstacksdk`, so both `clouds.yaml` and
`OS_*` environment variables are supported.

The production Pomerium adapter edits `pomerium.config_path`. It only manages
routes whose `description` carries the reconciler metadata marker, preserving
unmanaged routes in the same file.

## Local Usage

Run one dry pass from a local OpenStack snapshot and local JSON Pomerium state:

```bash
PYTHONPATH=src python -m mustelinet_reconciler \
  plan \
  --config config.example.yaml \
  --snapshot examples/snapshot.json \
  --state /tmp/mustelinet-pomerium-state.json
```

Apply the plan into the local JSON Pomerium state adapter:

```bash
PYTHONPATH=src python -m mustelinet_reconciler \
  reconcile \
  --config config.example.yaml \
  --snapshot examples/snapshot.json \
  --state /tmp/mustelinet-pomerium-state.json
```

Run in Docker against real OpenStack and a mounted Pomerium config file:

```bash
docker run --rm \
  -v "$PWD/config.yaml:/etc/openstack-pomerium-nova-reconciler/config.yaml:ro" \
  -v "$HOME/.config/openstack/clouds.yaml:/root/.config/openstack/clouds.yaml:ro" \
  -v "$PWD/pomerium.yaml:/etc/pomerium/config.yaml" \
  -p 8080:8080 \
  openstack-pomerium-nova-reconciler:latest
```

Run tests:

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

## Generated Route Shape

For an OpenStack VM named `web01` in project `otterlab`, the reconciler
generates a route shaped like this:

```yaml
routes:
  - from: ssh://web01-otterlab
    to: ssh://10.42.0.15:22
    policy:
      - allow:
          and:
            - claim/groups: openstack:otterlab:admin
            - ssh_username:
                is: ubuntu
      - allow:
          and:
            - claim/groups: openstack:otterlab:member
            - ssh_username:
                is: ubuntu
```

Route names always include the project: `{vm-name}-{project-name}` after slug
normalization.

## Production Behavior

The OpenStack infrastructure adapter reads Keystone projects and Nova instances
through OpenStack application credentials. The Pomerium adapter edits the
configured Pomerium YAML file and relies on Pomerium hot reload or the operator's
deployment rollout mechanism to apply the changed route set.

VM bootstrap is intentionally out of scope for this reconciler. VMs must already
run OpenSSH, trust the Pomerium SSH User CA for native SSH access, and be
reachable by Pomerium on their selected fixed IP and port 22.

See [docs/architecture.md](docs/architecture.md) for the full architecture and
operational design.
