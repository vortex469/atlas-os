# Atlas Discovery Center Roadmap

Discovery Center is Atlas's provider-neutral catalog and compatibility subsystem. This roadmap describes direction and progress.

## Current implementation status (as of Atlas v0.8.0)

Implemented:

- D1 — Domain Models
- D2 — YAML Catalog Loader
- D3 — Repository and Deterministic Search
- D4 — Read-Only API
- D5 — Initial Curated Catalog
- D6 — Mission Control Integration (Discovery API client, typed contracts, browse page, item detail page, relationships, provenance display, and compatibility evidence display)
- D7 — Compatibility Engine
- D8 — Orion Integration through deterministic intelligence findings consumed by the recommendation pipeline

Future beyond the shipped D1–D8 baseline:

- D9 — Atlas Agent Proposal and Navigation Handoff
- D10 — Dynamic Source Adapters
- D11 — Semantic Discovery
- D12 — Community and Private Catalogs

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

D9 remains separate proposal/navigation-only future work and is not part of the
Atlas v0.9 Operational Recovery and Evidence Automation release scope.

## D10 — Dynamic Source Adapters

Goal: supplement curated catalog data with optional dynamic sources.

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
