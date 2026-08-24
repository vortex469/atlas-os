# Atlas Discovery Center Roadmap

## Released baseline

Atlas v0.14.0 is released as `atlas-v0.14.0` at
`4d2526e1b022c5c36eaced65bf5b71703da5d2d7`.

Discovery is GET-only/read-only. It never installs, configures, approves,
executes, updates, deploys, rolls back, or publishes releases, and its evidence
does not grant Provider Intent, provider-action, operational, or repository
authority.

## Released D0-D10 history

- D0-D3: architecture, typed models, curated YAML loading, repositories, and
  deterministic search.
- D4-D6: public read-only API, initial catalog, and Mission Control.
- D7-D9: compatibility, Orion evidence consumption, and advisory proposal/
  navigation handoff.
- D10: bounded dynamic source adapters and the trust, merge, cache, offline,
  egress, health, and provenance contracts later released in v0.12.

These tracks are historical/completed, not current checkpoints.

## Released v0.12-v0.14 additions

- v0.12 released bounded dynamic Discovery refresh, deterministic curated plus
  dynamic projections, rebuildable cache, freshness/conflict handling, source
  health, provenance, and opt-in startup refresh.
- v0.13 released deterministic release evaluation, observed installed-version
  evidence, version-bound compatibility, and Mission Control upgrade
  intelligence.
- v0.14 released exact DeploymentBinding and Compose image observation,
  accepted immutable image-release evidence, informational grounding, and
  provenance. The generic image collector remains inactive with empty
  production registries and no startup or scheduled activation.

## Future D11 — Semantic Discovery

An uncommitted direction is optional semantic assistance grounded back to
structured catalog entries and evidence. It must not replace deterministic
search or make AI-only compatibility decisions.

## Future D12 — Community and Private Catalogs

An uncommitted direction is validated operator/community catalog extension
with explicit provenance, versioning, migration, conflict, and trust rules.
It must not enable unsandboxed third-party execution or secret distribution.

## Selected v0.15 — Deployment Image Grounding Operator Surface

The selected v0.15 theme is **Deployment Image Grounding Operator Surface**.
It is Discovery-facing: it presents the already-released read-only image
grounding and provenance as a bounded operator-facing surface. Neither D11
nor D12 is selected by v0.15.

Discovery-facing boundaries:

- The surface is read-only and informational; presentation grants no
  authority.
- Initial evidence breadth is the accepted Home Assistant `2026.8.3`
  registry-attested proof only.
- The generic image collector remains inactive; no scheduled or startup
  collection is added.
- Grounding, evidence, and provenance never create candidates, intents,
  approvals, action requests, or dispatches.
- The milestone dependency order is P0 → P1 → P2 → P3 → P4 → P5. P0 is the
  documentation-only scope-selection and boundary sign-off.
