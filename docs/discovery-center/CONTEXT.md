# Discovery Center Current Context — v0.14

Discovery Center is Atlas's provider-neutral, local-first, read-only knowledge
and evidence surface. Its public API is GET-only and its Mission Control views
cannot create candidates, intents, actions, approvals, dispatches, updates, or
deployments.

## Current sources and authority

- Shipped curated YAML is authoritative catalog knowledge.
- Dynamic source facts and the rebuildable cache are supplemental evidence
  with provenance, freshness, source health, and deterministic conflict rules.
- Compatibility and release evaluation derive advisory results from curated
  requirements plus observed evidence.
- Proposals are sanitized navigation/advice. Their destination must freshly
  establish authority; a proposal grants none.
- V0.14 DeploymentBinding, exact repository Compose observation, accepted
  image-release evidence, grounding, and provenance are internal/read-only.
  Image evidence is informational and has no operational authority.

The generic image collector is inactive. Production descriptor and adapter
registries are empty, and no route, startup refresh, or scheduler wires it.
This is distinct from v0.12's bounded, opt-in dynamic Discovery refresh.

## Released evolution

D0-D9 established models, curated loading, deterministic search, public GET
API, Mission Control, compatibility, Orion evidence use, and advisory handoff.
D10 and v0.12 added bounded dynamic sources, merge/cache/offline behavior, and
provenance. V0.13 added observed-version and upgrade intelligence. V0.14 added
trusted Compose image observation and informational grounding.

## Boundaries and future

Discovery remains useful offline and fails to unknown/insufficient evidence
rather than inventing compatibility. It does not override Provider Intent,
provider-action, operational, repository, approval, or backup authority.
D11 semantic Discovery and D12 community/private catalogs remain uncommitted
future directions. The selected v0.15 theme, Deployment Image Grounding
Operator Surface, extends the released read-only grounding and provenance
into a bounded operator-facing presentation surface with initial evidence
breadth limited to the accepted Home Assistant `2026.8.3` proof; it adds no
collector, no scheduled collection, no authority of any kind, and no
Discovery-to-dispatch coupling.

## Historical D0 note

The original D0 plan described only a future curated catalog. That material is
historical: the catalog and subsequent D1-D10 capabilities have shipped and
must not be read as current future-tense scope.
