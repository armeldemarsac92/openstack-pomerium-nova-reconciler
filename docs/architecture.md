# Mustelinet SSH Access Reconciler Architecture

## High-Level Architecture

Mustelinet provides SSH access through Teleport while OpenStack remains the
source of truth for resources.

```text
User
  -> Authentik OIDC
  -> Teleport login and short-lived SSH certificate
  -> Teleport proxy
  -> VM Teleport SSH service or OpenSSH configured with Teleport CA
```

The reconciler watches OpenStack projects and instances, builds the desired
Teleport inventory and labels, applies changes idempotently, and garbage
collects resources that no longer exist in OpenStack.

The preferred VM access path is a VM-side Teleport service that joins the
cluster over outbound connectivity. That preserves the requirement that VMs do
not expose port 22 publicly and users do not configure bastions or VM IPs.

## Component Responsibilities

Authentik:

- Owns human identities.
- Emits OIDC claims for email, stable user id, project groups, and project
  roles.
- Uses group naming that can be mapped deterministically to OpenStack projects,
  such as `project-otterlab-admin`.

OpenStack:

- Owns projects, instances, regions, and project membership.
- Provides Keystone and Nova APIs for discovery.
- Injects provider-controlled cloud-init, vendordata, config-drive content, or
  managed image content for VM bootstrap.

Teleport:

- Owns login sessions, short-lived SSH certificates, audit events, and access
  enforcement.
- Trusts Authentik as OIDC identity provider.
- Uses roles derived from Authentik groups and resource labels.
- Does not own the OpenStack resource catalog.

Reconciler:

- Reads OpenStack projects and instances.
- Builds desired Teleport node labels and derived access resources.
- Upserts changed resources.
- Deletes stale resources that it manages.
- Emits structured reconciliation results for observability.

VM bootstrap:

- Installs Teleport SSH service or configures OpenSSH certificate trust.
- Injects the Teleport SSH CA trust path.
- Configures node identity, labels, and join configuration from provider-owned
  metadata.
- Avoids user-managed `authorized_keys` for platform-managed users.

## Reconciliation Workflow

1. Load configuration and credentials.
2. Fetch enabled Keystone projects.
3. Fetch Nova instances for configured regions.
4. Filter instances by supported lifecycle state, normally `ACTIVE`.
5. Build desired Teleport resources with stable identities:
   `region:openstack_instance_id`.
6. Add labels such as project id, project name, region, instance id,
   environment, and managed-by marker.
7. Read current Teleport resources that have the managed-by marker.
8. Compare desired and current resources by stable identity and fingerprint.
9. Upsert missing or changed resources.
10. Delete stale managed resources when stale deletion is enabled.
11. Emit metrics, logs, and reconciliation summary.

The loop is safe to run repeatedly. A future event-driven path can trigger the
same reconciliation logic from Nova notifications, Keystone project events, or
message-bus events. Polling remains the correctness fallback.

## Security Model

Identity:

- Authentik is the human identity source.
- Teleport consumes Authentik OIDC claims.
- Stable identifiers should use immutable ids, not display names.

Authorization:

- Teleport roles are derived from Authentik groups and OpenStack project
  membership.
- Node selectors use reconciler-managed labels.
- Project admin and member groups should map to different allowed Linux logins,
  review requirements, or session policies as needed.

SSH authentication:

- Users receive short-lived SSH certificates from Teleport.
- VMs trust the Teleport SSH CA.
- Platform-managed accounts do not depend on per-user `authorized_keys`.

Reconciler credentials:

- OpenStack credentials should be read-only for Keystone and Nova inventory.
- Teleport credentials should be scoped to the resources the reconciler manages.
- All reconciler-managed resources carry a `managed-by` label to prevent
  accidental deletion of manually owned resources.

Audit:

- Teleport records login and session activity.
- Reconciler logs each upsert/delete with source id, project id, region, and
  reason.
- OpenStack remains the audit source for resource lifecycle.

## Data Model

Project:

- `id`
- `name`
- `domain_id`
- `enabled`
- `metadata`

Instance:

- `id`
- `name`
- `project_id`
- `status`
- `region`
- `availability_zone`
- `addresses`
- `metadata`

Managed Teleport node:

- `name`
- `source_id`
- `project_id`
- `project_name`
- `region`
- `labels`
- `logins`
- `address`
- `port`

Stable identity:

```text
region:openstack_instance_id
```

Required labels:

```text
mustelinet.io/managed-by
mustelinet.io/source
mustelinet.io/source-id
mustelinet.io/project-id
mustelinet.io/project-name
mustelinet.io/region
mustelinet.io/instance-name
mustelinet.io/status
```

## API Design Proposals

Python ports:

```python
class OpenStackInventory(Protocol):
    def list_projects(self) -> Sequence[Project]: ...
    def list_instances(self) -> Sequence[Instance]: ...

class TeleportInventory(Protocol):
    def list_managed_nodes(self, managed_by: str) -> Sequence[ManagedNode]: ...
    def upsert_node(self, node: ManagedNode) -> None: ...
    def delete_node(self, node: ManagedNode) -> None: ...
```

CLI:

```bash
mustelinet-reconciler plan
mustelinet-reconciler reconcile
```

Future service API:

```text
GET  /healthz
GET  /readyz
GET  /metrics
POST /reconcile
GET  /reconciliations/latest
```

The public API should expose reconciliation status, not direct mutation of
OpenStack-derived resources. Mutations should flow through OpenStack.

## Failure Scenarios

OpenStack API unavailable:

- Keep existing Teleport resources unchanged.
- Mark reconciliation failed.
- Retry with backoff.

Teleport API unavailable:

- Do not advance local checkpoints.
- Retry upserts/deletes.
- Emit degraded status.

Partial apply:

- Reconciliation is idempotent, so the next run repairs missing updates.
- Each action uses stable identities and full desired state.

VM bootstrap failure:

- VM appears in OpenStack but does not become reachable through Teleport.
- Surface as node readiness drift.
- Keep OpenStack lifecycle independent from access readiness.

Project rename:

- Stable ids continue to match.
- Labels update on the next reconciliation.
- Authentik group naming needs a migration strategy if names are embedded in
  group names.

Compromised VM:

- Disable the OpenStack instance, revoke its Teleport node identity, or rotate
  join credentials.
- Teleport session audit remains available.

Reconciler bug:

- Managed-by labels constrain deletion scope.
- Dry-run planning should be available before production apply.
- Stale deletion can be disabled during incident response.

## Operational Considerations

- Run one leader per OpenStack region or use leader election for active/passive
  replicas.
- Expose counters for discovered projects, discovered instances, upserts,
  deletes, skipped instances, and failed actions.
- Include source ids in every log line.
- Keep delete safeguards enabled by default.
- Use short Teleport join token lifetimes and rotate CA material through a
  documented operational runbook.
- Prefer provider-controlled vendordata or managed images for bootstrap so users
  do not need to supply cloud-init.
- Polling is the correctness baseline; events only reduce convergence latency.

## Future Evolution Roadmap

1. Add production OpenStack adapter using application credentials.
2. Add production Teleport adapter for the chosen deployment mechanism.
3. Add Prometheus metrics and structured JSON logging.
4. Add leader election for HA deployments.
5. Add Nova/Keystone event consumers to trigger faster reconciliations.
6. Generate or validate Teleport role resources for project groups.
7. Add VM bootstrap templates for vendordata/config-drive/managed images.
8. Add multi-region inventory aggregation.
9. Extend the resource model to Kubernetes cluster discovery.
10. Extend access workflows to databases through Teleport.
