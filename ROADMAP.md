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

**Theme: Operational Recovery and Evidence Automation**

Objective: make Atlas easier to diagnose, recover, support, and release safely
using the existing durable operational lifecycle, without adding any new
provider mutation capability. The dependency order is
`V0.9-P0 → V0.9-P1 → V0.9-P2 → V0.9-P3 → V0.9-P4 → V0.9-P5`.

### Current production boundary

- Repository execution is the separate `update-compose-stack` workflow.
- Operational production execution is exactly
  `restart-service / proxmox / qemu`.
- Agent planning and execution gates contain only `restart-service`.
- Core execution gate contains only `restart-service`.
- Agent translation and Core semantic action mapping contain exactly the QEMU
  graceful-restart action.
- The production handler registry contains exactly one QEMU restart handler.
- `restart-service / proxmox / lxc` remains unsupported and non-requestable.

### LXC feasibility decision

The read-only LXC identity feasibility investigation completed with a NO-GO.
Current Atlas-visible Proxmox APIs expose no provider-authoritative,
configuration-independent LXC incarnation identifier comparable to QEMU
`vmgenid`. Node and VMID are reusable; configuration digest is mutable and
reproducible; rootfs naming is reusable; MAC values are mutable; task history
is not authoritatively bound to the current incarnation; and no UUID, GUID, or
instance-generation token was found.

Atlas will not synthesize identity from those fields merely to enable
execution. The former tuple-expansion P2–P5 do not proceed for LXC. LXC may be
reconsidered only if an independently demonstrated provider-authoritative
incarnation identity becomes available. This is a successful fail-closed
architecture decision, not an implementation failure.

### V0.9-P0 — Release-state reconciliation and LXC feasibility closure

**Status: complete.**

- Goal: establish the final v0.8 baseline and revised v0.9 scope.
- Deliverables: final release identity, LXC identity NO-GO record, revised
  recovery/evidence milestones, dependencies, and non-goals.
- Dependencies: final `atlas-v0.8.0` release and completed read-only LXC audit.
- Non-goals: runtime code, identity synthesis, gates, handlers, ACLs, or
  mutation.
- Exit criteria: current-state documentation agrees, P0 is complete, and LXC
  feasibility is closed NO-GO.

### V0.9-P1 — Read-only recovery diagnostics

**Status: complete.**

- Goal: provide one operator-facing diagnostic projection for ambiguous and
  recovery states.
- Deliverables: lifecycle consistency, Core/Agent availability,
  request-to-ledger correlation, target-fingerprint state, controlled recovery
  reason, and recommended safe next action.
- Dependencies: P0 and existing Agent/Core lifecycle projections.
- Non-goals: provider calls, reconciliation writes, mutation endpoints,
  retries, handlers, or gate changes.
- Exit criteria: diagnostics are deterministic, controlled, sanitized, and
  strictly read-only.

The first code-bearing slice is a strictly read-only operational recovery
diagnostic model derived from existing Agent lifecycle and Core durable-ledger
projections. It adds no provider call, reconciliation write, mutation endpoint,
handler, or gate change and exposes only controlled reasons.

### V0.9-P2 — Sanitized operational support bundle

**Status: complete.**

- Goal: generate a bounded local evidence package from already-safe
  projections.
- Deliverables: release and image identity, service health, workflow/candidate/
  planning/request IDs, approval presentation, sanitized lifecycle,
  transitions and verification state, target fingerprint, capability parity,
  and selected audit IDs.
- Dependencies: P1 diagnostic contract.
- Non-goals: credentials, cookies, CSRF or bearer tokens, TLS keys, edge
  `htpasswd` or operator-verifier material, provider-native payloads,
  `vmgenid` or raw identity tokens, commands, environment, arbitrary exception
  text, or any automatic upload destination.
- Exit criteria: output is bounded, deterministic, local, sanitized, and
  independently testable for forbidden fields.

### V0.9-P3 — Release evidence automation

**Status: complete.**

- Goal: automate collection and validation of release evidence currently
  gathered manually.
- Deliverables: exact SHA/tag, required CI, container-gate, image/source parity,
  capability parity, ingress policy, worktree provenance, secret hygiene, and
  immutable-tag checks.
- Dependencies: P2 evidence contracts where shared.
- Non-goals: automatic tagging, production deployment mutation, or release
  publication.
- Exit criteria: check-only tooling reproduces the required release evidence
  and fails closed on inconsistency.

### V0.9-P4 — Recovery/history operator UX

**Status: complete.**

- Goal: surface recovery diagnostics and evidence availability in Mission
  Control.
- Deliverables: diagnostic state, correlation IDs, evidence availability,
  safe support-bundle generation/download, and clear guidance for
  `outcome_unknown`, `target_replaced`, and `verification_failed`.
- Dependencies: P1 and P2.
- Non-goals: retry, run-again, reconciliation writes, or mutation controls.
- Exit criteria: operators can understand and export controlled evidence
  without any execution affordance.

### V0.9-P5 — Release acceptance and documentation

**Status: complete.** P0 through P5 are implemented and accepted. The immutable
`atlas-v0.9-rc1` candidate at
`bc549ff6ab57d366205c1b9eb0c36fc2f7a61ba3` passed exact-candidate CI,
release-evidence validation, exact-RC production deployment, and sequential
restart soak. The final `atlas-v0.9.0` release was published at
`7a5beac58e1677cd97b9bcc2f160dc30573582aa`; final Quality gates and Container
release gate passed.

- Goal: validate the read-only recovery/evidence toolchain under production
  service-restart soak and finalize release documentation.
- Deliverables: focused/full test evidence, production restart-soak evidence,
  redaction/security review, upgrade/rollback guidance, and release checklist.
- Dependencies: P3 and P4.
- Non-goals: a new operational intent, provider handler, automatic tag, or
  deployment mutation.
- Exit criteria: the toolchain remains read-only and accurate across service
  restarts, and the existing QEMU mutation boundary is unchanged.

### V0.9 non-goals

V0.9 does not add LXC execution, backup execution, restore execution, a new
operational intent, a new provider, a new mutation handler, automatic provider
retry, automatic rollback, automatic approval, automatic tag publishing,
automatic production deployment, Discovery-to-dispatch coupling, remote or
distributed execution, new Docker socket authority, broader Proxmox ACLs, or
synthetic LXC incarnation identity.

## Atlas v0.10 roadmap

**Theme: Discovery-to-Operator Proposal Handoff**

Objective: turn trusted Discovery and Orion advisory evidence into sanitized,
stale-aware operator proposals that navigate to existing authoritative review
or operator-intent surfaces without granting Discovery execution authority.
The dependency order is
`V0.10-P0 → V0.10-P1 → V0.10-P2 → V0.10-P3 → V0.10-P4 → V0.10-P5`.

### Proposal trust boundary

Atlas Core's Discovery/intelligence layer initially owns proposals. They are
derived rather than persisted. A proposal may contain its ID, catalog item and
provenance, source finding, compatibility assessment/finding/evidence
references, a closed intent hint, sanitized target hints, a closed destination,
generation and expiry times, and a source-state fingerprint.

Proposal context is never sufficient to create an operational request. It
cannot create an `ExecutionCandidate` or `OperationalActionRequest`, approve or
dispatch, select an authoritative resource, assert a target fingerprint,
supply a provider action ID or arbitrary parameters, or bypass authentication,
capability, or selector boundaries. At the destination Atlas must freshly load
the current capability descriptor, authoritative selector, target state and
fingerprint, and operator authentication/permission state. Any operator-intent
POST uses only those freshly resolved server facts.

Proposal identity is a versioned canonical digest over schema/version, catalog
item ID, provenance source type/entry ID/version or a deterministic entry
fingerprint, applicable source finding ID, compatibility target ID/type/status,
sorted finding and evidence IDs, controlled intent hint, sanitized target hints,
and controlled destination. Display text, `checked_at`, `generated_at`, and
arbitrary UI state are excluded. A proposal is stale when expired or when its
catalog source, compatibility evidence, source finding, or required evidence no
longer matches or resolves. Stale proposals remain inspectable but are not
actionable.

Compatibility is evidence, never execution permission. Compatible and
supported proposals may navigate to an existing authoritative surface;
incompatible proposals are review/troubleshooting-only; insufficient-information
proposals are review/investigation-only; unsupported resources never become
requestable. Destinations and intent hints use closed enums and mappings;
unknown or arbitrary routes, URLs, intents, provider actions, and parameters
fail closed.

### V0.10-P0 — Release-state and D9 boundary reconciliation

**Status: complete.**

- Goal: record final v0.9.0 and establish the authoritative D9 boundary.
- Deliverables: release-state consistency, proposal ownership, authority,
  identity, freshness, compatibility, navigation, milestones, and non-goals.
- Dependencies: final `atlas-v0.9.0` release.
- Non-goals: runtime, tests, deployment, security-control, or execution changes.
- Exit criteria: current documentation agrees and D9 cannot grant authority.

### V0.10-P1 — Sanitized proposal contracts and provenance

**Status: complete.**

- Goal: define immutable internal proposal contracts.
- Deliverables: frozen extra-forbid models, controlled enums, bounded fields,
  provenance, deterministic identity, expiry, and security tests.
- Dependencies: P0 and shipped Discovery contracts.
- Non-goals: routes, persistence, UI, candidates, operator intent, Agent, or providers.
- Exit criteria: contracts deterministically reject malformed or unsafe content.

### V0.10-P2 — Derivation, compatibility, and staleness

**Status: complete.**

- Goal: derive proposals from current catalog, compatibility, and D8 evidence.
- Deliverables: read-only derivation, source-state validation, closed hints,
  stale detection, and compatibility-specific navigation eligibility.
- Dependencies: P1.
- Non-goals: authoritative selection, candidate creation, or mutation.
- Exit criteria: changed, expired, missing, incompatible, and unsupported facts
  fail closed without making a resource requestable.

### V0.10-P3 — Authoritative navigation contract

**Status: complete.**

- Goal: navigate without transferring proposal authority.
- Deliverables: closed destination descriptors and fresh server-side reload of
  capability, selector, target, fingerprint, and operator authority.
- Dependencies: P2 and existing operator boundaries.
- Non-goals: copied authoritative fields or automatic submission.
- Exit criteria: stale or tampered navigation state cannot influence a request.

### V0.10-P4 — Mission Control proposal UX

**Status: complete.**

- Goal: present proposals, provenance, compatibility, and safe next steps.
- Deliverables: proposal list/detail, stale presentation, controlled navigation,
  and explicit advisory/non-authority messaging.
- Dependencies: P2 and P3.
- Non-goals: execute/install, approval, retry, or arbitrary parameter controls.
- Exit criteria: UI tests prove stale and unsupported proposals non-actionable.

### V0.10-P5 — Boundary integration and release acceptance

**Status: complete; immutable RC1 accepted for final promotion.**

- Goal: validate D9 end to end without widening execution.
- Deliverables: Core/UI boundary tests, Agent regressions, redaction and release
  gates, upgrade/rollback documentation, and acceptance evidence.
- Dependencies: P1 through P4.
- Non-goals: provider mutation acceptance or new execution capability.
- Exit criteria: proposals create no candidate, approval, action request, or
  dispatch record, and capability parity remains QEMU restart only.

P0 through P5 implementation is complete. The immutable `atlas-v0.10-rc1`
candidate at `95d98a4d5e0e9767dd6cb5df06c7ffdb693bf162` passed exact-SHA
Quality gates and Container release gate, `atlas-release-evidence-v1`, no-cache
production deployment with source/image parity, proposal redaction and
non-authority acceptance, and sequential Core, Mission Control, Agent, and Edge
restart soak. Capability parity remained exactly
`restart-service/proxmox/qemu`; the existing verified workflow and exactly-once
counts were unchanged. The immutable `atlas-v0.10.0` release was published at
`b19ded149f65dfb4043a1b80833e5ff64d83e55d`.

### V0.10 non-goals

V0.10 adds no operational intent, provider mutation handler, LXC or synthetic
LXC identity, backup/restore/install-provider/update-image execution, automatic
approval, direct Discovery dispatch, arbitrary provider action or parameter,
automatic retry or rollback, remote/distributed execution, automatic deployment
or tagging, Proxmox ACL expansion, proposal-derived target authority, D10
dynamic adapters, D11 semantic search, D12 community/private catalogs, or new
incident persistence subsystem. Repository execution remains separately gated
as `update-compose-stack`; operational execution remains exactly
`restart-service / proxmox / qemu`.

The first P1 code slice is limited to immutable internal
`DiscoveryOperatorProposal`, `DiscoveryProposalProvenance`,
`DiscoveryProposalCompatibility`, and `DiscoveryProposalDestination` contracts,
controlled status/reason enums, canonical fingerprinting, time/bounds
validation, and deterministic identity/staleness/security tests. It adds no API,
persistence, UI, candidate, operator-intent or Agent integration, provider call,
or mutation.

## Atlas v0.11 roadmap

**Theme: Provider Management Framework — Identity-Bound Runtime Intent**

Objective: establish a provider-management control plane in which durable user
intent is bound to the provider-authoritative incarnation of a managed
resource. The initial supported write direction is narrowly limited to Proxmox
QEMU monitoring intent until the identity and authenticated mutation contracts
prove safe; no other provider or resource type supports provider-intent writes.
The dependency order is
`V0.11-P0 → V0.11-P1 → V0.11-P2 → V0.11-P3 → V0.11-P4 → V0.11-P5`.

### Mutation and control boundaries

Provider intent is control-plane monitoring and policy state. It records what
Atlas should monitor or expect and is not infrastructure execution. Provider
actions are the existing legacy/generic provider-action subsystem; they are not
equivalent to hardened operational dispatch, and v0.11 does not expand them.
Operational production execution remains exactly `restart-service / proxmox /
qemu`, while repository execution remains the separate
`update-compose-stack` workflow.

For identity-capable managed resources, persisted intent must eventually bind
to provider-authoritative incarnation identity rather than reusable provider
coordinates alone. For Proxmox QEMU, a reused VMID must not silently inherit
intent after the authoritative incarnation identity changes. LXC has no
accepted authoritative incarnation identity, remains unsupported for
operational execution, and receives no synthetic identity.

Discovery proposals remain advisory, sanitized, non-authoritative, and unable
to directly create policy or execution authority. Proposal navigation or
content cannot authorize a provider-intent write or couple Discovery to
dispatch.

### V0.11-P0 — Release-state and provider-management boundary

**Status: complete when this documentation milestone is accepted.**

- Goal: reconcile final v0.10 state and define the authoritative v0.11 control,
  identity, ownership, milestone, and scope boundaries.
- Deliverables: final v0.10 release identity; provider-intent, provider-action,
  operational, repository, identity, Discovery, dependency, and non-goal
  contracts across authoritative documentation.
- Non-goals: runtime code, tests, provider state, configuration, permissions,
  gates, handlers, ACLs, or production execution changes.
- Exit criteria: documentation agrees on final v0.10 state and the complete
  v0.11 boundary without implying a new writable or executable capability.

### V0.11-P1 — Provider-management descriptors and identity contracts

- Goal: define provider-neutral management descriptors and explicit resource
  incarnation identity contracts.
- Deliverables: typed provider/resource capability descriptors, identity
  support status, canonical identity binding inputs, and fail-closed QEMU
  replacement semantics.
- Non-goals: persistence, mutation routes, UI writes, provider actions, or
  operational execution changes.
- Exit criteria: contracts distinguish reusable coordinates from authoritative
  incarnation identity and reject unsupported identity/write combinations.

### V0.11-P2 — Durable identity-bound Provider Intent Store

- Goal: persist provider intent as auditable runtime state bound to authoritative
  resource incarnation identity.
- Deliverables: versioned Provider Intent Store, atomic persistence, validation,
  migration/backup behavior, and QEMU VMID-reuse protection.
- Non-goals: mutation API, Mission Control editing, remediation, provider calls,
  or LXC intent synthesis.
- Exit criteria: intent survives restart, cannot transfer across a changed QEMU
  incarnation, and fails closed for missing or unsupported identity.

### V0.11-P3 — Authenticated provider-intent mutation boundary

- Goal: permit explicit authorized changes to supported provider intent without
  granting infrastructure execution authority.
- Deliverables: authenticated and permission-checked mutation contract, exact
  current-resource/identity revalidation, concurrency controls, audit evidence,
  and narrow Proxmox QEMU monitoring-intent writes.
- Non-goals: provider-action handlers, operational intents, execution gates,
  automatic approval/application, arbitrary parameters, or Discovery authority.
- Exit criteria: only an authenticated operator can mutate supported intent,
  stale/replaced identities fail closed, and no provider operation is invoked.

### V0.11-P4 — Coherent Mission Control provider experience

**Status: complete.** P4a, P4b, and composed P4c acceptance satisfy the UI and
authority-separation exit criteria. P5 remains next and unstarted.

- Goal: present provider resources, identity status, monitoring intent, actions,
  and diagnostics without conflating their authority.
- Deliverables: consistent Proxmox QEMU resource and monitoring-intent UX,
  Needs Review and unsupported-identity states, explicit approval/review, and
  clear separation from legacy actions and operational dispatch.
- Non-goals: writes for other providers/resource types, bulk mutation,
  execution controls, or conversational execution.
- Exit criteria: UI tests prove only supported QEMU monitoring intent is
  editable and no UI path implies automatic remediation or execution.

### V0.11-P5 — Advisory policy suggestions and release acceptance

- Goal: add reviewable suggestions and validate the complete identity-bound
  provider-intent boundary for release.
- Deliverables: advisory suggestion contracts and UX, explicit operator
  application flow, boundary/security regressions, documentation, and release
  acceptance evidence.
- Non-goals: automatic approval, automatic policy application or remediation,
  proposal-derived authority, rollback automation, or execution expansion.
- Exit criteria: suggestions cannot mutate policy without explicit authenticated
  operator action, replacement identity remains fail-closed, and execution,
  permissions, gates, handlers, and ACLs retain pre-v0.11 parity.

### V0.11 non-goals

V0.11 excludes backup execution, restore execution, install-provider execution,
update-image execution, new `restart-service` tuples, LXC operational execution,
synthetic LXC identity, new provider mutation handlers, new operational intents,
new execution-gate entries, Proxmox ACL expansion, arbitrary provider
actions/parameters, monitoring intent automatically causing remediation,
automatic approval, automatic policy application, proposal-derived authority,
Discovery-to-dispatch coupling, automatic rollback, remote deployment,
distributed orchestration, conversational execution, dynamic/community/private
Discovery catalogs, semantic catalog search, and bulk policy mutation.
