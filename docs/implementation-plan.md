# Full Implementation Plan

## Summary

Build v1 as a Docker-run Python reconciler that exposes Nova VM inventory to
Teleport as managed OpenSSH node resources, generates project-scoped Teleport
roles, and updates the Authentik OIDC connector mapping for groups shaped as
`project-{project_name}-{role}`.

VM bootstrap and Teleport CA installation are out of scope. VMs are assumed to
already run OpenSSH, trust the Teleport OpenSSH CA, and be reachable by
Teleport Proxy on port 22.

## Key Changes

- Add a production Teleport adapter using a small Go helper binary invoked by
  Python over JSON stdin/stdout.
- Keep Python as the main reconciler runtime for config, OpenStack discovery,
  planning, worker loop, CLI, logging, tests, and Docker entrypoint.
- Add Go helper commands for Teleport CRUD:
  - `list-nodes`, `upsert-node`, `delete-node`
  - `list-roles`, `upsert-role`, `delete-role`
  - `get-oidc-connector`, `upsert-oidc-connector`
  - `health`
- Use deterministic OpenSSH node identity:
  - Teleport `metadata.name`: UUIDv5 from `{region}:{openstack_instance_id}`
  - Teleport `sub_kind`: `openssh`
  - Teleport `spec.addr`: selected Nova fixed IP plus `:22`
  - Teleport `spec.hostname`: `instance.name` when unique, otherwise
    `{instance}--{project}--{region}`
- Generate two roles per OpenStack project:
  - `mustelinet-project-{project_slug}-admin`
  - `mustelinet-project-{project_slug}-member`
  - Both allow configured Linux logins and select nodes by
    `mustelinet.io/project-id`.
- Manage Authentik OIDC connector mappings:
  - `groups=project-{project_name}-admin` maps to the admin role.
  - `groups=project-{project_name}-member` maps to the member role.
  - Preserve non-managed connector mappings.
  - Only remove mappings whose value/role pair is managed by this reconciler.
- Extend config:
  - `teleport.helper_path`
  - `teleport.proxy_addr`
  - `teleport.identity_file`
  - `teleport.oidc_connector_name`
  - `teleport.default_logins`
  - `teleport.delete_stale_nodes`
  - `teleport.delete_stale_roles`
  - `openstack.cloud`
  - `openstack.regions`
  - `openstack.sync_statuses`
  - `openstack.address_family`
  - `controller.poll_interval_seconds`
  - `controller.dry_run`
- Replace the CLI shape with explicit commands:
  - `mustelinet-reconciler plan --config config.yaml`
  - `mustelinet-reconciler reconcile --config config.yaml`
  - `mustelinet-reconciler serve --config config.yaml`
  - Keep snapshot/state development flags for local tests only.
- Add Docker support for raw `docker run`:
  - Multi-stage image builds Python package and Go helper.
  - Mount `config.yaml`, `clouds.yaml`, and Teleport identity file.
  - Container command defaults to `serve`.

## Implementation Details

- Rework domain planning around three desired resource sets: OpenSSH nodes,
  project roles, and OIDC connector mappings.
- Keep planning pure and idempotent: current Teleport state plus current
  OpenStack state produces a deterministic action list.
- Add collision detection before node planning:
  - Active desired instances are grouped by display name.
  - Unique names keep the plain Nova name.
  - Colliding names use the qualified form.
- Add OpenStack address selection:
  - Prefer fixed IPv4 addresses.
  - Fall back to fixed IPv6 only if configured.
  - Skip instances without a selected SSH address and report
    `missing-ssh-address`.
- Add stale cleanup safeguards:
  - Only delete Teleport nodes with
    `mustelinet.io/managed-by=openstack-teleport-reconciler`.
  - Only delete roles with names beginning `mustelinet-project-`.
  - Only delete OIDC mappings that match generated project group and role
    names.
- Add structured reconciliation output:
  - counts for discovered projects, discovered instances, desired nodes,
    upserts, deletes, skipped, and errors.
  - JSON logs suitable for Docker collection.
- Add optional HTTP observability endpoint in `serve`:
  - `/healthz`
  - `/readyz`
  - `/metrics`
  - `/reconciliations/latest`

## Test Plan

- Unit tests:
  - node identity UUID generation
  - name collision handling
  - address selection and skip reasons
  - role generation for admin/member
  - OIDC mapping merge and cleanup preservation
  - stale node/role cleanup safeguards
- Integration tests with fakes:
  - full plan from snapshot OpenStack inventory to fake Teleport state
  - dry-run does not mutate fake Teleport state
  - reconcile applies node, role, and connector changes
- Go helper tests:
  - JSON command parsing
  - resource serialization for OpenSSH nodes, roles, and OIDC connectors
  - error mapping to stable JSON error responses
- CLI tests:
  - `plan --output json`
  - `reconcile --dry-run`
  - missing config/identity/helper failures
- Docker validation:
  - image builds locally
  - `docker run ... mustelinet-reconciler plan` works with mounted
    snapshot/config
  - health endpoint responds in `serve`

## Assumptions

- VMs already trust the Teleport OpenSSH CA; this project will not install or
  rotate CA trust on guests.
- Teleport Proxy can reach VM selected fixed IPs on port 22; network plumbing
  is outside this reconciler.
- Authentik emits group claims named `project-{project_name}-admin` and
  `project-{project_name}-member`.
- OpenStack project names are acceptable for Authentik group names after slug
  normalization.
- The reconciler may mutate the configured Teleport OIDC connector, but only
  managed `claims_to_roles` entries.
- The first runtime target is raw Docker on your nodes, not Kubernetes, Kolla
  packaging, or systemd-managed host Python.
