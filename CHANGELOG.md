# Changelog

This project is under active development. Entries describe significant
operator-visible changes; Git tags remain the source of truth for exact
release boundaries.

## Unreleased

Atlas v0.9 has the theme Operational Recovery and Evidence Automation. P0
through P5 are complete. The immutable `atlas-v0.9-rc1` candidate at
`bc549ff6ab57d366205c1b9eb0c36fc2f7a61ba3` passed required CI,
`atlas-release-evidence-v1`, exact-SHA no-cache production deployment, and
sequential restart soak and is accepted for final promotion. The final
`atlas-v0.9.0` release remains pending.

### Added

- Added a deterministic read-only recovery diagnostic covering lifecycle
  consistency, Core availability, immutable correlation, transition validity,
  target replacement, outcome uncertainty, and controlled safe-next-action
  guidance.
- Added bounded, allow-listed `atlas-operational-support-bundle-v1` evidence
  with deterministic integrity/correlation digests and explicit truncation.
- Added check-only `atlas-release-evidence-v1` automation with fail-closed
  worktree, exact-SHA/tag, CI, Compose, capability, image, and secret-hygiene
  evidence.
- Added Mission Control recovery summaries, bounded enriched operational
  history, controlled filters, and local-only support-evidence preview/download.

### Safety boundary

A read-only feasibility audit rejected `restart-service / proxmox / lxc`
because no provider-authoritative, configuration-independent incarnation
identifier was available. Atlas did not synthesize identity from mutable or
reusable fields, and added no LXC candidate, selector, translation, gate,
handler, ACL, or mutation. The operational production boundary remains exactly
`restart-service / proxmox / qemu`; v0.9 adds no mutation intent or handler.

## atlas-v0.8.0 — Atlas v0.8.0 (2026-08-15)

Atlas v0.8.0 was published at
`f83cd90982d4682ce49e60308e93dc9840984211`, promoting the immutable
`atlas-v0.8-rc1` candidate at
`cf09dfe1eebbd138d37ba7144d91b893f70732fa` after required CI, exact-SHA
production deployment, and sequential service-restart soak validation.

### Added

- Added effect-aware approval presentation with explicit actionable,
  historical, superseded, and expired states and effect-specific approval
  boundaries.
- Added a unified sanitized operational lifecycle read model correlating
  provenance, planning, approvals, dispatch-barrier evidence, provider
  operation capture, verification, recovery, and terminal outcome.
- Added read-only Mission Control operational history and recovery guidance
  with no mutation retry or run-again controls.
- Added provider-neutral, read-only capability and resource-selector
  descriptors projected from existing closed capability sources.

### Changed

- Hardened HTTPS deployments so Atlas Edge is the only host-published browser
  ingress while Mission Control remains reachable on the internal Compose
  network.
- Improved expired-session, reauthentication, permission, CSRF-rotation, and
  Core-unavailable operator UX without adding automatic mutation retry.
- Added release assertions for Agent/Core/translation/registry/descriptor
  parity and lifecycle-response redaction.

The production mutation boundary remains exactly
`restart-service / proxmox / qemu`; v0.8 adds no intent or provider mutation
handler.

### RC1 validation

- Rebuilt no-cache production images from the exact RC1 checkout and proved
  Core, Agent, and Mission Control source/image parity.
- Validated the three-file production deployment, Edge-only HTTPS ingress,
  absence of a Mission Control host port, and exact operational capability
  parity for `restart-service/proxmox/qemu`.
- Restarted Agent, Core, Mission Control, and Atlas Edge sequentially; all
  services remained healthy and the accepted operational workflow remained
  terminal, verified, and lifecycle-consistent.
- Confirmed stale and historical approvals remained non-actionable, no commit
  approval appeared for the operational workflow, and lifecycle/history views
  exposed no retry or run-again control.
- Confirmed exactly-once evidence remained unchanged: one dispatch record, six
  transitions, one dispatching/barrier transition, one provider operation, one
  dispatch result, one verification success, and VM 110 `qmreboot` count `3`,
  with no new request ID and no target-fingerprint change.

## atlas-v0.7.0 — Atlas v0.7.0 (2026-08-14)

Atlas v0.7.0 was published at
`8dbc43de73dda300b50c121f19324cb5174df2a9`, promoting the immutable
`atlas-v0.7-rc1` candidate at
`5b1321091af0fc191844cdf71e9e0d919e4ea415`.

### Added

- Added the approval-gated `restart-service / proxmox / qemu` operational
  workflow, including authoritative QEMU identity, deterministic candidate
  planning, immutable action requests, exact approvals, authenticated
  Agent-to-Core dispatch, a durable exactly-once barrier, provider UPID
  capture, bounded verification, and verifier-only recovery.
- Added Core-owned operator authentication with Argon2id verifier provisioning,
  secure sessions, exact HTTPS trusted-origin enforcement, CSRF protection,
  rate limits, security audit records, and the closed
  `operational_intent:create` permission.
- Added durable operator-intent candidates and a sanitized authoritative
  resource selector. Mission Control now provides operator login and bounded
  maintenance-request pages without exposing provider commands, action IDs,
  native identities, or arbitrary parameters.
- Added one-shot sandbox and verifier-only recovery harnesses used to validate
  the operational contracts without enabling a generic execution path.

### Changed

- Provider health and intelligence collection are bounded concurrently so one
  slow provider cannot serially multiply the dashboard startup timeout.
- Production Compose supports the explicit operator-auth overlay and separate
  Agent-to-Core dispatch credential while retaining existing container
  hardening.

### Validated

- On 2026-08-14, the normal production workflow performed exactly one approved
  graceful restart of Proxmox QEMU VM 110 (`Frigate`). The workflow completed,
  the durable ledger reached `verified`, the same authoritative fingerprint was
  observed afterward, and barrier, provider-operation, and dispatch-result
  counts were each exactly one with no replay.

## atlas-v0.6.0 — Atlas v0.6.0 (2026-08-13)

Atlas v0.6.0 promotes the validated `atlas-v0.6-rc1.9` baseline and was
published as the immutable `atlas-v0.6.0` release at
`03c1e03099b0f638dc674235312a3b3e70768c2f`.

### Added

- Hardened Codex `workspace-write` execution with an immutable named permission
  profile, runsc isolation, a segmented Agent-to-worker relay, peer-bound bearer
  authentication, and production-gate proofs for disposable workspace writes,
  outside-workspace denial, and direct worker-control-plane denial.

- Configurable loopback or LAN HTTP binding and an optional authenticated
  HTTPS ingress overlay.
- Online, integrity-checked backups and guarded restores for persistent
  action history and provider telemetry.
- Optional daily systemd backups with persistent scheduling, strict
  verification, and minimum-count retention safeguards.

### Security

- Updated React Router to 7.18.2 and refreshed the lockfile's compatible
  `brace-expansion`, `nanoid`, and `postcss` transitive releases, resolving the
  final dependency audit findings without a major-version migration or package
  override.

### Validated RC baseline

`atlas-v0.6-rc1.9` was published on 2026-08-13 at
`6d85df5b112b4bde28ec31fc60cce88560c9dbfc` as the validated release-candidate
baseline for v0.6.0.

### Implemented in v0.6.0

- Discovery Center compatibility engine, evidence flow, and catalog integration now
  drive execution-candidate projection with compatibility context available to
  planning and runtime decisions.
- Mission Control Discovery views and execution workflow shell now include
  discovery compatibility details and candidate workflow status across planning,
  implementation, verification, review, and commit checkpoints.
- Provider resources and connection management are now persisted in runtime state,
  including runtime policy and provider-connection stores plus connection secrets.
- Approval-gated execution is implemented across implementation, verification,
  review, and commit stages with immutable approval records.
- Candidate workflow planning and execution state is durable and restart-safe, with
  persisted transition artifacts and deterministic recovery behavior.
- Concurrent resume and workflow state transitions are hardened to prevent
  duplicated effective execution boundaries.
- Runtime verification context is preserved in redacted metadata for restart-safe
  continuation and strict validation.
- Deterministic and hardening coverage added for timing-sensitive candidate paths,
  restart/recovery matrix behaviors, audit-chain validation, concurrency, and
  contract regression.
- Validation coverage required for this RC includes ruff, test, lint, build, and
  container-release-gate verification.
- Core operational scope remains explicit to `update-compose-stack`.
- Structured Compose mutation evidence is required before implementation
  approval. It is carried through planning, workflow metadata, immutable
  implementation requests, and deterministic plan fingerprints.
- Planning, exact approval binding, persistence/recovery, stale evidence
  rejection, and successor concurrency/idempotent reuse were validated in the
  RC1 production smoke-test boundary.
- The final production-like RC1 execution smoke validation passed through the
  awaiting-commit-approval boundary on commit
  `c333937e61343aed714a475395b41077bad86e28`. It verified isolated worker
  execution, exact implementation and verification approvals, deterministic
  zero-command RC1 verification, baseline-aware review, and an exact commit
  approval request without performing the validation-only commit.
- The smoke hardening set now covers worker journal exactly-once recovery,
  approval-boundary audit projection, gated RC1 intent verification,
  baseline-aware verification and review, exact verification-plan approval
  binding, candidate resume dispatch, approval-repository storage identity,
  AtlasCoreClient event-loop ownership, deterministic zero-check evidence, and
  baseline-aware commit validation.
- Codex authentication, CLI installation, ephemeral runtime provisioning, and
  repository mutation are production-ready through the exact approval-gated
  candidate path. A named `workspace-write` permission profile runs inside a
  runsc-isolated worker with an authenticated, network-segmented control plane.
  Runtime proofs cover disposable workspace writes, outside-workspace denial,
  and direct worker-control-plane denial. Broad unconfined profiles,
  `CAP_SYS_ADMIN`, root execution, and `danger-full-access` remain explicitly
  rejected.

### Deferred to v0.7+

- `restart-service` execution intent.
- `backup` and `restore` execution intents.
- `install-provider` and `update-image` execution intents.
- Push, tag, release publication, remote deployment, and rollback automation.
- Candidate UI execution affordances in Mission Control beyond current shell,
  audit, and status workflows.

### Completed v0.6.0 milestone

**Codex Execution Sandbox Hardening** provides an isolated runsc execution
runtime, disposable `workspace-write` and outside-workspace denial proofs,
preserved non-root uid `10001`, zero effective capabilities,
`no-new-privileges`, and read-only rootfs hardening. Authenticated end-to-end
execution was validated through verification, review, and the pending commit
approval boundary without creating the validation-only commit.

### Inherited technical debt

- Atlas Core has an existing repository-wide backlog of 90 Ruff violations.
- Atlas Agent has an existing repository-wide backlog of 20 Ruff violations.
  v0.6.0 blocks new violations in changed production and test files while leaving
  both services' inherited cleanup outside release scope.
- Mission Control currently emits a large JavaScript chunk warning during build.
- Some Atlas Core source-boundary tests assume Atlas Core working-directory layout.

## v1.0.0 — Foundry (2026-07-25)

### Added

- Specialized OPNsense, Frigate, Obsidian, Qdrant, and n8n providers.
- Provider-backed ACE findings with bounded concurrent collection.
- Persistent provider-intelligence telemetry, filtering, export, trends,
  and retention administration.
- Live provider policies, performance thresholds, structured validation
  diagnostics, and Mission Control policy views.
- Persistent action history with filtering, pagination, detail views,
  sanitized export, and confirmed retention maintenance.
- Reproducible development dependency manifests and runtime requirements.
- Hardened production containers for Atlas Core and Mission Control with
  health checks, an API proxy, and persistent telemetry storage.
- Isolated container release gate with runtime hardening assertions,
  HTTP smoke checks, automatic cleanup, and GitHub Actions coverage.
- Pinned Core and Mission Control quality gates, a release checklist, and
  the project MIT license.

### Changed

- Atlas Core integration tests now use a thread-free in-process ASGI
  harness.
- Mission Control exposes provider telemetry, trends, policy status, and
  operational retention controls.
- Removed a stale tracked test backup from release source archives.

## Historical development tags

- `v0.7.0-foundry` — deployment planning, risk engine, and Forge workflow.
- `foundry-0.4.0` — Mission Control provider architecture.
- `v0.3.0-alpha2` — reusable knowledge-engine assessment rules.
- `v0.3.0-alpha1` — Atlas Intelligence Engine and summary API.
- `v0.2.0` — typed ACE policy engine.

### Architecture

- Completed Phase 3 candidate workflow from Discovery compatibility evidence through local Git commit.
- Added deterministic end-to-end candidate workflow coverage, audit-chain validation, recovery matrix coverage, concurrency hardening, commit-path security hardening, strict request validation, and route-contract regression coverage.
- Documented v0.6 boundaries: only `update-compose-stack` is supported; Atlas does not push, tag, release, deploy remotely, auto-approve, auto-execute, or roll back changes.

### Security

- Candidate commits are constrained to exact reviewed files and reject unsafe paths such as `.git/`, `jcode/`, `logs/`, absolute paths, parent traversal, duplicates, empty paths, symlink escape, and unrelated changed files.
- Caller-controlled Phase 3 request bodies use strict validation so input cannot broaden command, path, approval, verification, evidence, or commit scope.
