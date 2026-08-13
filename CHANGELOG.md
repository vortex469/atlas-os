# Changelog

This project is under active development. Entries describe significant
operator-visible changes; Git tags remain the source of truth for exact
release boundaries.

## Unreleased

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

## atlas-v0.6-rc1 — Recovery Candidate RC1 (2026-08-05)

### Implemented in RC1

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
- Codex authentication, CLI installation, and ephemeral runtime provisioning
  are production-ready. Actual Codex-backed repository mutation is deferred to
  **Codex Execution Sandbox Hardening** because the hardened Docker
  seccomp/AppArmor policy prevents bubblewrap `workspace-write` initialization.
  Broad unconfined profiles, `CAP_SYS_ADMIN`, root execution, and
  `danger-full-access` are explicitly rejected.

### Deferred to v0.7+

- `restart-service` execution intent.
- `backup` and `restore` execution intents.
- `install-provider` and `update-image` execution intents.
- Push, tag, release publication, remote deployment, and rollback automation.
- Candidate UI execution affordances in Mission Control beyond current shell,
  audit, and status workflows.

### Deferred RC1 milestone

**Codex Execution Sandbox Hardening** must provide a reviewed narrow
seccomp/AppArmor policy or isolated execution runtime, disposable
`workspace-write` and outside-workspace denial proofs, preserved non-root,
`CapDrop=ALL` where applicable, `no-new-privileges`, and read-only rootfs
hardening, followed by authenticated end-to-end execution through verification,
review, and commit approval boundaries.

### Inherited technical debt

- Atlas Core has an existing repository-wide backlog of 90 Ruff violations.
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
