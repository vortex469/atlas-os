# Atlas Production Deployment and v0.15.0 Acceptance Record

This guide describes the released v0.15.0 Compose topology and its read-only
acceptance record. It does not replace
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
- The v0.15 image-grounding GET and Mission Control panel are informational;
  image grounding grants no deployment or execution authority and adds no
  action controls.
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

## Backup and restore through v0.17

Create a consistent online backup with:

```bash
./scripts/atlas-data-backup
```

Format v3 remains the current closed Atlas Core managed-state format through
v0.17. It includes `operational_dispatch.db` as safety-authoritative no-replay
state. “Complete” covers the declared Core boundary, not the repository or
worktree, Agent state, external provider state, remote infrastructure, images,
host state, or rebuildable Discovery cache. Activated Provider Intent requires
its database and exact activation/import semantics; a not-activated generation
requires that managed database absent. Formats v1/v2 remain legacy-partial
inputs and require the restore tool's explicit new-lineage acknowledgement on
a managed-empty target.

The independent v0.17 `installation_destination_selections.db` store is
operator-maintenance metadata and is not automatically included in backup
format v3. Preserve or remove it by an explicit maintenance procedure during a
downgrade; older code does not consume it. Do not restore it as installation,
approval, candidate, or execution authority. Ephemeral installation interests
and the assessment retry cache are process memory and are never restored.

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

## v0.15 release validation

P0 through P5 and production acceptance are complete. Atlas v0.15.0 is
released as `atlas-v0.15.0` at
`850480ce6c5f86a5bf4a783e33f7e08a7f29a2ab`. Release validation required
Quality gates (`atlas-agent`, `atlas-core`, and `mission-control`) plus Container
release gate (`Container integration (runc; no gVisor proof)`), with each
workflow `headSha` exactly equal to the validated candidate. The local container
commands were:

```bash
ATLAS_CONTAINER_GATE_MODE=github-integration ./scripts/container-release-gate
./scripts/container-release-gate
```

The second invocation is the production runsc proof. Detailed evidence and any
items not captured for an earlier candidate remain recorded in the release
checklist; release status does not retroactively complete missing evidence.

The production-acceptance protocol is read-only: GET Home Assistant image grounding and
expect `grounded`; GET Frigate image grounding and expect
`no_deployment_binding`; GET a recorded known-absent item and expect a
sanitized 404; visually confirm both advisory states in Mission Control. Issue
no `POST`, `PUT`, `PATCH`, or `DELETE`, and cause no mutation, execution,
proposal, candidate, approval, workflow, provider, worker, or repository action.

During the same recorded acceptance interval, prove collector inactivity
without activating it: empty production registries; no enablement in rendered
configuration; no startup, scheduled/background, or request-time acquisition;
no correlated GHCR acquisition traffic; no runtime Sigstore verification; no
collector invocation; and no evidence refresh.

Rollback is to the prior accepted `atlas-v0.14.0` image/configuration at
`4d2526e1b022c5c36eaced65bf5b71703da5d2d7`. No data migration, evidence
rollback, side-effect replay, action/dispatch recreation, or automated
remediation is required.
