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

Long-running foundation track. The bounded v0.9 release theme is defined below.

Completed foundations include immutable defaults under `config/`, mutable
runtime state under `data/`, read-only production templates, validated runtime
initialization, explicit policy paths, and runtime-configuration backup and
restore with version-1 database-only backup compatibility. Further Runtime
Foundation work remains a cross-release track rather than unfinished v0.8
scope.

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

**Status: Complete.**

- Goal: establish the authoritative post-v0.7 release state and v0.8 scope.
- Deliverables: consistent release identities, current production boundaries,
  milestones, dependency order, and non-goals across project documentation.
- Non-goal: runtime, test, deployment, or security-control changes.
- Exit criteria: documentation consistently records v0.7.0 as final and defines
  one coherent v0.8 roadmap.

### V0.8-P1 — Effect-aware workflow and approval clarity

**Status: Complete.**

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

**Status: Complete.**

- Goal: provide one sanitized, correlated explanation of an operational action.
- Deliverables: a read-only projection covering intent provenance, candidate,
  plan, approvals, workflow, ledger transitions, barrier/provider-operation
  counts, verification, recovery, and terminal outcome.
- Non-goal: merging Core and Agent persistence or trust ownership.
- Exit criteria: stable correlation identifiers and redacted, paginated,
  filterable lifecycle responses explain the complete durable history.

### V0.8-P3 — Mission Control operational history and recovery UX

**Status: Complete.**

- Goal: make operational lifecycle and recovery state understandable to an
  operator without direct database or container access.
- Deliverables: operational history, lifecycle detail, verification and recovery
  states, terminal evidence, and fail-closed operator guidance.
- Non-goal: mutation retry, provider controls, or automatic reconciliation that
  can cross a dispatch barrier.
- Exit criteria: Mission Control accurately distinguishes pending verification,
  failure, replacement, unknown outcome, and verified terminal states.

### V0.8-P4 — Provider-neutral capability and selector descriptors

**Status: Complete.**

- Goal: make supported capabilities discoverable without granting execution.
- Deliverables: typed read-only capability descriptors and a provider-neutral
  selector contract implemented by the existing Proxmox QEMU projection.
- Non-goal: new intent, provider/resource tuple, translation, or handler.
- Exit criteria: tests prove descriptors cannot enable a gate, register a
  handler, derive arbitrary provider actions, or bypass authoritative resolution.

### V0.8-P5 — Deployment and security ergonomics

**Status: Complete.**

- Goal: clarify the supported browser ingress and operational-auth experience.
- Deliverables: direct Mission Control HTTP exposure review, session-expiry and
  reauthentication UX, evidence-retention guidance, and release checks for
  redaction, stale approvals, gate/registry parity, and ingress policy.
- Non-goal: weaker origin, CSRF, credential, container, or network controls.
- Exit criteria: production has one clearly documented browser-access model and
  reproducible security assertions.

P0 through P5 are complete. The immutable `atlas-v0.8-rc1` candidate at
`cf09dfe1eebbd138d37ba7144d91b893f70732fa` passed required CI, exact-SHA
production deployment, and sequential restart soak validation. The final
`atlas-v0.8.0` release was published at
`f83cd90982d4682ce49e60308e93dc9840984211`.

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

## Atlas v0.9 roadmap

**Theme: Safe Operational Tuple Expansion**

Objective: prove that Atlas can add one second closed operational tuple without
weakening identity binding, approval isolation, exactly-once dispatch,
recovery, or the existing QEMU restart path.

The contingent target is `restart-service / proxmox / lxc`. LXC execution is
conditional on authoritative resource-incarnation identity feasibility. The
dependency order is
`V0.9-P0 → V0.9-P1 → V0.9-P2 → V0.9-P3 → V0.9-P4 → V0.9-P5`.

### Current v0.8 production boundary

- Repository execution is the separate `update-compose-stack` workflow.
- Operational production execution is exactly
  `restart-service / proxmox / qemu`.
- Agent planning and execution gates contain only `restart-service`.
- Core execution gate contains only `restart-service`.
- Agent translation and Core semantic action mapping contain exactly the QEMU
  graceful-restart action.
- The production handler registry contains exactly one QEMU restart handler.
- No LXC execution is enabled.

### V0.9-P0 — Release-state and tuple-readiness reconciliation

- Goal: record the final v0.8 release and establish authoritative v0.9 scope.
- Deliverables: consistent release identity, current production boundary,
  milestones, hard gates, parity contract, dependencies, and non-goals.
- Dependencies: final `atlas-v0.8.0` release.
- Non-goals: runtime code, candidates, gates, handlers, ACLs, or mutation.
- Exit criteria: all current-state documentation agrees and no document implies
  LXC execution exists.

### V0.9-P1 — Authoritative LXC identity and read-only eligibility

- Goal: prove one exact Proxmox LXC incarnation can be identified and
  fingerprinted authoritatively.
- Deliverables: a versioned identity contract, stable same-incarnation
  fingerprint, replacement/delete-recreate detection, and stale, missing,
  duplicate, ambiguous, and uncertain identity rejection.
- Dependencies: P0.
- Non-goals: candidate creation, translation, gate widening, handler
  registration, ACL changes, or restart.
- Exit criteria: every identity uncertainty fails closed. VMID plus node alone
  is explicitly insufficient. If replacement identity cannot be proven, all
  LXC execution work stops.

The first P1 code slice is read-only, versioned Proxmox LXC authoritative
identity and fingerprint contracts with replacement and staleness tests. It
must leave planning, translation, both execution gates, capability
advertisement, selector requestability, and handler registration unchanged.
Identity code alone must not make LXC requestable.

### V0.9-P2 — Multi-tuple capability and permission contracts

- Goal: make capability projection, selectors, parity, and operator authority
  safe for more than one tuple.
- Deliverables: immutable multi-tuple descriptor/selector registration,
  fail-closed parity, and backward-compatible tuple-scoped permission
  semantics.
- Dependencies: P1 identity feasibility passes.
- Non-goals: a final permission string chosen without design evidence,
  execution enablement, handler registration, or provider mutation.
- Exit criteria: the existing broad `operational_intent:create` permission
  cannot silently authorize every future tuple, and dormant LXC metadata grants
  no request or execution authority.

### V0.9-P3 — Dormant LXC planning and dispatch contracts

- Goal: prepare immutable LXC restart contracts while production execution
  remains disabled for LXC.
- Deliverables: intent-keyed planning, closed translation, exact request and
  approval binding, persistence compatibility, and recovery-state fixtures.
- Dependencies: P2.
- Non-goals: gate widening, production handler registration, ACL changes, or
  restart.
- Exit criteria: exact LXC artifacts can be planned and approved, but no
  production dispatch path exists.

### V0.9-P4 — Handler, verification, and recovery validation

- Goal: validate one graceful LXC handler and its failure lifecycle outside
  production enablement.
- Deliverables: pre-dispatch identity revalidation, provider-operation capture,
  bounded verification, ambiguity handling, crash recovery, verifier-only
  recovery, and exactly-once sandbox evidence.
- Dependencies: P3.
- Non-goals: production registration, global enablement, automatic retry, or
  QEMU behavior changes.
- Exit criteria: every failure window is covered, mutation count is bounded to
  one, and recovery constructs no mutation path.

### V0.9-P5 — Controlled enablement and release acceptance

- Goal: enable the second tuple only after reviewed identity, permissions,
  contracts, handler, verification, recovery, and sandbox evidence.
- Deliverables: least-privilege ACL procedure, explicit Agent/Core gate and
  registry changes, multi-tuple release parity, controlled acceptance, and
  upgrade/rollback guidance.
- Dependencies: P4 plus explicit operator authorization.
- Non-goals: any additional tuple, intent, provider, or broad ACL.
- Exit criteria: production exposes exactly the reviewed QEMU and LXC tuples;
  QEMU regressions remain green and one controlled LXC acceptance proves no
  replay.

### V0.9 capability parity contract

Every operational tuple must match across Agent planning registration,
translation table, and execution gate, plus Core execution gate, semantic
action mapping, handler registry, capability descriptor, and selector
registration. Any missing or extra tuple fails closed. Atlas does not
auto-repair parity mismatches.

### V0.9 non-goals

V0.9 does not add backup execution, restore execution, a new operational
intent, a new provider, QEMU reset/stop/start/forced restart, automatic mutation
retry, automatic rollback, arbitrary provider action IDs or parameters,
Discovery-to-dispatch coupling, remote deployment, distributed execution, new
Docker socket authority, automatic approval, broad Proxmox ACL expansion, a
major Mission Control redesign, or backup artifact retention/storage
architecture.
