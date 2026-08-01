# Atlas Discovery Center Architecture

Discovery Center is Atlas's provider-neutral catalog and compatibility subsystem. It owns structured knowledge about applications, services, container images, AI models, integrations, hardware devices, deployment methods, capabilities, requirements, and relationships.

D0 is documentation only. It defines the intended architecture and boundaries. It does not introduce runtime Discovery Center functionality.

## Purpose and scope

Discovery Center answers four questions:

1. What exists?
2. What does it provide?
3. What does it require?
4. Is it compatible with this Atlas environment?

Discovery Center is intentionally structured and deterministic before semantic or AI-based behavior. Its initial authoritative source is a curated YAML catalog. Dynamic ingestion, semantic discovery, and AI-assisted matching may supplement curated data later, but they must not silently replace curated facts.

## Non-goals

Discovery Center must not:

- Install packages.
- Start, stop, or modify containers.
- Modify provider configuration.
- Open ports.
- Write secrets.
- Apply recommendations.
- Execute deployment plans.
- Silently change Atlas policy or runtime configuration.

All future executable work must be handed to Atlas Agent and pass through approval-controlled planning, execution, verification, review, and commit workflow.

## Ownership boundaries

### Discovery Center

Discovery Center owns catalog knowledge and compatibility facts. It returns explainable, evidence-based answers about items, capabilities, requirements, relationships, and compatibility.

Discovery Center may say:

- PostgreSQL provides relational database capability.
- Immich requires PostgreSQL and Redis-like cache services.
- A model requires a minimum memory or GPU profile.
- A container image is compatible, incompatible, or unknown for the current Atlas environment based on explicit evidence.

### Orion

Orion owns recommendations.

Discovery Center may identify compatibility status and supporting evidence. Orion decides whether the user should install, change, investigate, defer, or ignore something, why it matters, and how urgent it is.

### Atlas Agent

Atlas Agent owns future execution handoff.

Discovery Center may provide structured context for a future change, but it must not execute that change. Any future executable work must cross the Atlas Agent approval boundary and use its planning, execution, verification, review, and commit workflow.

### Mission Control

Mission Control owns the user interface.

Mission Control should present catalog entries, compatibility evidence, provenance, and eventually Orion recommendations and Agent handoffs. Mission Control must not bypass Discovery Center's read-only default or Atlas Agent approval boundaries.

## Relationship to the Knowledge Engine

The existing Knowledge Engine contains the current YAML application catalog and assessment code. It is the current predecessor for structured application knowledge and a source of reusable concepts, including application definitions, image matching, resource recommendations, recommended ports, persistent paths, and environment-variable metadata.

D0 does not decide that Knowledge Engine becomes only a consumer of Discovery Center. D1-D3 must determine whether Discovery Center extends, migrates, absorbs, or replaces individual Knowledge Engine components.

The initial implementation should avoid duplicating Knowledge Engine concepts blindly. It should preserve useful YAML loading, validation, matching, and assessment behavior while defining a broader provider-neutral catalog contract.

## Relationship to infrastructure inventory and relationships

`inventory/services.yaml` currently describes known services for provider loading and health checks. Provider resources expose observed infrastructure such as Proxmox guests and Docker containers. Deployment analysis models components, ports, storage, dependencies, and health checks.

Discovery Center should not replace these sources. Instead, it should provide catalog knowledge that can be joined with observed inventory and provider resources.

Relationship terms include:

- depends-on
- provides
- consumes
- requires
- integrates-with
- conflicts-with
- runs-on
- deployed-by
- compatible-with
- incompatible-with

Dependencies are primarily relationships, not initial top-level discovery item types. A dependency may still be represented as a discovery item when it is independently discoverable, such as PostgreSQL, MQTT, Redis, or an Ollama model.

## Initial discovery item types

D0 defines these initial item types:

- application
- service
- container image
- AI model
- integration
- hardware device
- deployment method

Item types should be extensible without forcing every catalog entry into an application-centric schema.

## Capabilities and requirements

A capability describes what an item provides. Examples:

- relational-database
- object-storage
- reverse-proxy
- mqtt-broker
- gpu-inference
- home-automation
- video-ingest

A requirement describes what an item needs to function safely or correctly. Examples:

- minimum CPU, memory, storage, GPU, or architecture
- required runtime such as Docker or Kubernetes
- required dependent capability such as relational-database
- required environment variable or secret name
- required network access pattern
- required device class such as Coral TPU or NVIDIA GPU

Requirements must be structured enough for deterministic compatibility checks.

## Compatibility concepts

Compatibility is an evidence-backed status, not a recommendation.

Implemented statuses:

- compatible
- compatible_with_warnings
- insufficient_information
- incompatible

Unknown information is represented as `insufficient_information`. Unknown facts are not treated as success or warning.

A compatibility result should include:

- item id
- target environment or provider context
- status
- evidence list
- unmet requirements
- assumptions
- provenance
- checked_at timestamp when runtime data is used

Compatibility findings must be explainable without relying on AI interpretation. Semantic or AI-based behavior may rank, summarize, or assist later, but deterministic evidence must exist first.

## YAML catalog source-of-truth policy

The curated YAML catalog is the initial authoritative source for Discovery Center facts.

Rules:

- YAML files are read-only shipped catalog data in early phases.
- Catalog entries must validate against typed models before use.
- Invalid catalog entries fail safely with clear diagnostics.
- Dynamic ingestion may supplement curated entries later, but cannot silently override curated facts without provenance and conflict handling.
- Private and community catalogs are future work and must include trust and provenance metadata.

## Repository and service boundaries

The backend implementation lives under a provider-neutral Atlas Core namespace:

```text
services/atlas-core/app/discovery/
```

Initial runtime code should be independent of provider implementations. Provider data should enter Discovery Center through explicit projections rather than Discovery Center importing provider clients directly.

Implemented catalog data lives under:

```text
services/atlas-core/app/discovery/catalog/
```

or another reviewed source path selected in D1-D2. Runtime indexes and private catalogs, when implemented, should follow Atlas Runtime Foundation and use `data/knowledge/` or another documented runtime state location.

## Read-only API direction

The initial API should be read-only.

Implemented D7.5 routes:

```text
GET /api/v1/discovery
GET /api/v1/discovery/items
GET /api/v1/discovery/items/{item_id}
GET /api/v1/discovery/items/{item_id}/relationships
GET /api/v1/discovery/items/{item_id}/compatibility
GET /api/v1/discovery/search
```

The compatibility endpoint uses the current Atlas compatibility context and remains read-only. It must not write runtime state, secrets, policies, configuration, ports, containers, or packages. See [Discovery Center API Contract](API.md).

## Security boundaries

Discovery Center is read-only by default.

Security rules:

- No direct infrastructure mutation.
- No package installation.
- No container start/stop/create/delete.
- No configuration writes.
- No secret writes.
- No port changes.
- No provider credential access except sanitized metadata necessary for compatibility context.
- Dynamic ingestion adapters must be sandboxed by source, trust, and provenance rules.
- Any future execution must use Atlas Agent approval controls.

## Offline-first behavior

Discovery Center must work without internet access for curated local catalog data.

Offline-first rules:

- Local YAML catalog loads deterministically.
- Search and compatibility checks work from local data first.
- Dynamic sources are optional supplements.
- Missing external metadata should produce `insufficient_information`, not a hard failure when local data is sufficient.
- Online enrichment must be cached and provenance-tagged before use in future phases.

## Catalog trust and provenance

Every catalog fact should have a provenance trail.

Initial curated entries can use repository provenance:

- source type: curated
- source path
- catalog version or Git revision when available
- entry id

Future dynamic entries should include:

- source adapter
- fetched_at
- upstream URL or identifier
- trust level
- signature or checksum when available
- conflict status when dynamic facts disagree with curated facts

## Testing expectations

Discovery Center testing should be deterministic.

Expected test categories:

- YAML schema validation
- duplicate id rejection
- stable sorted repository output
- deterministic search ranking for exact and field-based queries
- compatibility status and evidence checks
- provenance preservation
- malformed catalog diagnostics
- API response contracts
- no side effects from read-only operations
- security tests proving no execution or secret writes occur
