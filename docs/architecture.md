# Mustelinet Pomerium SSH Access Reconciler Architecture

## High-Level Architecture

Mustelinet provides SSH access through Pomerium Native SSH while OpenStack
remains the source of truth for resources.

```text
User
  -> SSH to user@route@pomerium
  -> Pomerium OAuth flow through Authentik
  -> Pomerium policy check against Authentik claims
  -> Pomerium-signed SSH certificate
  -> VM OpenSSH trusting the Pomerium User CA
```

The reconciler watches OpenStack projects and instances, builds the desired
Pomerium `ssh://` route set, applies changes idempotently, and garbage collects
routes that it owns when the corresponding OpenStack VM disappears.

The v1 VM access path is Pomerium Native SSH Access. VMs do not need a Pomerium
agent, but they must already trust the Pomerium SSH User CA and must be
reachable by Pomerium on their selected fixed IP and port 22.

## Component Responsibilities

Authentik:

- Owns human identities.
- Emits OIDC claims for email, stable user id, project groups, and project
  roles.
- Owns project access permissions and emits group claim values such as
  `openstack:otterlab:member`.

OpenStack:

- Owns projects, instances, regions, and project membership.
- Provides Keystone and Nova APIs for discovery.
- Injects provider-controlled cloud-init, vendordata, config-drive content, or
  managed image content for VM bootstrap.

Pomerium:

- Owns OAuth session handling, SSH route policy enforcement, SSH certificate
  signing, and SSH access logs.
- Trusts Authentik as the identity provider.
- Evaluates route policy using Authentik claims such as `claim/groups`.
- Does not own the OpenStack resource catalog.

Reconciler:

- Reads OpenStack projects and instances.
- Builds desired Pomerium SSH route definitions.
- Upserts changed managed routes into the configured Pomerium YAML config.
- Deletes stale managed routes when stale deletion is enabled.
- Emits structured reconciliation results for observability.

VM bootstrap:

- Is out of scope for this reconciler.
- Must configure OpenSSH to trust the Pomerium SSH User CA.
- Must avoid per-user `authorized_keys` for platform-managed users where the
  platform owns SSH access policy.

## Reconciliation Workflow

1. Load configuration and credentials.
2. Fetch enabled Keystone projects.
3. Fetch Nova instances for configured regions.
4. Filter instances by supported lifecycle state, normally `ACTIVE`.
5. Select the preferred fixed SSH address from Nova network data.
6. Build desired Pomerium SSH routes with stable identities:
   `region:openstack_instance_id`.
7. Generate `from: ssh://{vm-name}-{project-name}` and
   `to: ssh://{fixed_ip}:22`.
8. Generate per-route Pomerium policy from Authentik project group claims and
   configured Linux login names.
9. Read current Pomerium routes carrying the reconciler metadata marker.
10. Compare desired and current routes by stable identity and fingerprint.
11. Upsert missing or changed routes.
12. Delete stale managed routes when stale deletion is enabled.
13. Emit metrics, logs, and reconciliation summary.

The loop is safe to run repeatedly. A future event-driven path can trigger the
same reconciliation logic from Nova notifications, Keystone project events, or
message-bus events. Polling remains the correctness fallback.

## Security Model

Identity:

- Authentik is the human identity source.
- Pomerium consumes Authentik OIDC claims.
- Stable identifiers should use immutable ids, not display names.

Authorization:

- Pomerium route policy is derived from Authentik groups and OpenStack project
  membership.
- Authentik group claim values map directly to route allow rules:
  `claim/groups: openstack:{project_slug}:{role}`.
- Configured Linux logins are enforced with Pomerium's `ssh_username` criterion.

SSH authentication:

- Pomerium signs short-lived SSH certificates for native SSH access.
- VMs trust the Pomerium SSH User CA.
- Platform-managed accounts do not depend on per-user `authorized_keys`.

Reconciler credentials:

- OpenStack credentials should be read-only for Keystone and Nova inventory.
- Pomerium config access should be limited to the route configuration file or
  ConfigMap owned by the operator.
- Reconciler-managed routes carry a metadata marker in `description` to prevent
  accidental deletion of manually owned routes.

Audit:

- Pomerium records SSH route access and authorization decisions.
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

Managed Pomerium SSH route:

- `name`
- `route_name`
- `source_id`
- `project_id`
- `project_name`
- `region`
- `group_claim`
- `allowed_groups`
- `allowed_logins`
- `address`
- `port`
- `labels`

Stable identity:

```text
region:openstack_instance_id
```

Required internal labels:

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

## API Design

Python ports:

```python
class OpenStackInventory(Protocol):
    def list_projects(self) -> Sequence[Project]: ...
    def list_instances(self) -> Sequence[Instance]: ...

class PomeriumRouteRepository(Protocol):
    def list_managed_routes(self, managed_by: str) -> Sequence[ManagedSSHRoute]: ...
    def upsert_route(self, route: ManagedSSHRoute) -> None: ...
    def delete_route(self, route: ManagedSSHRoute) -> None: ...
```

CLI:

```bash
mustelinet-reconciler plan
mustelinet-reconciler reconcile
mustelinet-reconciler serve
```

Service API:

```text
GET /healthz
GET /readyz
GET /metrics
GET /reconciliations/latest
```

The public API should expose reconciliation status, not direct mutation of
OpenStack-derived resources. Mutations should flow through OpenStack.

## Failure Scenarios

OpenStack API unavailable:

- Keep existing Pomerium routes unchanged.
- Mark reconciliation failed.
- Retry with backoff.

Pomerium config write unavailable:

- Do not partially rewrite the config.
- Retry upserts/deletes.
- Emit degraded status.

Partial apply:

- Reconciliation is idempotent, so the next run repairs missing updates.
- Each action uses stable identities and full desired state.

VM bootstrap failure:

- VM appears in OpenStack but does not become reachable through Pomerium SSH.
- Surface as route readiness drift in future health checks.
- Keep OpenStack lifecycle independent from access readiness.

Project rename:

- Stable ids continue to match.
- Route policy updates on the next reconciliation.
- Authentik group naming needs a migration strategy if names are embedded in
  group names.

Compromised VM:

- Disable the OpenStack instance, remove the route, or rotate the Pomerium SSH
  User CA trust according to the incident runbook.
- Pomerium access audit remains available.

Reconciler bug:

- Managed metadata constrains deletion scope.
- Dry-run planning is available before production apply.
- Stale deletion can be disabled during incident response.

## Operational Considerations

- Run one leader per OpenStack region or use leader election for active/passive
  replicas.
- Expose counters for discovered projects, discovered instances, upserts,
  deletes, skipped instances, and failed actions.
- Include source ids in every log line.
- Keep delete safeguards enabled by default.
- Mount the Pomerium config writable only where reconciliation should run.
- Use Pomerium hot reload or deployment rollout mechanics to pick up changed
  route config.
- Prefer provider-controlled vendordata or managed images for VM bootstrap so
  users do not need to supply cloud-init.
- Polling is the correctness baseline; events only reduce convergence latency.

## Future Evolution Roadmap

1. Validate the Pomerium Native SSH bootstrap on managed VM images.
2. Add Kubernetes ConfigMap adapter for Pomerium deployments in Kubernetes.
3. Add Prometheus metrics and structured JSON logging.
4. Add leader election for HA deployments.
5. Add Nova/Keystone event consumers to trigger faster reconciliations.
6. Add optional Pomerium Enterprise API adapter for route CRUD.
7. Add VM bootstrap templates for vendordata/config-drive/managed images.
8. Add multi-region inventory aggregation.
9. Extend the resource model to Kubernetes cluster discovery.
10. Extend access workflows to databases through Pomerium TCP routes.
