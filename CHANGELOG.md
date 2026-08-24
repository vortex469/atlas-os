# Changelog

This project is under active development. Entries describe significant
operator-visible changes; Git tags remain the source of truth for exact
release boundaries.

## Unreleased

## atlas-v0.14.0 — release-candidate closure

Atlas v0.14 implementation is complete and is in release-candidate closure.
It is not yet tagged or released; exact closure-SHA validation, required CI and
container gates, production image/source parity, and read-only production
acceptance remain release gates.

#### Added

- `DeploymentBinding` connects a curated catalog item to one exact repository
  Compose file and service without granting access to arbitrary source
  configuration.
- Image grounding composes an exact repository Compose-image observation with
  accepted image-release evidence. The resulting grounding and evidence
  provenance projection are read-only and informational.
- The image-release evidence loader accepts reviewed, immutable evidence rows;
  reviewed promotion preserves the `REGISTRY_ATTESTED` source class rather than
  converting registry proof into `CURATED` knowledge.
- Repository Compose-image observation reads the bound image from the reviewed
  repository boundary without adding a route, collector activation, or
  execution path.
- The trusted collector boundary supports bounded GHCR acquisition and offline
  Sigstore verification for one reviewed fixed proof case: Home Assistant
  `2026.8.3`. Its Sigstore trust root is repository-owned and hash-pinned.
- The accepted Home Assistant proof integrates as `REGISTRY_ATTESTED` evidence,
  then participates in read-only grounding composition and provenance
  projection.

#### Security and authority boundary

`acquisition != verification != accepted evidence != grounding != operational authority`

- Acquisition is bounded retrieval, verification is offline cryptographic
  evaluation, accepted evidence is immutable knowledge, and grounding is an
  informational composition. None grants operational authority.
- The collector remains inactive in production. Production collector
  registries remain empty, and there is no scheduled or startup collection.
- V0.14 adds no update, pull, restart, or deploy authority. It does not change
  the existing operational or repository execution boundaries.
- `REGISTRY_ATTESTED` and `CURATED` remain distinct trust classes. Accepted
  registry evidence is never silently promoted to curated authority.

## atlas-v0.13.0 — Atlas v0.13.0 (2026-08-21)

Atlas v0.13 has the theme **Compatibility/Upgrade Intelligence**. It turns the
already-released v0.12 dynamic Discovery facts into bounded, read-only upgrade
intelligence: a deterministic release evaluation for each merged item, observed
installed-version evidence, version-bounds compatibility checks, and Mission
Control upgrade presentation. The immutable `atlas-v0.13.0` release is
published; implementation completed at `64e8341` before its release closure.

#### Added

- P1 discovery release evaluation: a bounded, deterministic, side-effect-free
  evaluation of the authoritative baseline version against the freshest dynamic
  release evidence for each `discovery-merged-item-v1` projection, exposed as an
  additive, optional `release_evaluation` property.
- P2 observed installed version evidence: a provider-neutral, advisory
  `installed_version` observation on compatibility context services and a strict
  numeric `X.Y.Z` comparison key, so a missing or malformed version is unknown
  and never yields a positive assertion.
- P3 version-bounds compatibility: deterministic `version` compatibility checks
  comparing an observed installed version against the curated
  `minimum_version`/`maximum_version` bounds of a required relationship,
  fail-closed to `insufficient_information` when a version is not strict
  numeric `X.Y.Z`.
- P4 Mission Control upgrade intelligence: an advisory release-evaluation
  notice on the Discovery evidence panel presenting the bounded status,
  baseline, and latest candidate with no Apply, Execute, update, or remediate
  control.
- P5 release isolation/readiness validation: isolation tests proving the
  release-evaluation module has no I/O, network, cache, or application-module
  coupling beyond its two reviewed Discovery consumers.

#### Security and authority boundary

- The release evaluation is read-only upgrade intelligence. It is derived, not
  persisted; it adds no Provider Intent, policy, proposal, approval, provider
  action, or execution authority.
- The curated catalog remains authoritative. The baseline is the curated
  release version when present (`baseline.source=curated`), otherwise the item
  version (`baseline.source=item_version`). Dynamic and observed facts remain
  evidence, not authority, and never override curated data.
- Discovery remains `GET`-only and read-only. `release_evaluation` is additive
  and optional in `discovery-merged-item-v1`; legacy item schemas are
  unchanged.
- Capability parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`. LXC remains unsupported. The rebuildable
  Discovery cache remains excluded from backup v3.

## atlas-v0.12.0 — Atlas v0.12.0 (2026-08-19)

Implementation is complete at `5075f1a`. The annotated `atlas-v0.12.0` release
tag points to the documentation-only closure commit `c8d06a5`, which is not
the tested implementation SHA.

#### Added

- P1 fixed, code-owned `frigate-github-latest-release-v1` source foundation
  with bounded unauthenticated allowlisted HTTPS retrieval.
- P2 atomic rebuildable cache, freshness and offline evaluation, source health,
  conflict handling, and bounded refresh coordination.
- P3 deterministic merged Discovery evidence read API in which curated claims
  remain authoritative and dynamic/cached facts remain supplemental evidence.
- P4 Mission Control provenance, freshness, conflict, and source-health
  presentation with curated-only fallback.
- P5 opt-in, default-off bounded startup refresh via
  `ATLAS_ENABLE_DISCOVERY_DYNAMIC_REFRESH`, with isolation tests preserving the
  evidence-not-authority boundary.

#### Security and authority boundary

- Dynamic Discovery adds no Provider Intent, policy, proposal, approval, or
  execution authority. Capability parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`.

## atlas-v0.11.0 — Atlas v0.11.0 (2026-08-17)

The annotated `atlas-v0.11.0` release tag points to the exact evidence-bound
implementation SHA `f8b2c8a202ca1c7316361e0c6b0ba72ee83eb9e2`. The later
documentation-only release-acceptance closure remains commit
`375db0a883bd100de21d2deabaa118be48c1e057` and is not the tested binary or
recovery-evidence SHA.

#### Added

- `atlas-core-recovery-evidence-v3` schema with 12 additional v3-specific checks
  beyond v2, binding exact-SHA mutation-state proof to identity-bound Provider
  Intent incarnation boundaries.
- V3 evidence validation enforces that only exact-SHA evidence with schema/activation
  pairing (v3+activated) satisfies final release acceptance for identity-bound
  provider-intent mutation.
- V3 regression test suite covering Provider Intent idempotency, replacement
  isolation, Discovery/ACE/suggestion isolation, and legacy-YAML non-authority.
- Recovery gate v3 verification branch with seeded fixture demonstrating active
  identity-bound records, legacy evidence preservation, mutation receipt,
  and audit operator-binding.
- Identity-bound Provider Intent authority for supported Proxmox QEMU resources,
  with schema-v2 durable mutation, audit, and idempotency records.
- Authenticated explicit mutation and a coherent Mission Control authority
  presentation separating observed state, monitoring intent, diagnostics,
  provider actions, and operational maintenance.
- Advisory suggestions that require explicit Review and Save; suggestions never
  apply automatically or cause remediation.
- Backup/recovery-v3 preservation of active identity-bound intent, legacy
  records, import receipts, mutation evidence, and audit evidence.

#### Validation

- Provider Intent Store mutation idempotency: exact request replay returns
  identical outcome without duplicate audit records.
- Incarnation rebinding: new fingerprint creates new v1 record; old incarnation
  retained in history but superseded in active coordinates.
- Isolation boundaries: Discovery/ACE/suggestion reads, UI rendering, and
  legacy-YAML authority never create or mutate Provider Intent records.
- LXC unsupported: record creation fails closed; no active coordinate entry.
- LXC remains unsupported for identity-bound Provider Intent. V0.11 adds no
  automatic remediation and no execution expansion; capability parity remains
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`.
- Canonical Atlas Core regression suite: 1188/1188 passed. The separately
  reported 1184/1186 root invocation was traced to two pre-existing
  working-directory-sensitive tests that pass from the canonical Core
  directory on both the P5c tree and clean baseline.

#### Exit criteria

- [x] `atlas-core-recovery-evidence-v3` recognized and enforced
- [x] Exact-SHA candidate validation with schema/activation pairing
- [x] V3 idempotency and replacement-isolation proven
- [x] Isolation boundaries validated
- [x] Full regression suite clean
- [x] Documentation and release evidence package complete

## atlas-v0.10.0 — Atlas v0.10.0 (2026-08-15)

Atlas v0.10 implements a sanitized, stale-aware Discovery-to-Operator Proposal
Handoff without expanding execution authority.

### Added

- Immutable, extra-forbid proposal, provenance, compatibility, destination,
  target-hint, identity, expiry, and source-state contracts.
- Read-only derivation and evaluation with bounded process-local observation of
  stale or expired proposals and no durable proposal persistence.
- Bounded GET-only proposal list/detail APIs with sanitized, closed navigation.
- Mission Control proposal cards, review-only stale/incompatible presentation,
  compatibility navigation, and separate advisory maintenance context.

### Security boundary

- Proposal existence or navigation cannot create a candidate, planning session,
  approval, action request, dispatch record, or provider operation.
- Maintenance selection reloads current operator permission, production
  capability descriptors, selector resources, state, requestability, and target
  fingerprint. Proposal hints are presentation-only.
- Production mutation remains exactly `restart-service/proxmox/qemu`; LXC and
  all other mutation tuples remain unsupported. The immutable
  `atlas-v0.10.0` release was published at
  `b19ded149f65dfb4043a1b80833e5ff64d83e55d`.

### RC1 validation

- `atlas-v0.10-rc1` (tag object
  `1c8798472ce46b2aa1fc822c1613a720c62113c4`) peels to
  `95d98a4d5e0e9767dd6cb5df06c7ffdb693bf162`. Quality gates run
  `31863884438` and Container release gate run `31863884456` succeeded, and
  `atlas-release-evidence-v1` reported `ready`.
- Production was rebuilt without cache from the exact RC checkout using only
  the production, HTTPS, and operator-auth Compose files. Core and Agent source
  checksums and the Mission Control image matched the RC build; all required
  services remained healthy.
- Live proposal list/detail reads returned four deterministic, sanitized
  proposals, known detail returned 200, unknown detail returned controlled 404,
  and IDs remained stable through Core, Mission Control, Agent, and Edge
  restarts.
- Proposal reads and navigation changed no candidate, planning, approval,
  action-request, dispatch, barrier, provider-operation, result, verification,
  or VM reboot count. Review-only, stale, expired, missing-source/evidence,
  unsupported, transport-failure, and tampered states remained fail-closed.
- Mission Control remained advisory with no target preselection, automatic
  submission, execution, approval, dispatch, retry, or replay control. Atlas
  Edge remained the sole browser ingress.

## atlas-v0.9.0 — Atlas v0.9.0 (2026-08-15)

Atlas v0.9 completed Operational Recovery and Evidence Automation. The final
release was published at
`7a5beac58e1677cd97b9bcc2f160dc30573582aa`, promoting the immutable
`atlas-v0.9-rc1` candidate at
`bc549ff6ab57d366205c1b9eb0c36fc2f7a61ba3` passed required CI,
`atlas-release-evidence-v1`, exact-SHA no-cache production deployment, and
sequential restart soak. Final Quality gates run `31861408265` and Container
release gate run `31861408264` passed.

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
