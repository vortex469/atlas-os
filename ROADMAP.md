# Atlas OS Roadmap

Atlas is in the Foundry development phase. Completed work is recorded in
`CHANGELOG.md`; this file describes direction rather than a release
promise. Product direction is guided by the
[Atlas Design Principles](ATLAS_DESIGN_PRINCIPLES.md) and the [Atlas Runtime Architecture](ATLAS_RUNTIME_ARCHITECTURE.md).

## Foundry release hardening

- Release documentation and configuration consistency
- Reproducible dependency installation and security review
- API, Mission Control, and packaging release gates
- Operational deployment guidance


## Atlas Runtime Foundation

Long-running foundation track. The bounded v0.8 release theme is defined below.

- Define immutable defaults under `config/` and mutable runtime state under `data/`
- Keep shipped templates read-only in production
- Move normal Mission Control writes to runtime state so they must not dirty the Git checkout
- Initialize missing runtime configuration from validated templates without overwriting existing user state
- Make runtime policy storage explicit with `ATLAS_POLICY_FILE` and `ATLAS_POLICY_TEMPLATE_FILE`
- Include runtime configuration in backup and restore with backward compatibility for version-1 database-only backups

## Provider Management Framework

Runtime Foundation subsystem.

- Build an intent-driven Mission Control experience for provider management
- Discover provider resources automatically before asking users for policy
- Introduce Needs Review workflows for newly discovered resources
- Let users set monitoring intent without editing YAML
- Keep files available for advanced operators and automation
- Make provider pages consistent across connection, discovery, resources, monitoring, actions, and diagnostics
- Allow AI suggestions for intent changes while requiring user approval before policy updates

## Knowledge Engine

- Expand the application knowledge catalog
- Resource estimation
- Best-practice recommendations
- Cross-provider infrastructure relationships

## Discovery Center

Provider-neutral catalog and compatibility subsystem. D0 architecture and planning docs live in [docs/discovery-center](docs/discovery-center/ARCHITECTURE.md).

- Define structured local catalog knowledge for applications, services, container images, AI models, integrations, hardware devices, and deployment methods
- Keep curated YAML as the initial authoritative source
- Evaluate compatibility through deterministic, evidence-based checks before semantic or AI-based behavior
- Preserve the recommendation interface ownership boundary and keep execution control in Atlas Agent pathways
- Keep Discovery Center read-only by default

### Current implementation status

- ✅ Implemented: curated catalog models, loader, repository/search, read-only API, compatibility engine, and Orion-consumed compatibility findings in intelligence pipeline.
- ✅ Implemented: Mission Control discovery API client, typed contracts, and read-only Discovery Center UI pages for browsing catalog items and viewing item details with relationships, provenance, and compatibility evidence.
- 📌 Planned / Future: dynamic catalog sources, semantic discovery, Atlas Agent handoff protocol, community/private catalogs, and broader execution candidate affordances.

## Deployment Platform

- Approval workflows
- Provider-backed execution
- Rollback support
- Live deployment monitoring

## Conversational Infrastructure

- Orion Assistant *(Planned)*
- Guided troubleshooting
- Cross-provider reasoning
- Voice interaction
- Conversational operations

## Atlas v0.6 roadmap status

### Completed

- Phase 3 `update-compose-stack` candidate workflow through structured planning intake, deterministic Compose mutation evidence, workflow shell, immutable implementation request, exact approvals, persistence/recovery, concurrency protection, verification evidence, deterministic review, and commit-boundary validation, including Codex-backed repository mutation through the hardened execution sandbox.
- P3.14A hardening: deterministic end-to-end coverage, machine-readable audit-chain validation, restart and recovery matrix coverage, deterministic concurrency coverage, commit-path security hardening, strict caller-controlled request validation, API route-contract regression coverage, and roadmap workflow regression coverage.
- Codex execution sandbox hardening: named workspace permission profile,
  runsc-isolated worker, authenticated and network-segmented control plane, and
  disposable workspace/outside-workspace runtime proofs, followed by an
  authenticated end-to-end candidate execution through verification, review,
  and the pending commit-approval boundary.

### Planned

- At the end of v0.6, the following work was deferred to later releases:
  - `restart-service` (the first closed tuple subsequently shipped in v0.7)
  - `backup`
  - `restore`
  - `install-provider`
  - `update-image`
  - automated rollback, tag/release automation, and remote deploy automation.

#### Phase 4: new execution intents

Beyond the closed `restart-service / proxmox / qemu` capability delivered in
v0.7, additional execution intents or provider/resource tuples require separate
architecture, contracts, exact approvals, recovery behavior, security review,
and end-to-end tests.

#### Phase 5: distributed orchestration

Distributed orchestration, clustering, cross-host recovery, and advanced provider execution require a persistence and coordination design beyond current local Agent state.

### Future ideas

Dynamic discovery sources, semantic search, Mission Control candidate controls, release workflows, and rollback automation remain future ideas. They are not part of v0.6.

## Atlas v0.7 roadmap status

Atlas v0.7 is complete and was released as `atlas-v0.7.0` at
`8dbc43de73dda300b50c121f19324cb5174df2a9`. Its immutable release candidate,
`atlas-v0.7-rc1`, remains at
`5b1321091af0fc191844cdf71e9e0d919e4ea415`.

### Completed: P1.3 operational restart

- `restart-service / proxmox / qemu` is enabled as the first production
  operational-action capability.
- An authenticated operator with `operational_intent:create` can request a
  candidate for one exact authoritative QEMU resource. The candidate still
  traverses planning, workflow-shell approval, immutable action translation,
  exact operational-action approval, Agent orchestration, and authenticated
  Core dispatch.
- Core binds execution to the authoritative QEMU identity and fingerprint,
  revalidates the target before crossing a durable exactly-once dispatch
  barrier, captures the provider UPID, and performs bounded read-only
  verification. Ambiguous outcomes fail closed without mutation replay.
- Verifier-only recovery can resume interrupted verification without
  constructing a mutation handler or reopening the dispatch barrier.
- Mission Control provides Core-owned operator login and a sanitized,
  resource-scoped maintenance-request flow. It accepts no provider action ID,
  command, native provider identity, endpoint, environment, or arbitrary
  parameters.

Production acceptance on 2026-08-14 exercised the normal path against the
approved non-critical Proxmox QEMU guest VM 110 (`Frigate`). Exactly one
graceful restart was accepted, the workflow reached `COMPLETED`, verification
observed the same guest running with QMP running, and the authoritative target
fingerprint remained unchanged. The dispatch ledger recorded one barrier, one
provider-operation capture, one dispatch result, and no replay.

### Deferred beyond v0.7

- `backup`, `restore`, `install-provider`, and `update-image` remain unsupported
  execution intents and require their own contracts, security review, recovery
  behavior, and end-to-end validation.
- Automated rollback, push, tag/release publication, and remote deployment
  remain out of scope.

## Atlas v0.8 roadmap

**Theme: Operational Control Plane Clarity and Observability**

Purpose: make the existing operational capability understandable, auditable,
recoverable, and safely extensible without widening the mutation boundary.

The dependency order is:
`V0.8-P0 → V0.8-P1 → V0.8-P2 → V0.8-P3 → V0.8-P4 → V0.8-P5`.

### V0.8-P0 — Roadmap and release-state reconciliation

- Goal: establish the authoritative post-v0.7 release state and v0.8 scope.
- Deliverables: consistent release identities, current production boundaries,
  milestones, dependency order, and non-goals across project documentation.
- Non-goal: runtime, test, deployment, or security-control changes.
- Exit criteria: documentation consistently records v0.7.0 as final and defines
  one coherent v0.8 roadmap.

### V0.8-P1 — Effect-aware workflow and approval clarity

- Goal: make repository and operational workflows unmistakably distinct.
- Deliverables: effect-aware approval presentation; explicit stale, historical,
  and superseded states; exact actionability rules; deterministic refresh after
  decisions; and proof that operational workflows never expose commit approval.
- Non-goal: any execution, gate, handler, or approval-binding behavior change.
- Exit criteria: Mission Control presents only currently actionable approvals
  as actionable and renders repository-only stages only for repository changes.

The first code slice is limited to those presentation and read-contract changes.
It must not change execution behavior.

### V0.8-P2 — Unified operational lifecycle read model

- Goal: provide one sanitized, correlated explanation of an operational action.
- Deliverables: a read-only projection covering intent provenance, candidate,
  plan, approvals, workflow, ledger transitions, barrier/provider-operation
  counts, verification, recovery, and terminal outcome.
- Non-goal: merging Core and Agent persistence or trust ownership.
- Exit criteria: stable correlation identifiers and redacted, paginated,
  filterable lifecycle responses explain the complete durable history.

### V0.8-P3 — Mission Control operational history and recovery UX

- Goal: make operational lifecycle and recovery state understandable to an
  operator without direct database or container access.
- Deliverables: operational history, lifecycle detail, verification and recovery
  states, terminal evidence, and fail-closed operator guidance.
- Non-goal: mutation retry, provider controls, or automatic reconciliation that
  can cross a dispatch barrier.
- Exit criteria: Mission Control accurately distinguishes pending verification,
  failure, replacement, unknown outcome, and verified terminal states.

### V0.8-P4 — Provider-neutral capability and selector descriptors

- Goal: make supported capabilities discoverable without granting execution.
- Deliverables: typed read-only capability descriptors and a provider-neutral
  selector contract implemented by the existing Proxmox QEMU projection.
- Non-goal: new intent, provider/resource tuple, translation, or handler.
- Exit criteria: tests prove descriptors cannot enable a gate, register a
  handler, derive arbitrary provider actions, or bypass authoritative resolution.

### V0.8-P5 — Deployment and security ergonomics

- Goal: clarify the supported browser ingress and operational-auth experience.
- Deliverables: direct Mission Control HTTP exposure review, session-expiry and
  reauthentication UX, evidence-retention guidance, and release checks for
  redaction, stale approvals, gate/registry parity, and ingress policy.
- Non-goal: weaker origin, CSRF, credential, container, or network controls.
- Exit criteria: production has one clearly documented browser-access model and
  reproducible security assertions.

### V0.8 non-goals

V0.8 does not add new operational execution intents, new provider mutation
handlers, backup execution, restore execution, `update-image` execution,
`install-provider` execution, automatic rollback, arbitrary provider actions,
mutation retry after ambiguity, remote deployment, distributed orchestration,
conversational execution, automatic approval, Proxmox ACL expansion, or direct
Discovery Center-to-dispatch coupling.

### Current production execution boundary

Repository execution remains the separate `update-compose-stack` workflow.
Operational production execution is exactly `restart-service / proxmox / qemu`:
the Agent planning gate, Agent execution gate, and Core execution gate contain
only `restart-service`, and the production registry contains exactly the one
`restart-service/proxmox/qemu` tuple.
