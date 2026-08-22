# Atlas Discovery Center Roadmap

Discovery Center is Atlas's provider-neutral catalog and compatibility subsystem. This roadmap describes direction and progress.

## Current implementation status (as of Atlas v0.13 implementation closure)

Implemented:

- D1 — Domain Models
- D2 — YAML Catalog Loader
- D3 — Repository and Deterministic Search
- D4 — Read-Only API
- D5 — Initial Curated Catalog
- D6 — Mission Control Integration (Discovery API client, typed contracts, browse page, item detail page, relationships, provenance display, and compatibility evidence display)
- D7 — Compatibility Engine
- D8 — Orion Integration through deterministic intelligence findings consumed by the recommendation pipeline

Completed in v0.10:

- D9 — Atlas Agent Proposal and Navigation Handoff

Completed in v0.12 (released as `atlas-v0.12.0`):

- D10 — Dynamic Source Adapters: one fixed Frigate GitHub latest-release
  adapter, with bounded read-only retrieval and rebuildable caching

Completed in v0.13 (publication and tag pending):

- Compatibility/Upgrade Intelligence — a deterministic, read-only release
  evaluation comparing the authoritative baseline version of a merged item
  against the freshest dynamic release evidence, observed installed-version
  evidence, version-bounds compatibility checks, and Mission Control upgrade
  presentation. It builds on D7 and D10 and adds no execution or mutation
  authority.

Deferred future work:

- D11 — Semantic Discovery: deferred beyond v0.12
- D12 — Community and Private Catalogs: deferred beyond v0.12

## D0 — Documentation

Goal: define the Discovery Center architecture, ownership boundaries, terminology, roadmap, context, and initial decisions.

Deliverables:

- Architecture document
- Roadmap
- Context document
- Decisions document
- Minimal root documentation links

Non-goals:

- Runtime code
- API routes
- Mission Control UI
- Catalog migration
- Execution handoff implementation

Exit criteria:

- Docs clearly state that Discovery Center is provider-neutral, offline-first, read-only by default, and YAML-catalog-first.
- Docs clearly state that Orion owns recommendations and Atlas Agent owns execution.

## D1 — Domain Models

Goal: define typed Discovery Center domain contracts.

Deliverables:

- Discovery item model
- Capability model
- Requirement model
- Relationship model
- Compatibility result model
- Provenance model
- Diagnostics model

Non-goals:

- Public API
- Mission Control UI
- Dynamic ingestion

Exit criteria:

- Models validate stable ids, item types, relationship types, requirement shape, compatibility statuses, and provenance.
- Existing Knowledge Engine concepts are evaluated for extension, migration, absorption, or replacement at component level.

## D2 — YAML Catalog Loader

Goal: load curated local YAML catalog entries deterministically.

Deliverables:

- Catalog file layout decision
- YAML loader
- Schema validation
- Duplicate detection
- Sorted deterministic load order
- Malformed-entry diagnostics

Non-goals:

- Network ingestion
- Semantic search
- Runtime catalog writes

Exit criteria:

- Valid YAML loads offline.
- Invalid YAML fails safely with clear diagnostics.
- Curated YAML remains the authoritative source for initial facts.

## D3 — Repository and Deterministic Search

Goal: provide an in-memory repository and deterministic search over loaded catalog data.

Deliverables:

- Discovery repository
- Exact id lookup
- Type filtering
- Capability and requirement filtering
- Relationship traversal primitives
- Deterministic text matching over structured fields

Non-goals:

- Embeddings
- AI ranking
- Online enrichment

Exit criteria:

- Search order is stable.
- Results explain why an item matched.

## D4 — Read-Only API

Goal: expose Discovery Center through versioned read-only Atlas Core routes.

Deliverables:

- `GET /api/v1/discovery/items`
- `GET /api/v1/discovery/items/{item_id}`
- `GET /api/v1/discovery/search`
- Read-only compatibility input endpoint if needed
- OpenAPI tests

Non-goals:

- Runtime writes
- Installation actions
- Secret handling

Exit criteria:

- API exposes no mutation route.
- Responses are typed, stable, and provenance-aware.

## D5 — Initial Curated Catalog

Goal: seed a small production-quality curated catalog.

Deliverables:

- Initial applications
- Initial services
- Initial container images
- Initial AI models
- Initial integrations
- Initial hardware devices
- Initial deployment methods

Non-goals:

- Broad ecosystem coverage
- Community catalogs

Exit criteria:

- Catalog entries are useful, validated, and traceable.
- Dependencies are modeled primarily as relationships.

## D6 — Mission Control Integration

Goal: provide a read-only Discovery Center UI in Mission Control.

Deliverables:

- Catalog browse page
- Item detail page
- Relationship display
- Provenance display
- Compatibility evidence display

Non-goals:

- Install buttons
- Configuration writes
- Secret inputs

Exit criteria:

- Users can inspect what Atlas knows without editing YAML.
- UI does not imply unsupported runtime functionality.

## D7 — Compatibility Engine

Goal: evaluate catalog requirements against the current Atlas environment with deterministic evidence.

Deliverables:

- Compatibility evaluator
- Environment projection inputs
- Provider-resource projection inputs
- Evidence and unmet requirement reporting
- `compatible`, `compatible_with_warnings`, `insufficient_information`, and `incompatible` statuses

Non-goals:

- Orion recommendations
- Agent execution
- AI-only compatibility decisions

Exit criteria:

- Compatibility findings are evidence-based and explainable.

## D8 — Orion Integration

Goal: allow Orion to consume Discovery Center facts and compatibility results when forming recommendations.

Deliverables:

- Read-only Orion service integration
- Recommendation context contracts
- Explainability links back to Discovery Center evidence

Non-goals:

- Discovery Center generating recommendations directly
- Silent policy changes

Exit criteria:

- Orion owns recommendation wording, priority, and urgency.
- Discovery Center remains the source of compatibility evidence.

## D9 — Atlas Agent Proposal and Navigation Handoff

Goal: define a safe proposal and navigation boundary from Discovery Center and
Orion into Atlas Agent-owned candidate pathways.

Deliverables:

- Sanitized proposal context shape
- Links into existing authoritative candidate or operator-intent entry points
- Provenance and compatibility evidence references
- Closed intent and exact-target preconditions

Non-goals:

- Direct Discovery Center execution
- Bypassing approval
- Creating an `OperationalActionRequest`
- Dispatching a mutation
- Supplying provider action ids or arbitrary action parameters

Exit criteria:

- Any D9 integration is proposal/navigation-only and cannot create a candidate,
  action request, or dispatch mutation.
- Any later executable work remains routed through authoritative candidate
  creation and Atlas Agent approval-controlled planning and execution.

D9 P0 through P5 implementation and local acceptance are complete. Atlas
Core's Discovery/intelligence layer owns proposals initially, and proposals are
derived rather than persisted. They are sanitized, provenance-bound,
stale-aware, and advisory. They may navigate only through closed destinations
and intent hints.

A proposal cannot create an `ExecutionCandidate` or
`OperationalActionRequest`, approve, dispatch, select an authoritative provider
resource, assert a target fingerprint, supply provider action IDs or arbitrary
parameters, or bypass authentication, capability, and selector boundaries. The
destination must freshly resolve current capability descriptors, authoritative
resources, target state/fingerprint, and operator authority. Expired or
source-mismatched proposals remain inspectable but non-actionable;
compatibility evidence never grants execution permission.

The shipped D9 surface consists of immutable proposal/provenance contracts,
stale-aware read-only derivation, bounded GET-only proposal APIs, closed
navigation, and Mission Control advisory presentation. Observed proposals are
retained only in a bounded process-local cache so stale/expired context remains
inspectable; there is no proposal database. The immutable `atlas-v0.10-rc1`
candidate passed exact-SHA CI, live bounded proposal API acceptance, redaction,
staleness and tampering tests, candidate-projector/non-authority regression,
no-cache production deployment, and restart soak. Proposal IDs remained stable
and no candidate, approval, action request, dispatch, provider operation, or VM
reboot was created. D9 was released in immutable `atlas-v0.10.0` at
`b19ded149f65dfb4043a1b80833e5ff64d83e55d`. Its proposals remain sanitized,
advisory, non-authoritative, and incapable of directly creating provider
policy or execution authority.

## D10 — Dynamic Source Adapters

Goal: supplement curated catalog data with optional dynamic sources.

Release mapping: D10 is the complete accepted theme for Atlas v0.12, **Dynamic
Discovery Sources**. D1 through D9 are prerequisites. D11 and D12 remain
separate later work and are neither dependencies nor deliverables of D10.

Deliverables:

- Adapter interface
- Source trust metadata
- Provenance records
- Conflict detection
- Offline fallback behavior

Non-goals:

- Silent overrides of curated data
- Required internet access

Exit criteria:

- Dynamic facts are clearly marked and never silently replace curated facts.

### D10 authority and source contract

Dynamic facts are read-only advisory evidence. They grant no permission or
execution and cannot mutate Provider Intent or `policies.yaml`, invoke provider
actions, create operational requests or execution candidates, approve work,
apply Discovery proposals, convert recommendations into authority, or cause
automatic remediation.

Each adapter has a closed, code-owned source ID and type. It retrieves from a
fixed allowlisted source, normalizes only recognized fields into strict typed
Discovery facts, attaches bounded provenance, and reports controlled healthy,
degraded, or unavailable state. It cannot write Atlas runtime state, modify a
provider, install software, or import mutation/execution services.

Every projected dynamic fact includes its source ID/type, safe source-origin
classification, supplemental trust tier, retrieval timestamp, freshness and
expiry state, source health, exact normalized provenance, and conflict state.
Raw remote payloads are not authoritative and are neither exposed nor retained
as unbounded catalog state.

These fields use closed values. Source IDs are canonical bounded identifiers
registered in code, and source types are registered adapter literals. The
initial origin class is `public_https_allowlisted`; trust is `supplemental`;
freshness is `fresh`, `stale`, or `expired`; health is `healthy`, `degraded`, or
`unavailable`; and conflict is `none`, `agreement`, `dynamic_conflict`, or
`curated_conflict`. Unknown values fail validation rather than widening the
contract.

### D10 deterministic merge and conflict behavior

- Curated and dynamic agreement retains both provenances and may present one
  agreed claim.
- Agreement among dynamic sources retains every contributing provenance.
- Dynamic disagreement projects an explicit conflict and selects no dynamic
  winner.
- A dynamic/curated disagreement preserves the curated fact and projects the
  supplemental claim as conflicting; it never overwrites curated data.
- Stale cache is visibly stale and cannot satisfy a fresh-data claim.
- Unavailable sources contribute health state and may contribute explicitly
  stale cache, but do not remove curated results.
- Malformed responses are rejected as controlled degraded/unavailable source
  state and do not partially publish facts.
- Canonical source/fact keys and stable sort rules make merged output independent
  of adapter completion order.

### D10 cache, offline, and recovery contract

Normalized source generations use a bounded, versioned, checksummed, atomic,
rebuildable cache under `/opt/atlas/data/cache/discovery/`. TTL is evaluated
against recorded retrieval and expiry times. Fresh generations participate in
normal reads; stale generations may be displayed only with explicit stale state;
expired, malformed, or corrupt generations are excluded from facts. Failure is
isolated per source, deletion is always safe, and cache absence never prevents
startup or curated catalog use.

The shipped curated catalog remains fully available without network access.
Optional source failure cannot make Core startup fail or make local search and
compatibility unusable. Pure cache is excluded from authoritative backup and
restore inventory, so D10 requires neither a change to
`atlas-core-data-backup-v3` nor backup v4. Operator-managed source configuration
is deferred; any later durable configuration must be separate from cache and
receive explicit authentication, migration, backup, restore, and recovery
contracts.

### D10 egress and user-interface contract

Adapters are not arbitrary URL fetchers. Initial sources are fixed and
code-owned, HTTPS-only, bounded by connect/read/total timeouts and response-size
limits, require an expected machine-readable content type, and follow no
redirect unless a separately bounded same-origin policy is accepted. DNS and
connected destinations must reject loopback, link-local, private, reserved,
metadata, and other disallowed networks. The initial adapter should require no
credential; future credentials must never appear in URLs, logs, errors, cache,
provenance, or public contracts. Logs contain only sanitized identifiers,
controlled reasons, health, and bounded timing.

Mission Control presents provenance, trust, freshness, stale/expired state,
source health, conflicts, degraded/offline behavior, and curated-only fallback.
Dynamic evidence creates no Apply, Execute, Fix, or Remediate control.

### D10 first-adapter decision

Accepted for v0.12: `frigate-github-latest-release-v1`, a fixed, code-owned,
unauthenticated adapter for the Frigate GitHub latest-release JSON endpoint.
It is HTTPS-only and allowlisted, uses `supplemental` trust and
`public_https_allowlisted` origin classification, and supplies only bounded
read-only evidence for the curated `frigate` item. It is not an operator-managed
source and grants no authority. Additional adapters remain deferred until
separately reviewed.

## v0.13 — Compatibility/Upgrade Intelligence

**Status: P1–P5 implemented; publication and tag pending.** Evidence-bound to
the commit span `1df238c` through `64e8341`. Atlas v0.13 turns the released v0.12
dynamic Discovery facts into bounded, read-only upgrade intelligence. It builds
on D7 (compatibility) and D10 (dynamic sources) and adds no new discovery item
type, endpoint, or mutation authority.

### Release goal and authority boundary

The release evaluation is derived, not persisted, and is additive and optional in
`discovery-merged-item-v1`. It compares the authoritative baseline version of a
merged item against the freshest dynamic release evidence and evaluates observed
installed versions against curated version bounds. The curated catalog remains
authoritative; dynamic and observed facts remain evidence, not authority, and
never override curated data.

Release evaluation, version-bounds compatibility, and upgrade presentation add
no permission, execution, or mutation authority. They create no Provider Intent,
policy, proposal, approval, provider action, operational request, execution
candidate, or remediation. Discovery remains `GET`-only and read-only.

### v0.13-P1 — Discovery release evaluation

**Status: complete.** `1df238c`.

- A bounded, deterministic, side-effect-free release-evaluation contract.
- An additive, optional `release_evaluation` field on `discovery-merged-item-v1`.
- A typed cross-field invariant with `conflict_state`.
- Route and OpenAPI contract tests; legacy item schemas remain unchanged.
- Exactly the eight bounded statuses: `no_baseline`, `no_dynamic_evidence`,
  `insufficient_information`, `stale_evidence`, `conflicted`, `up_to_date`,
  `update_available`, and `baseline_ahead`. `baseline.source` is exactly
  `curated` or `item_version`.

### v0.13-P2 — Observed installed version evidence

**Status: complete.** `286521b`.

- A provider-neutral, advisory `installed_version` observation on
  compatibility-context services.
- A strict numeric `X.Y.Z` comparison key.
- A missing or non-strict version is unknown and never yields a positive
  assertion.

### v0.13-P3 — Version-bounds compatibility

**Status: complete.** `4fe0c23`.

- Deterministic `version` compatibility checks comparing an observed installed
  version against a required relationship's curated `minimum_version` and
  `maximum_version` bounds.
- Below-minimum or above-maximum is `incompatible`; a satisfying version is
  `compatible`; a missing or non-strict version is `insufficient_information`.
- Adds no execution or remediation authority.

### v0.13-P4 — Mission Control upgrade intelligence

**Status: complete.** `7d77bf7`.

- An advisory release-evaluation notice on the Discovery evidence panel showing
  the bounded status, baseline, and latest candidate.
- No Apply, Execute, update, remediate, or other mutation control.

### v0.13-P5 — Release isolation/readiness validation

**Status: complete.** `64e8341`.

- Isolation tests proving the release-evaluation module has no I/O, network,
  cache, or application-module coupling beyond its two reviewed Discovery
  consumers in `discovery/compatibility.py` and
  `discovery/dynamic_projection.py`.
- The module is side-effect-free and references only those two consumers.

### v0.13 non-goals

v0.13 adds no execution intent, provider mutation handler, LXC or synthetic LXC
identity, backup/restore/install-provider/update-image execution, automatic
approval, direct Discovery dispatch, arbitrary provider action or parameter,
automatic retry or rollback, remote/distributed execution, automatic deployment
or tagging, Proxmox ACL expansion, proposal-derived target authority, automatic
remediation, or a new backup format. Repository execution remains separately
gated as `update-compose-stack`; operational execution remains exactly
`restart-service / proxmox / qemu`. The rebuildable Discovery cache remains
excluded from backup v3. D11 semantic discovery and D12 community/private
catalogs remain deferred.

## D11 — Semantic Discovery

Goal: add semantic assistance on top of structured deterministic discovery.

Deliverables:

- Optional semantic index
- Local-first search path where practical
- Explainable mapping back to structured facts

Non-goals:

- Replacing deterministic search
- AI-only compatibility decisions

Exit criteria:

- Semantic results remain grounded in catalog entries and evidence.

## D12 — Community and Private Catalogs

Goal: support operator-owned and community catalog extensions.

Deliverables:

- Private catalog location under runtime state
- Community catalog trust model
- Versioning and migration policy
- Conflict and override rules

Non-goals:

- Unsandboxed third-party execution
- Secret distribution

Exit criteria:

- Private and community catalog entries are validated, provenance-tagged, and safely separable from shipped curated data.

## v0.6 Phase 3 status

Discovery Center now feeds the completed Phase 3 candidate pipeline by providing deterministic catalog and compatibility evidence to Atlas intelligence and execution-candidate projection. Discovery remains provider-neutral and read-only. It does not install, configure, execute, push, tag, release, deploy remotely, approve, or roll back changes.

The only supported downstream execution intent in v0.6 is `update-compose-stack`, and any execution must pass through Atlas Agent planning, immutable requests, exact approvals, verification, deterministic review, and local commit.
