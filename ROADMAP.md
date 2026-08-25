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
selection: no v0.16 milestone, including P0, is implemented or complete.

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

### P0 — InstallationPlan contract and threat model

P0 is documentation/architecture work and remains pending. It is not complete
until all decisions below are reviewed together:

- **Schema and version:** design an additive InstallationPlan read model, with
  `installation-plan-v1` as the proposed candidate version. Minimum information
  categories for P0 design, expressed as candidate fields, are
  `schema_version`, `plan_id`, `fingerprint`, `application`, `status`,
  `deployment_artifact`, `image`, `accepted_evidence`, `provenance`,
  `compatibility`, `prerequisites`, `relationships`, `assumptions`, `blockers`,
  `risks`, `missing_facts`, `required_operator_confirmations`, and optional
  `target_context`. P0 must review and freeze the exact schema version, closed
  field set, field types, required/optional classification, bounds,
  normalization, compatibility rules, and unknown-field behavior. P0 must also
  define deterministic collection ordering and explicit representation of
  unknown facts rather than omission or synthesis.
- **Status and blocker vocabularies:** the binding minimum v0.16 status concepts
  are `plan_ready_for_review`, `insufficient_information`, `incompatible`,
  `conflicted`, `stale_evidence`, and `missing_deployment_artifact`. P0 must
  define and freeze their exact versioned vocabulary, the exact semantics of
  each status, evaluation and transition rules, and unknown-value behavior. P0
  may add fail-closed status values only when required by the decision-complete
  threat/failure model and reviewed within P0. P0 must also define a closed,
  versioned blocker vocabulary covering at least missing or
  invalid artifacts, missing immutable image identity, missing/stale/untrusted
  evidence, provenance conflict, incompatibility, missing prerequisite facts,
  missing target identity, and required operator confirmation. Unknown blocker
  values fail closed.
- **Fingerprint:** hash a documented canonical serialization of
  `schema_version` plus every normalized decision input and provenance
  identity; exclude request time, presentation text, unordered input order,
  and transport metadata. Identical inputs produce identical fingerprints;
  any decision-relevant fact, freshness bucket, conflict, or target-context
  change changes the fingerprint. The fingerprint is identity/integrity
  information, not approval, freshness proof, or replay authority.
- **Provenance, freshness, and conflict:** every derived claim links to its
  sanitized source identity, source class, immutable evidence identity, and
  applicable observation/attestation time. Freshness is evaluated from one
  server-supplied evaluation instant under explicit source-specific windows.
  The binding minimum precedence constraints are that conflict cannot resolve
  to readiness, a missing required deployment artifact cannot be overridden by
  successful image grounding, and incompatibility cannot be erased by absence
  of optional context. P0 must define, review, test, and freeze the complete
  status/freshness/conflict/blocker precedence table. No newest-wins, trust
  promotion, voting, or fallback may silently resolve disagreement.
- **Payload allowlist:** only the named typed fields and bounded scalar/enum/
  relationship values are admitted. Unknown fields and opaque blobs fail
  closed. Commands, shell, argv, scripts, executable content, environment
  variables, credentials, secrets, secret-bearing URLs, and raw provider
  payloads are prohibited from inputs, plans, evidence, fingerprints, logs,
  and UI.
- **Lifetime and target context:** plans are assembled on read and are never
  durably stored. Optional target context is server-resolved, sanitized,
  read-only, informational, and non-authorizing. V0.16 introduces no approved
  installation-target contract. Existing Proxmox/QEMU restart identity grants
  no guest installation authority, and missing target identity is never
  synthesized.
- **Legacy isolation and dependencies:** the existing
  `POST /analysis/deployments` accepts caller-supplied deployment documents and
  returns its legacy analysis/planning proposal, including steps and an
  `approval_required` flag. It remains a separate legacy Forge analysis path.
  V0.16 must neither expand nor reuse it and must not translate its input or
  output into an `InstallationPlan`, candidate, intent, approval, or workflow.
  The new path may import only reviewed read-side Discovery/catalog,
  binding/observation, evidence/provenance, compatibility, and sanitization
  modules; imports from Agent, candidates, approvals, provider mutation,
  operational/repository execution, workers, maintenance, or the legacy deploy
  planner fail structural review.
- **Failure model:** malformed or unavailable input produces a bounded explicit
  non-ready status and blocker; it never raises readiness, drops a conflict,
  performs network acquisition, mutates state, or falls back to caller content.
  Missing artifacts and target identity cannot be fabricated. Timeout or
  internal failure returns a sanitized read error, never a partial positive
  plan.
- **Threat model:** address authority confusion, confused-deputy conversion,
  caller-controlled executable injection, secret leakage, provenance spoofing,
  mutable-image substitution, path traversal/symlink escape, stale-evidence
  replay, conflict suppression, fingerprint ambiguity, target-identity
  spoofing, enumeration, cache/persistence drift, unsafe rendering, and import
  coupling to mutation/execution.

P0's complete test matrix must be decision-complete before P1: schema/version
and unknown-field rejection; immutable/closed fields; every status and blocker;
canonical-order/fingerprint stability and sensitivity; provenance preservation;
freshness boundaries; conflict precedence; artifact/path/symlink failures;
mutable/missing/mismatched image failures; compatibility and prerequisite
combinations; optional target sanitization and missing identity; payload
allowlist, secret/URL redaction, command/executable rejection; no persistence,
network, clock ambiguity, or side effects; dependency/import isolation; legacy
POST isolation; GET/OpenAPI/unsupported-method behavior; deterministic Home
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
