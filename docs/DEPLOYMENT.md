# Atlas v0.14 Production Deployment

This guide describes the released v0.14 Compose topology. It does not replace
operator review of `.env.example`, the Compose files, runtime gates, or the
backup manifests.

## Base production topology

`compose.production.yaml` defines exactly these services:

- `atlas-core`
- `atlas-agent`
- `atlas-agent-auth-stager`
- `atlas-execution-worker`
- `atlas-execution-worker-relay`
- `atlas-execution-auth-stager`
- `atlas-core-agent-auth-stager`
- `atlas-egress-proxy`
- `mission-control`

Core and Agent run non-root with read-only roots. Agent defaults to
`ATLAS_EXECUTION_BACKEND=local` for repository execution. The packaged
`atlas-execution-worker`, `atlas-execution-worker-relay`,
`atlas-egress-proxy`, and related authentication staging are disabled by
default and require explicit, separately gated activation. When that optional
backend is activated, authenticated worker requests pass through the relay on
segmented internal networks; authentication is enforced end-to-end by the
worker together with the allowed relay-peer boundary. Worker egress uses the
pinned, allowlisted proxy. Mission Control is the base browser ingress and
defaults to loopback publication.

Required host inputs include `ATLAS_REPOSITORY_HOST_PATH`,
`ATLAS_CODEX_AUTH_HOST_PATH`, an `.env`, and the Docker-socket group through
`DOCKER_GID`. Copy the example configuration and inspect it before startup:

```bash
cp config/atlas.example.yaml config/atlas.yaml
cp .env.example .env
docker compose -f compose.production.yaml config
docker compose -f compose.production.yaml up --build -d
```

Do not commit credentials. Tracked configuration is the immutable template;
Core-managed mutable policy, provider connections, secrets, databases,
history, and knowledge live in the `atlas-data` volume. Agent and execution
worker state use their own named volumes.

## Overlays

### HTTPS and Atlas Edge

`compose.https.yaml` removes Mission Control's host port and adds
`atlas-edge` as the only browser ingress. Operators must provide the TLS
certificate/key and htpasswd paths. Edge Basic authentication is defense in
depth and is not Core mutation authority.

```bash
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  config
```

### Operator authentication

`compose.operator-auth.yaml` enables Core-owned operator sessions and requires
an operator verifier file plus exact HTTPS trusted origins. Use it only with
the HTTPS overlay. Core permissions remain separate: operational creation does
not imply `provider_intent:update`, and neither implies legacy provider-action
authority.

### Provider Intent activation

Provider Intent is not activated by the base deployment.
`compose.provider-intent-activated.yaml` requires an explicit database path and
the exact accepted legacy-import ID. When activated and available, the
schema-v2 store is authoritative only for Proxmox QEMU `monitoring-policy`.
Database presence alone never activates it.

```bash
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  -f compose.provider-intent-activated.yaml \
  config
```

## Runtime authority and safety

- Repository candidate execution is exactly `update-compose-stack`.
- Hardened operational dispatch is exactly
  `restart-service / proxmox / qemu`.
- Legacy provider actions are a separate provider-specific surface.
- Provider Intent changes monitoring policy only.
- Discovery is GET-only/read-only. V0.14 image evidence and grounding are
  informational and have no operational authority.
- The generic image collector is inactive: production registries are empty and
  no startup or scheduled collection exists.
- Backup/restore is operator maintenance tooling, not an Agent intent.

Atlas performs no automatic remediation, approval, update, deployment,
rollback, or release publication.

## Operate and validate

Use the same ordered overlay set for `config`, `up`, `down`, and inspection.
Inspect service health after startup and run the supplied runtime gates where
applicable:

```bash
./scripts/atlas-agent-codex-runtime-gate
./scripts/atlas-execution-worker-runtime-gate
```

The optional worker path is disabled by default and requires explicit,
separately gated activation. When activated, the worker accepts requests only
through the allowed relay-peer boundary, with authentication enforced
end-to-end by the worker. Do not replace runsc, network segmentation, the
read-only source, or the named workspace permission profile with root,
`CAP_SYS_ADMIN`, unconfined policies, or `danger-full-access`.

## Backup and restore through v0.14

Create a consistent online backup with:

```bash
./scripts/atlas-data-backup
```

Format v3 is the current complete Atlas Core managed-state format through
v0.14. It includes `operational_dispatch.db` as safety-authoritative no-replay
state. “Complete” covers the declared Core boundary, not the repository or
worktree, Agent state, external provider state, remote infrastructure, images,
host state, or rebuildable Discovery cache. Activated Provider Intent requires
its database and exact activation/import semantics; a not-activated generation
requires that managed database absent. Formats v1/v2 remain legacy-partial
inputs and require the restore tool's explicit new-lineage acknowledgement on
a managed-empty target.

Restore requires every container attached to the target volume to be removed:

```bash
docker compose -f compose.production.yaml down
./scripts/atlas-data-restore /path/to/atlas-data-TIMESTAMP --confirm
docker compose -f compose.production.yaml up -d
```

Use the deployment's full overlay set for `down` and `up`. The restore tool
validates manifest format, inventory, checksums, state shape, Provider Intent
activation compatibility, and transactional recovery. Do not delete its
journal or manufacture compatibility by deleting Provider Intent state.
`operator_sessions.db` is not restored as live session authority: restore
invalidates operator sessions. Uncertain operational side effects preserve
no-replay semantics; a restored operation that had been dispatching reconciles
to `outcome_unknown` where applicable rather than replaying its handler.

Compatibility is determined by the released restore code and the backup
manifest—not by directory names or old prose. Preserve a pre-activation v3
generation if rollback to a release without Provider Intent is required.

## Release lineage

Historical version-specific upgrade and rollback procedures belong to their
released tags and Git history. For v0.14, deploy the exact tag
`atlas-v0.14.0` (`4d2526e1b022c5c36eaced65bf5b71703da5d2d7`) and validate the
resolved Compose configuration before changing a running installation. This
reconciliation does not invent a cross-environment upgrade or rollback
procedure beyond the released tooling above.
