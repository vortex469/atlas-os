# Atlas Discovery Center Roadmap

## Released baseline

Atlas v0.15.0 is released as `atlas-v0.15.0` at
`850480ce6c5f86a5bf4a783e33f7e08a7f29a2ab`.

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

## Released v0.12-v0.15 additions

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
- v0.15 released the bounded Deployment Image Grounding Operator Surface.

## Future D11 — Semantic Discovery

An uncommitted direction is optional semantic assistance grounded back to
structured catalog entries and evidence. It must not replace deterministic
search or make AI-only compatibility decisions.

## Future D12 — Community and Private Catalogs

An uncommitted direction is validated operator/community catalog extension
with explicit provenance, versioning, migration, conflict, and trust rules.
It must not enable unsandboxed third-party execution or secret distribution.

## Released v0.15 — Deployment Image Grounding Operator Surface

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
- The milestone dependency order is P0 → P1 → P2 → P3 → P4 → P5. P0 through
  P5 and production acceptance are complete.

Implementation is fixed by phase:

- **P1 — read model (complete):** deterministically compose the existing
  `DeploymentBinding`, repository Compose observation, accepted evidence, and
  `ground_deployment_image` semantics. Preserve provenance and fail closed.
  Add no bindings or evidence; perform no network, acquisition, runtime
  verification, collection, clock-based decision, persistence, mutation, or
  execution. Home Assistant `2026.8.3` remains the only accepted proof.
- **P2 — Core projection (complete):** the bounded, additive, redacted GET-only
  projection at `GET /api/v1/discovery/items/{item_id}/image-grounding` keeps
  fail-closed statuses intact. It has no
  mutation sibling, persistence, Agent dependency, provider mutation, or
  proposal/candidate/workflow creation. OpenAPI, method, redaction, and
  route-isolation tests are release gates.
- **P3 — Mission Control (complete):** show status and provenance as advisory information,
  keep `REGISTRY_ATTESTED` distinct from `CURATED`, and show conflict, missing,
  and unknown states. There are no Apply, Execute, Update, Pull, Restart,
  Remediate, or workflow-conversion controls.
- **P4 — isolation (complete):** the authoritative validation matrix proved
  empty production collector registries and absence
  of startup, scheduled, and request-time acquisition. A GET consumes only
  already-accepted local evidence and reviewed local readers and cannot trigger
  GHCR access, registry acquisition, Sigstore verification, collector
  execution, or evidence refresh. Also prove separation from
  mutation/execution, no silent precedence, redaction, and unchanged Provider
  Intent, capability, approval, no-replay, worker-default, and backup/restore
  contracts.
- **P5 — closure (complete):** focused and full Core validation, Agent regressions,
  Mission Control tests/lint/build, capability parity, and exact-SHA CI and
  container gates; then record read-only production acceptance,
  collector-inactivity evidence, documentation reconciliation, rollback, and
  release evidence.

P5 release closure is complete at
`850480ce6c5f86a5bf4a783e33f7e08a7f29a2ab`.

## Selected v0.16 — Grounded Installation Planning

V0.16 is a bounded read-side consumer of released Discovery facts. P0 is
complete in the normative
[InstallationPlan v1 contract](../architecture/installation-plan-v1.md), and
the P1 assembler/P2 evaluator are complete and accepted. P3 is the next
implementation milestone; P4–P5 remain future work. It provides deterministic,
immutable, provenance-linked, ephemeral
`InstallationPlan` views answering what would be required to install an
application here.

- P0 freezes the exact closed schema/status/blocker vocabularies and total
  mapping, exact-time freshness, typed fingerprint, released-data evidence and
  provenance derivation, item-scoped target rejection, no-plan boundary,
  isolated modules, both legacy mounts, and the validation matrix.
- P0 also freezes a bounded raw-evidence adaptation boundary, the exhaustive
  evidence disposition/eligibility/reason relation, and closed typed catalog,
  compatibility, provenance, fingerprint, absence/conflict/unavailability,
  sorting, and identity inputs without invented malformed-record values.
- P1 (complete) assembles the Home Assistant reference deterministically. Its
  exact
  `compose/home-assistant.yaml` artifact is absent, so the only valid current
  outcome is `missing_deployment_artifact`—never a substitute artifact,
  mutable-image inference, or grounding-derived readiness. The accepted golden
  fingerprint is `34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a`.
- P2 (complete) evaluates readiness, blockers, risks, assumptions, missing
  facts, prerequisites, relationships, and confirmations without creating
  authority.
- P3 (next) exposes only a bounded GET read; it does not reuse or expand legacy
  `POST /analysis/deployments` or `POST /api/v1/analysis/deployments`, accept
  caller deployment documents, or persist.
- P4 presents read-only Mission Control review with no action or conversion
  controls. P5 validates isolation, authority parity, and release closure.

The exact v0.16 statuses are `plan_ready_for_review`,
`insufficient_information`, `incompatible`, `conflicted`, `stale_evidence`,
and `missing_deployment_artifact`; no additional v1 status is selectable. The
normative contract freezes their semantics, unknown behavior and precedence:
conflict cannot resolve to readiness, successful image grounding cannot
override a missing required deployment artifact, and absence of optional
context cannot invent compatibility.
Ready-for-review is not approved, executable, or deployable. Plans cannot
create candidates, intents, approvals, workflows,
dispatches, repository or worker execution, and cannot contain commands,
executable payloads, secrets, or credentials. V1 is item-scoped only; every
caller target selector is rejected with 422 and no approved installation-target
contract is selected.

Execution candidate generation, install-container execution, installation
intents, approved targets, conversational installation, generic collection,
D11, D12, distributed orchestration, and general VM/container lifecycle
management are explicitly deferred.
