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
- The generic image collector remains inactive; no startup, scheduled, or
  request-time collection is added.
- Grounding, evidence, and provenance never create candidates, intents,
  approvals, action requests, or dispatches.
- The milestone dependency order is P0 → P1 → P2 → P3 → P4 → P5. P0 is the
  documentation-only scope-selection and boundary sign-off.

Implementation is fixed by phase:

- **P1 — read model:** deterministically compose the existing
  `DeploymentBinding`, repository Compose observation, accepted evidence, and
  `ground_deployment_image` semantics. Preserve provenance and fail closed.
  Add no bindings or evidence; perform no network, acquisition, runtime
  verification, collection, clock-based decision, persistence, mutation, or
  execution. Home Assistant `2026.8.3` remains the only accepted proof.
- **P2 — Core projection:** add a bounded, additive, redacted GET-only
  projection with fail-closed statuses intact. Select exact endpoint and route
  placement during repository-grounded P2 implementation review. It has no
  mutation sibling, persistence, Agent dependency, provider mutation, or
  proposal/candidate/workflow creation. OpenAPI, method, redaction, and
  route-isolation tests are release gates.
- **P3 — Mission Control:** show status and provenance as advisory information,
  keep `REGISTRY_ATTESTED` distinct from `CURATED`, and show conflict, missing,
  and unknown states. There are no Apply, Execute, Update, Pull, Restart,
  Remediate, or workflow-conversion controls.
- **P4 — isolation:** prove empty production collector registries and absence
  of startup, scheduled, and request-time acquisition. A GET consumes only
  already-accepted local evidence and reviewed local readers and cannot trigger
  GHCR access, registry acquisition, Sigstore verification, collector
  execution, or evidence refresh. Also prove separation from
  mutation/execution, no silent precedence, redaction, and unchanged Provider
  Intent, capability, approval, no-replay, worker-default, and backup/restore
  contracts.
- **P5 — closure:** run focused and full Core validation, Agent regressions,
  Mission Control tests/lint/build, capability parity, and exact-SHA CI and
  container gates; then record read-only production acceptance,
  collector-inactivity evidence, documentation reconciliation, rollback, and
  release evidence.

P1 through P5 are sequential implementation milestones, not completed work.
