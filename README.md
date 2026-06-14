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
- Derive SSH access from Authentik project group claims that are aligned with
  OpenStack project names and roles.
- Keep OpenStack as the resource source of truth.
- Generate deterministic Pomerium route configuration that is safe to reconcile
  repeatedly.
- Leave unmanaged Pomerium routes untouched.

## Route Naming And Sanitization

Routes are named from OpenStack display names because the SSH user experience is
intended to be human-readable:

```text
<vm-name>-<project-name>
```

Both parts are sanitized before they are used in a route:

- lowercase only
- `a-z` and `0-9`
- invalid characters become `-`
- repeated hyphens collapse
- leading and trailing hyphens are trimmed
- an empty result becomes `unknown`

For example, an instance named `Web 01` in a project named `Armel Test` becomes:

```text
web-01-armel-test
```

The same sanitization is applied to the default Authentik claim values generated
from `pomerium.group_value_template`:

```text
openstack:{project}:{role}
```

With the default template, project `Armel Test` and role `member` produce:

```text
openstack:armel-test:member
```

The raw OpenStack names and IDs are still preserved in generated route metadata:

```text
mustelinet.io/source-id
mustelinet.io/project-id
mustelinet.io/project-name
mustelinet.io/project-slug
mustelinet.io/instance-name
mustelinet.io/region
```

The controller's stable identity is `<region>:<openstack-instance-id>`, not the
sanitized route name. This lets the reconciler update or delete its own route
even if the display name changes. Route name collisions are still an operational
configuration problem, so Mustelinet should avoid duplicate VM names inside the
same project.

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
  forbidden_logins:
    - root
  delete_stale_routes: true
```

OpenStack credentials are loaded by `openstacksdk`, so both `clouds.yaml` and
`OS_*` environment variables are supported.

For production multi-project discovery, use a service credential that can list
Keystone projects and Nova servers across the projects Mustelinet manages. A
project-scoped reader credential will only work for the projects and servers
visible to that token, and some clouds reject the Nova `all_projects` query
unless policy grants explicit all-project inventory access.

The production Pomerium adapter edits `pomerium.config_path`. It only manages
routes whose `description` carries the reconciler metadata marker, preserving
unmanaged routes in the same file.

## Running Locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Run one dry pass from a local OpenStack snapshot and local JSON Pomerium state:

```bash
mustelinet-reconciler \
  plan \
  --config config.example.yaml \
  --snapshot examples/snapshot.json \
  --state /tmp/mustelinet-pomerium-state.json
```

Apply the plan into the local JSON Pomerium state adapter:

```bash
mustelinet-reconciler \
  reconcile \
  --config config.example.yaml \
  --snapshot examples/snapshot.json \
  --state /tmp/mustelinet-pomerium-state.json
```

Use dry-run for the first pass against a real cloud:

```bash
mustelinet-reconciler reconcile --config config.yaml --dry-run
```

Run tests and checks:

```bash
pytest
ruff check .
ruff format --check .
mypy
```

## Docker

Build:

```bash
docker build -f docker/Dockerfile -t openstack-pomerium-nova-reconciler:latest .
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

On many Kolla control nodes, the Docker bridge cannot reach the internal API VIP
or the Pomerium upstream network. Use host networking if the reconciler needs
the same internal management-network reachability as the Kolla or Pomerium
containers:

```bash
docker run --rm --network host \
  -v /etc/openstack-pomerium-nova-reconciler/config.yaml:/etc/openstack-pomerium-nova-reconciler/config.yaml:ro \
  -v /etc/openstack/clouds.yaml:/etc/openstack/clouds.yaml:ro \
  -v /etc/pomerium/config.yaml:/etc/pomerium/config.yaml \
  ghcr.io/armeldemarsac92/openstack-pomerium-nova-reconciler:latest
```

## GitHub Artifacts

The repository publishes artifacts with GitHub Actions on pushes to `main`,
pull requests, manual dispatches, and `v*.*.*` tags.

On `main`, the workflow runs tests, Ruff, mypy, builds Python wheel/source
distributions, uploads them as workflow artifacts, and publishes a Docker image
to GitHub Container Registry:

```text
ghcr.io/armeldemarsac92/openstack-pomerium-nova-reconciler:latest
ghcr.io/armeldemarsac92/openstack-pomerium-nova-reconciler:sha-<commit>
```

On version tags such as `v0.1.0`, it also creates a GitHub Release with the
wheel, source distribution, and SHA256 checksum attached.

## User Visibility

Pomerium Native SSH route selection uses the route name as the SSH username
suffix. For the example below, users connect through the shared Pomerium SSH
endpoint with:

```bash
ssh ubuntu@web01-otterlab@ssh.mustelinet.com
```

Route discovery is outside this reconciler. In production, expose available
routes through an operator-provided route portal or a future Mustelinet API that
reads the generated Pomerium config state. OpenStack remains the VM inventory
source of truth, but Authentik remains the source of human access claims.

## Generated Route Shape

For an OpenStack VM named `web01` in project `otterlab`, the reconciler
generates a route shaped like this:

```yaml
routes:
  - from: ssh://web01-otterlab
    to: ssh://10.42.0.15:22
    policy:
      - deny:
          and:
            - ssh_username:
                is: root
      - allow:
          and:
            - claim/groups: openstack:otterlab:admin
      - allow:
          and:
            - claim/groups: openstack:otterlab:member
```

Route names always include the project: `{vm-name}-{project-name}` after slug
normalization.

The `from` value is intentionally not a per-VM DNS hostname. With stock
Pomerium Native SSH, route selection happens through the SSH username suffix,
not through SNI or a target hostname like `web01-otterlab.ssh.mustelinet.com`.

## OpenStack Permissions

The reconciler only needs read-only OpenStack inventory access:

- Keystone Identity: list/read projects visible to Mustelinet.
- Nova Compute: list/read server inventory across configured regions and target
  projects, including server ID, name, project ID, status, metadata, addresses,
  and availability zone.

The reconciler does not need permission to create, update, or delete OpenStack
servers, networks, ports, security groups, floating IPs, Keystone users,
Keystone role assignments, or Keystone projects.

Access decisions are not read from Keystone role assignments at runtime.
Authentik owns human access policy and should emit claims such as:

```text
openstack:armel-test:member
openstack:armel-test:admin
```

The OpenStack side is used to discover which projects and VMs exist. The
Pomerium policy generated for each route then checks the Authentik claim values.

## Kolla-Ansible Notes

Kolla-Ansible can install policy overrides that make a least-privilege
inventory credential possible. It does not manage this project as an OpenStack
service by default; run the reconciler as a normal container or systemd service
beside the Kolla containers.

The recommended model is:

```text
Keystone service user: pomerium-nova-reconciler
Project scope: service
Roles: mustelinet_inventory_reader
Keystone: project read/list only
Nova: server read/list across projects only
```

Create Kolla policy override files on the deployment host. Adjust role names and
base rules for your OpenStack release and policy posture.

`/etc/kolla/config/keystone/policy.yaml`:

```yaml
identity:get_project: "role:mustelinet_inventory_reader or (rule:admin_required) or (role:reader and system_scope:all) or (role:reader and domain_id:%(target.project.domain_id)s and not None:%(target.project.domain_id)s) or project_id:%(target.project.id)s"
identity:list_projects: "role:mustelinet_inventory_reader or (rule:admin_required) or (role:reader and system_scope:all) or (role:reader and domain_id:%(target.domain_id)s)"
```

`/etc/kolla/config/nova/policy.yaml`:

```yaml
os_compute_api:servers:index: "role:mustelinet_inventory_reader or rule:project_reader_or_admin"
os_compute_api:servers:detail: "role:mustelinet_inventory_reader or rule:project_reader_or_admin"
os_compute_api:servers:show: "role:mustelinet_inventory_reader or rule:project_reader_or_admin"
os_compute_api:servers:index:get_all_tenants: "role:mustelinet_inventory_reader or rule:context_is_admin"
os_compute_api:servers:detail:get_all_tenants: "role:mustelinet_inventory_reader or rule:context_is_admin"
```

The `get_all_tenants` rules are what let Nova return server inventory from every
project without granting server create, update, rebuild, delete, console,
metadata mutation, security group, or floating IP privileges.

Apply the overrides with a focused reconfigure:

```bash
kolla-ansible reconfigure \
  -i /path/to/multinode \
  -t keystone,nova \
  --configdir /etc/kolla
```

After the play finishes, confirm the relevant containers are healthy and test
the intended API surface with the reconciler credential before running the
controller.

## Application Credential

Create the custom role and assign it only to the reconciler service user in the
`service` project:

```bash
openstack role create mustelinet_inventory_reader
openstack user create --domain Default --project service --password-prompt pomerium-nova-reconciler
openstack role add --user pomerium-nova-reconciler --project service mustelinet_inventory_reader
```

Then authenticate as that service user and create a restricted application
credential. The access-rule service names are Keystone service types; confirm
them with `openstack catalog list` if your deployment uses custom types. Do not
use `--unrestricted`.

`access-rules.json`:

```json
[
  {"service": "identity", "method": "GET", "path": "/v3/projects"},
  {"service": "identity", "method": "GET", "path": "/v3/projects/*"},
  {"service": "compute", "method": "GET", "path": "/servers"},
  {"service": "compute", "method": "GET", "path": "/servers/detail"},
  {"service": "compute", "method": "GET", "path": "/servers/*"}
]
```

If your Keystone deployment evaluates application-credential access rules
against versioned compute paths, add equivalent `/v2.1/servers`,
`/v2.1/servers/detail`, and `/v2.1/servers/*` entries.

```bash
openstack application credential create \
  --role mustelinet_inventory_reader \
  --access-rules access-rules.json \
  pomerium-nova-reconciler
```

Store the returned application credential ID and secret in a root-owned
`clouds.yaml`, then mount that file into the reconciler container. The secret is
shown only once. Do not bake credentials into the image.

```yaml
clouds:
  pomerium-nova-reconciler:
    auth_type: v3applicationcredential
    auth:
      auth_url: https://openstack.example.net:5000
      application_credential_id: <id>
      application_credential_secret: <secret>
    region_name: RegionOne
    interface: internal
    identity_api_version: 3
```

### Reconciler Configuration

For a Kolla deployment that uses the policy model above, set:

```yaml
openstack:
  cloud: pomerium-nova-reconciler
  sync_statuses:
    - ACTIVE
  address_family: ipv4

pomerium:
  group_claim: groups
  group_value_template: "openstack:{project}:{role}"
  project_roles:
    - admin
    - member
  forbidden_logins:
    - root
```

Keep Authentik group naming aligned with the same slug rules. For a project
named `Armel Test`, the default generated allow claims are:

```text
openstack:armel-test:admin
openstack:armel-test:member
```

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
