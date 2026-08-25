# Atlas OS Roadmap

## 1. Current released baseline — v0.15

Atlas v0.15.0 is released as `atlas-v0.15.0` at
`850480ce6c5f86a5bf4a783e33f7e08a7f29a2ab` (2026-08-25).

The released system includes the hardened production topology; repository
candidate execution (`update-compose-stack`); operational dispatch
(`restart-service / proxmox / qemu`); identity-bound Proxmox QEMU
`monitoring-policy` Provider Intent; and Discovery through dynamic evidence,
compatibility/upgrade intelligence, exact Compose image observation, accepted
image evidence, grounding, and provenance.

## 2. Enduring architectural constraints

- Local-first, provider-neutral evidence precedes mutation.
- Curated authority and dynamic evidence remain distinguishable.
- Discovery stays GET-only/read-only and grants no operational authority.
- Legacy provider actions, Provider Intent, hardened operational dispatch, and
  repository execution remain separate authority surfaces.
- Provider Intent is limited to monitoring policy unless a future released
  contract deliberately changes it.
- Backup/restore remains operator maintenance tooling.
- No automatic remediation, approval, update, deployment, rollback, or release
  publication.
- New authority must fail closed, be explicitly activated, and be independently
  enforceable at each trust boundary.

## 3. Released history summary

- v0.6 completed the approval-gated repository candidate path for
  `update-compose-stack`.
- v0.7 introduced hardened operational restart for Proxmox QEMU.
- v0.8 improved effect clarity, lifecycle views, recovery UX, descriptors,
  and hardened ingress.
- v0.9 added recovery diagnostics, support bundles, and release evidence; LXC
  operational restart was rejected for lack of authoritative identity.
- v0.10 added advisory Discovery-to-operator proposal handoff.
- v0.11 released identity-bound Provider Intent for Proxmox QEMU monitoring.
- v0.12 released dynamic Discovery evidence, caching, freshness, and
  provenance.
- v0.13 released compatibility and upgrade intelligence.
- v0.14 released trusted Compose image observation and informational image
  grounding/provenance while leaving the generic collector inactive.
- v0.15 released the bounded Deployment Image Grounding Operator Surface.

The detailed v0.6-v0.15 milestone plans are historical and completed. Their
release records remain in [CHANGELOG.md](CHANGELOG.md), the release checklist,
and Git history; they are not current work queues.

## 4. Released v0.15 scope — Deployment Image Grounding Operator Surface

Atlas v0.15 has the theme **Deployment Image Grounding Operator Surface**. It
extends the released v0.14 read-only image grounding (exact repository Compose
image observation, accepted image-release evidence, and informational
grounding/provenance) into a bounded operator-facing presentation surface.

The milestone dependency order is P0 → P1 → P2 → P3 → P4 → P5. P0 is this
documentation-only, decision-complete architecture and boundary sign-off,
recorded in [CHANGELOG.md](CHANGELOG.md) and
[docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md). P0 through P5 and
production acceptance are complete. The release is `atlas-v0.15.0` at
`850480ce6c5f86a5bf4a783e33f7e08a7f29a2ab`.

### Scope

- The surface is read-only and informational. It presents already-accepted
  grounding and provenance to the operator; presentation derives no new
  authority.
- Initial evidence breadth is the accepted Home Assistant `2026.8.3`
  registry-attested proof only. No other release evidence is in scope.
- Discovery remains GET-only. Grounding, evidence, and provenance remain
  evidence, not authority, and never override curated data.

### Non-goals (binding for v0.15)

- No generic image collectors and no collector activation.
- No startup, scheduled, or request-time collection of any kind.
- No update, pull, install, restart, deploy, rollback, approval, or execution
  authority of any kind.
- No automatic remediation or automatic application.
- No Discovery-to-dispatch coupling: grounding, evidence, or provenance never
  create candidates, intents, approvals, action requests, or dispatches.
- Provider Intent remains limited to Proxmox QEMU `monitoring-policy`.
- Capability parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`; LXC remains unsupported.

### P1 — Binding-driven image-grounding read model

Implemented: one deterministic, fail-closed, local read-only composition path
for each catalog item. It consumes the item's existing `DeploymentBinding`, the
existing bounded repository Compose observation, the existing accepted image
evidence, and the existing `ground_deployment_image` semantics. The result
must preserve the observation and evidence provenance and every existing
non-grounded/conflict status; it must not add fallback precedence or infer a
positive result from missing, malformed, mutable, mismatched, untrusted, or
conflicting input.

P1 is composition only. Home Assistant `2026.8.3` remains the sole accepted
registry-attested proof. P1 must add neither evidence rows nor
`DeploymentBinding` entries, and must perform no network access, registry
acquisition, Sigstore runtime verification, collector activation, persistence,
clock-derived authority, mutation, or execution. Focused tests must prove
determinism, provenance preservation, the complete fail-closed status mapping,
and isolation from collectors and authority modules.

### P2 — GET-only Core grounding/provenance projection

Implemented at `GET /api/v1/discovery/items/{item_id}/image-grounding` as an
additive, bounded Core GET-only projection. The projection is redacted and
retains the exact fail-closed status and provenance distinctions;
unavailable data is represented explicitly rather than omitted in a way that
implies success. It has no mutation sibling.

The request path must not persist state, depend on Atlas Agent, mutate a
provider, or create a proposal, candidate, intent, workflow, approval, action
request, or dispatch. Contract, OpenAPI, method-rejection, route-isolation,
redaction, and authority-import tests are required. In particular, no route or
schema addition may make collector, provider, operational, repository, Agent,
or execution modules reachable from the projection.

### P3 — Mission Control advisory image-evidence surface

Implemented an explicitly **informational/advisory** presentation on the existing
Discovery item experience. It displays grounding status and sanitized evidence
provenance, visibly preserves `REGISTRY_ATTESTED` versus `CURATED`, and renders
grounded, conflict, missing, unknown, and other fail-closed states without
turning absence into a positive claim.

The surface has no Apply, Execute, Update, Pull, Restart, Remediate, approval,
or workflow-conversion control. It cannot create or navigate through a
proposal/candidate/workflow as a substitute for such a control. Tests must
cover status/provenance rendering, source-class distinction, missing and error
responses, accessibility, and the absence of mutation controls and requests.

### P4 — Security, isolation, and authority gates

Completed the authoritative structural and behavioral validation matrix proving
all of the following together:

- production image-collector descriptor and adapter registries remain empty,
  with no startup, scheduled, or request-time acquisition wiring;
- a grounding/provenance GET consumes only already-accepted local evidence and
  reviewed local readers and cannot trigger GHCR access, registry acquisition,
  Sigstore verification, collector execution, or evidence refresh;
- grounding/provenance imports and request paths cannot reach mutation or
  execution modules, and projected data excludes secrets, credentials, raw
  provider payloads, and commands;
- curated catalog authority is not silently displaced: `REGISTRY_ATTESTED`
  remains distinct from `CURATED`, conflicts fail closed, and no silent source
  precedence is introduced;
- Provider Intent remains identity-bound Proxmox QEMU `monitoring-policy`
  only; operational capability remains `restart-service/proxmox/qemu`,
  repository execution remains `update-compose-stack`, and LXC remains
  unsupported;
- independent, stage-specific approvals and interrupted-side-effect no-replay
  behavior remain unchanged;
- the execution-worker backend remains optional and default-disabled; and
- backup/restore remains explicit operator maintenance, outside Agent and
  Discovery authority.

### P5 — Release validation and closure

Completed focused Core grounding/API/isolation tests, the full Core suite,
Agent regression tests, and Mission Control tests, lint, and production build.
Capability parity, CI, and container release gates were validated, and
production acceptance remained read-only: it verified
the projected Home Assistant proof and fail-closed states, verified that
collector registries remained empty and acquisition remained inactive, and
verified that no mutation/execution request occurred.

Reconcile the roadmap, current context, README, changelog, Discovery docs, and
release checklist to the observed result. Record commands, outcomes, exact
SHA, image identities/digests, capability evidence, production read-only
acceptance, collector-inactivity evidence, and rollback guidance. Rollback is
the normal image/configuration rollback to the previously accepted release;
there is no data migration, evidence rollback, replay, or automated remediation
to perform because v0.15 adds no durable state or execution authority.

## 5. Selected v0.16 plan — Grounded Installation Planning

Atlas v0.16 is selected as **Grounded Installation Planning**. It will create
deterministic, immutable, provenance-linked, ephemeral `InstallationPlan` read
models answering: “What would be required to install this application here?”
The dependency order is P0 → P1 → P2 → P3 → P4 → P5. This is a planning-only
selection: P0 is complete as documentation/architecture only; no v0.16
production implementation exists and P1–P5 remain pending.

### Binding scope and authority boundary

An `InstallationPlan` is informational only. It may describe deployment
artifact requirements, immutable image identity, accepted evidence and
provenance, compatibility, storage/network prerequisites, relationships,
assumptions, blockers, risks, missing facts, and required operator
confirmation. It authorizes nothing and cannot generate an execution
candidate or installation intent; approve a plan or target; become a workflow;
dispatch an action; modify a repository; invoke a worker; install, restart,
remediate, roll back, or publish anything; or carry arbitrary commands,
executable payloads, secrets, or credentials.

`plan_ready_for_review != approved`, `plan_ready_for_review != executable`, and
`plan_ready_for_review != deployable`. Planning cannot silently become
approval, and approval cannot silently become execution.

### P0 — InstallationPlan contract and threat model — complete

P0 is complete as documentation/architecture work. The normative
[InstallationPlan v1 contract and threat model](docs/architecture/installation-plan-v1.md)
freezes the exact schema, six-status and blocker vocabularies, total precedence,
fingerprint, provenance/freshness/conflict semantics, item-scoped target
decision, failure/threat models, isolation rules, and P1–P5 validation matrix.
This completion implements no plan, endpoint, UI, test, or runtime behavior.

The superseded selection-time alternatives are omitted here. The finalized
decisions are: a closed `installation-plan-v1` schema and total state table;
exact-time freshness and typed fingerprint input; released-field-only evidence
and provenance derivation without trust promotion; all released relationship
kinds; and fail-closed target-free compatibility. V1 has no `plan_id`, target
field/selector, caller evidence, caller artifact, or caller source fact.
Required-reader, clock, schema, timeout and internal failures return sanitized
no-plan errors. The normative contract freezes the isolated module stack and
both legacy mounts.
The evidence adapter never invents normalized values for malformed input; the
normative contract exhaustively freezes evidence decision triples and closes
catalog, compatibility, provenance, fingerprint, absence, conflict, optional
source-unavailability, sorting, and compound-identity inputs.

P0's frozen test matrix requires: schema/version
and unknown-field rejection; immutable/closed fields; every status and blocker;
canonical-order/fingerprint stability and sensitivity; provenance preservation;
freshness boundaries; conflict precedence; artifact/path/symlink failures;
mutable/missing/mismatched image failures; compatibility and prerequisite
combinations; item-scoped target rejection and required missing identity; payload
allowlist, secret/URL redaction, command/executable rejection; no persistence,
network, clock ambiguity, or side effects; dependency/import isolation; both
legacy POST mounts; GET/OpenAPI/unsupported-method behavior; deterministic Home
Assistant missing-artifact behavior; UI rendering/accessibility/no controls;
authority/capability/no-replay/worker/backup regressions; and explicit tests
that ready-for-review is neither approval, executable, nor deployable.

### P1 — Deterministic Home Assistant Installation-Plan assembler

Implement a pure, local, deterministic assembler over reviewed read-side
inputs only. The current Home Assistant `DeploymentBinding` refers exactly to
`compose/home-assistant.yaml`, which is absent. Therefore its current plan must
fail closed as `missing_deployment_artifact`. Do not fabricate the artifact,
substitute another Compose file, infer a mutable image, or treat image
grounding as deployment readiness.

### P2 — Readiness, blocker, and risk evaluation

Evaluate the P0-frozen status/blocker vocabulary, risks, missing facts,
assumptions, prerequisite relationships, freshness, conflicts, compatibility,
and required confirmations deterministically. Evaluation remains descriptive;
it creates no approval or execution eligibility.

### P3 — GET-only Installation-Plan API

Add only a bounded, redacted GET projection for server-assembled plans, with no
POST/PUT/PATCH/DELETE sibling and no caller-supplied deployment document. It
must not persist a plan or reach the legacy analysis route, Agent, candidates,
approvals, providers, dispatch, repository execution, or workers.

### P4 — Mission Control Installation-Plan review

Present status, provenance, prerequisites, assumptions, blockers, risks,
missing facts, and confirmations as read-only review information. Provide no
approve, install, deploy, execute, convert, remediate, restart, or rollback
control, and never render unsafe opaque content.

### P5 — Authority isolation, release validation, and closure

Validate the complete P0 matrix, exact authority/capability parity, GET-only
behavior, absence of persistence and side effects, and the Home Assistant
fail-closed result. Release closure remains a future explicit operator action;
v0.16 performs no automatic push, tag, or publication.

## 6. Explicitly deferred work

- execution candidate generation and install-container execution;
- installation-intent lifecycle and approved installation targets;
- conversational execution or installation;
- generic image collection;
- D11 semantic Discovery and D12 community/private catalogs;
- distributed orchestration; and
- general VM/container lifecycle management.

## 7. Uncommitted future directions

The following remain uncommitted directions, not commitments:

- D11 semantic Discovery grounded in deterministic catalog/evidence results.
- D12 private and community catalogs with explicit provenance and trust rules.
- Additional provider, operational, or repository capabilities only after
  explicit identity, authority, approval, recovery, and validation contracts.
- Broader Agent knowledge and distributed orchestration where trust boundaries
  can remain local-first and reviewable.
- Generic image acquisition only if production activation, registry ownership,
  egress, verification, and non-authority contracts are separately approved.

No item above inherits commitment from an older deferred bullet.
