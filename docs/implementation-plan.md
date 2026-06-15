# Pomerium Migration Implementation Plan

## Summary

Manage Pomerium Native SSH routes from OpenStack inventory. OpenStack remains
the resource source of truth, and Authentik project group claims remain the
authorization source.

VM bootstrap and Pomerium SSH User CA installation are out of scope. VMs are
assumed to already run OpenSSH, trust the Pomerium User CA, and be reachable by
Pomerium on port 22.

## Implemented Slices

1. Replace access settings.
   - Add `pomerium.config_path`.
   - Add `pomerium.managed_by`.
   - Add `pomerium.group_claim`.
   - Add `pomerium.group_value_template`.
   - Add `pomerium.project_roles`.
   - Add `pomerium.forbidden_logins`.
   - Add `pomerium.delete_stale_routes`.
   - Add `pomerium.cookie_expire`.
   - Add `pomerium.route_timeout`.
   - Add `pomerium.route_idle_timeout`.

2. Replace domain resources.
   - Add `ManagedSSHRoute`.
   - Generate `from: ssh://{vm-name}-{project-name}`.
   - Generate `to: ssh://{selected_floating_ip}:22`.
   - Generate long-lived route `timeout` and `idle_timeout` fields.
   - Generate route policy from `claim/{group_claim}` plus a `deny` rule for
     forbidden SSH usernames.
   - Preserve stable identity as `region:openstack_instance_id`.

3. Replace planner behavior.
   - Remove managed node, role, and OIDC connector mapping planning.
   - Plan only managed Pomerium SSH route upserts and deletes.
   - Keep instance filtering and address selection.

4. Replace application repository boundary.
   - Add `PomeriumRouteRepository`.
   - Wire `ReconciliationService` to list/upsert/delete routes.
   - Keep CLI commands: `plan`, `reconcile`, and `serve`.

5. Add adapters.
   - Add JSON state adapter for local tests and dry runs.
   - Add Pomerium YAML config adapter for self-hosted Pomerium Core.
   - Preserve unmanaged routes in the same Pomerium config file.
   - Mark managed routes in `description` with reconciler metadata.

6. Update runtime packaging.
   - Remove Go helper build stage.
   - Keep Python-only Docker image.
   - Keep `mustelinet-reconciler` as the CLI entrypoint.

7. Update tests.
   - Cover route generation.
   - Cover Pomerium policy generation.
   - Cover stale route deletion and deletion disablement.
   - Cover JSON and YAML route repositories.
   - Cover service-level reconciliation with fakes.

## Current Generated Route Shape

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

Route names always include the project name after slug normalization:
`{vm-name}-{project-name}`.

## Remaining Work

1. Validate against a real Pomerium Native SSH deployment.
   - Confirm route config is accepted by the running Pomerium version.
   - Confirm Authentik `groups` claim values match
     `openstack:{project}:{role}`.
   - Confirm `ssh_username` deny policy blocks root while allowing project users
     to choose valid non-root Linux accounts.

2. Validate VM bootstrap.
   - Install the Pomerium User CA trust through managed image, vendordata, or
     config-drive.
   - Confirm `authorized_keys` is not required for platform-managed access.
   - Confirm Pomerium can reach fixed VM addresses on port 22.

3. Add Kubernetes adapter if Pomerium runs in Kubernetes.
   - Reconcile a dedicated ConfigMap or generated config fragment.
   - Add leader election before multiple replicas write the same ConfigMap.

4. Add stronger observability.
   - Prometheus counters for discovered, desired, upserted, deleted, skipped,
     and failed resources.
   - Structured JSON logs.
   - Last reconciliation status endpoint with error details.

5. Add production safety checks.
   - Dry-run diff summary before destructive deletes.
   - Optional maximum delete percentage per reconciliation.
   - Config file backup before write.
   - Pomerium config validation command hook before atomic replacement.

6. Add optional Enterprise API adapter.
   - Use Pomerium Enterprise gRPC API for route CRUD where available.
   - Keep the Core YAML adapter as the self-hosted baseline.

## Assumptions

- Pomerium Native SSH Access is the target SSH workflow, not TCP tunneling.
- Authentik emits a claim named `groups` containing project group values.
- Group values follow `openstack:{project_slug}:{role}` by default.
- `admin` and `member` project roles both grant SSH route access by default.
- OpenStack project names are acceptable for group names after slug
  normalization.
- The first runtime target is raw Docker on operator-managed nodes, with a
  writable mounted Pomerium config file.
