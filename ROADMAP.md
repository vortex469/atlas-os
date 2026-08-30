# Atlas OS Roadmap

## 1. Current released baseline — v0.36

Atlas v0.36.0 is released as `atlas-v0.36.0` at
`d02e04126fd4a897c9faaab0f68b49d84f218044`; its completed milestone and
release-checklist reconciliation are merged to current `main` at
`0b23b2c292e65b293a8097c74c3ab11b5d3295dd`.

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
- v0.16 released immutable, target-free Grounded Installation Planning.
- v0.17 released operator-owned Prospective Installation Destination
  Assessment.
- v0.18 released ephemeral, non-authorizing Installation Capability
  Assessment.
- v0.19 released ephemeral Installation Candidate Admission whose strongest
  result is `admitted_but_non_executable`.
- v0.20 released bounded durable preservation of an exact non-executable
  installation candidate record without adding an authority consumer.
- v0.21 released an immutable operator approval statement for one exact
  non-executable candidate without adding an execution consumer.
- v0.22 released a closed validation-only Agent install-container contract and
  non-authorizing evidence while keeping runtime intake unsupported.
- v0.23 released an immutable, record-only installation execution request
  binding v0.20–v0.22 without adding a consumer or dispatch authority.
- v0.24 released a prepared, non-delivered dispatch handoff envelope binding
  v0.20–v0.23 without adding live Agent delivery or admission.
- v0.25 released an explicitly constructed Agent intake simulation path and
  durable evidence without adding a production intake surface or receipt.
- v0.26 released explicitly constructed in-process simulated delivery and
  acknowledgement evidence without adding live transport, receipt, admission,
  or execution authority.
- v0.27 released an explicitly constructed authenticated real-intake evidence
  boundary and dormant test-only Agent route factory without production Core
  delivery, Agent registration, or execution authority.
- v0.28 released explicitly constructed dormant Core delivery preparation and
  injected-response validation without a send method, production transport,
  credential loading, Agent invocation, or execution authority.
- v0.29 released guarded durable delivery-activation preflight evidence over
  the exact v0.20–v0.28 chain while remaining non-activating and non-sending.
- v0.30 released guarded durable operator enablement evidence over a fresh
  same-owner v0.20–v0.29 chain without adding a send or execution consumer.
- v0.31 released an explicitly constructed, default-disabled, one-shot live
  HTTPS send of an inert evidence envelope, with permanent no-replay and
  terminal ambiguity, while Agent intake remained dormant and unregistered.
- v0.32 released independently default-off Agent live intake admission for the
  inert envelope without installation execution authority.
- v0.33 released a durable inert Core receipt binding the complete delivered
  evidence chain without adding an effect consumer.
- v0.34 released authenticated read-only installation readiness review over
  the exact v0.20–v0.33 chain; even `readiness_gated` leaves execution
  admission undefined.
- v0.35 released durable operator permission evidence over the exact
  v0.20–v0.34 chain without execution admission or an effect consumer.
- v0.36 released durable installation-execution admission evidence over the
  exact v0.20–v0.35 chain while remaining `admission_gated`, with no runner
  binding, execution-start boundary, or effect consumer.

The detailed v0.6-v0.15 milestone plans are historical and completed. Their
release records remain in [CHANGELOG.md](CHANGELOG.md), the release checklist,
and Git history; they are not current work queues.

## Selected v0.37 plan — Runner Binding Plan

Atlas v0.37 selects **Runner Binding Plan**. The normative documentation-only
P0 contract is [Runner Binding Plan v1](docs/architecture/runner-binding-plan-v1.md).

V0.37 may append one same-owner Core plan-evidence record binding the complete
v0.20–v0.35 evidence/permission chain, one active v0.36 admission, one abstract
eligible runner reference, and exact confined sandbox/resource/network/
filesystem ceilings. Its strongest state is `binding_planned`, permanently
blocked by `runner_not_bound` and `execution_start_boundary_not_defined`. It
does not register, contact, reserve, bind, or invoke a runner.

The phase order is P0 → P1 → P2 → P3 → P4 → P5:

- P0 freezes exact models, runner reference, fingerprints/linkage, lifecycle,
  eligibility/blockers, ownership/permissions, freshness, limit semantics,
  permanent reservations, audit/redaction, API/UI, threats, later enablement,
  and must-not-change contracts. P0 changes planning documents only.
- P1 adds closed immutable models, deterministic domain-separated
  fingerprints, bounds, and pure validation only.
- P2 adds an explicitly constructed default-off Core append-only plan-evidence
  service/store with injected owner-scoped readers and permanent no-replay.
- P3 adds only dedicated record/read permissions and candidate-scoped
  collection GET/guarded POST plus owned item GET.
- P4 adds only a strict Mission Control evidence panel and two-step record
  flow, with no polling, live runner selector, editable limit, or effect
  control.
- P5 adds isolation, concurrency/no-replay, regression, authority, redaction,
  Agent parity, Home Assistant, and release evidence only.

V0.37 enables a later milestone to require an active runner-binding plan before
separately specifying authenticated live runner binding. Runner discovery,
registration, endpoint/credential access, contact, reservation, binding,
invocation, execution authorization/start, installation, worker/workflow,
dispatch, retry/resend, Agent invocation, Docker/Podman/shell/process,
provider/repository/in-guest mutation, deployment, rollback, and Home Assistant
artifacts remain blocked.

## Completed v0.36 plan — Installation Execution Admission Boundary

Atlas v0.36 selects **Installation Execution Admission Boundary**. The
normative documentation-only P0 contract is [Installation Execution Admission
v1](docs/architecture/installation-execution-admission-v1.md).

V0.36 may append one same-owner Core admission-evidence record binding the
complete v0.20–v0.34 evidence/readiness chain and an active v0.35 permission
grant. Its strongest readiness is `admission_gated`, permanently blocked by
`runner_binding_not_defined` and `execution_start_boundary_not_defined`. It
does not select or invoke a runner and grants no execution or mutation
authority.

The phase order is P0 → P1 → P2 → P3 → P4 → P5:

- P0 freezes exact models, linkage/fingerprints, readiness/blockers,
  eligibility evidence, lifecycle, ownership/permissions, freshness,
  permanent reservations, audit/redaction, API/UI, threats, later enablement,
  and must-not-change contracts. P0 changes planning documents only.
- P1 added closed immutable models, deterministic domain-separated
  fingerprints, bounds, and pure validation only.
- P2 added an explicitly constructed default-off Core append-only evidence
  service/store with injected owner-scoped readers and permanent no-replay.
- P3 added only dedicated record/read permissions and candidate-scoped
  collection GET/guarded POST plus owned item GET.
- P4 added only the strict Mission Control evidence panel and two-step record
  flow, with no runner selector, polling, or effect control.
- P5 added isolation, concurrency/no-replay, regression, authority, redaction,
  Home Assistant, and release evidence only.

V0.36 enables a later milestone to require active admission evidence before a
separately specified runner-binding or execution-start decision. Runner
selection/registration/invocation, executable intent, installation, execution,
dispatch, retry/resend, Agent invocation, worker/workflow/process start,
Docker/Podman/shell, provider/repository/in-guest mutation, deployment,
rollback, credentials, and Home Assistant artifacts remain blocked.

## Completed v0.35 plan — Execution Permission Grant Boundary

Atlas v0.35 selects **Execution Permission Grant Boundary**. The normative
documentation-only P0 contract is
[Execution Permission Grant v1](docs/architecture/execution-permission-grant-v1.md).
It freezes one durable, operator-owned Core evidence artifact binding the exact
v0.20–v0.33 chain, v0.34 readiness review, authenticated operator, exact
confirmation text, short inherited freshness, and permanent no-replay.

The grant records only permission for the exact evidence chain to be considered
by a later, separately released execution-admission boundary. It does not
admit or authorize execution, install, dispatch, invoke Agent, start a worker
or workflow, mutate any provider/repository/guest, deploy, or roll back.

The phase order is P0 → P1 → P2 → P3 → P4 → P5:

- P0 freezes exact models, linkage/fingerprints, confirmation, ownership,
  freshness, lifecycle, permanent reservations, redaction/audit, API/UI,
  authority, threats, goldens, and must-not-change contracts. P0 changes
  planning documents only.
- P1 added closed immutable create/linkage/grant/status/result/audit/error,
  idempotency, and permanent-reservation models, domain-separated
  fingerprints, and pure same-owner, permission, freshness, expiry, authority,
  and Home Assistant blocked-golden validation only.
- P2 added an explicitly constructed default-off append-only Core service/store
  with atomic durable sanitized audit evidence, permanent review-subject and
  idempotency reservations, owner-scoped restart readback, quotas, corruption
  checks, and no external I/O or authority consumer.
- P3 added only the dedicated create permission, independent owned-read
  permission, candidate-scoped collection GET/guarded POST, and owned item GET,
  with strict parsing, security gates, redaction, an independent durable
  database setting, and no execution or action sibling.
- P4 added only the exact Mission Control confirmation/readback panel in the
  v0.34 review context: strict P3 create/list/get parsing, a two-step exact-text
  evidence confirmation, lifecycle/freshness/linkage/audit readback, and
  fixed-false authority presentation with no polling, retry, or effect control.
- P5 closed the milestone with exact Core route isolation, fixed-false
  authority, concurrent and restart-safe permanent reservation/no-replay
  validation, sensitive persistence/rendering exclusion, a v0.34 consumer
  allowlist, Mission Control structural isolation, Agent regression coverage,
  and the blocked/non-artifact Home Assistant golden. P0–P5 are complete.

V0.35 authority ends at append-only permission evidence. It enables a future
milestone to require that evidence as one prerequisite for a separately
specified execution-admission decision. Actual installation, admission,
execution, dispatch, retry/resend, Agent invocation, worker/workflow/process
start, Docker/Podman/shell, provider/repository/in-guest mutation, deployment,
rollback, credential access, and Home Assistant artifacts remain blocked.

## Selected v0.34 plan — Installation Readiness Review

Atlas v0.34 selects **Installation Readiness Review**. The normative
documentation-only P0 contract is
[Installation Readiness Review v1](docs/architecture/installation-readiness-review-v1.md).
It freezes one authenticated, owner-scoped Core GET and one read-only Mission
Control view over the complete v0.20–v0.33 evidence chain.

The review has only `blocked` and `readiness_gated` outcomes. Even the latter
retains the blocker `execution_admission_not_defined`; it is not approval,
admission, authorization, installability, or executability. Core reads only
existing local owner-scoped evidence, recomputes every released fingerprint,
and creates no durable review record, reservation, refresh, retry, or effect.

The phase order is P0 → P1 → P2 → P3 → P4 → P5:

- P0 freezes the exact review/linkage/summary/audit schemas, blocker vocabulary,
  ownership, time interpretation, redaction, API/UI, authority, threats,
  goldens, and must-not-change contracts. P0 changes planning documents only.
- P1 added closed immutable linkage/summary/review/audit/error/result models,
  deterministic fingerprints, strict bounds, and pure review evaluation only.
- P2 added an explicitly injected Core-local owner-scoped evidence reader and
  trusted clock composition, with redacted errors and no persistence,
  reservation, credential access, or external I/O.
- P3 added the sole authenticated read-only Core GET and exact OpenAPI surface,
  with owner non-disclosure, redacted errors, and no body, query, CSRF mutation,
  collection, action, or non-GET sibling.
- P4 added the sole strictly parsed read-only Mission Control GET client and
  candidate-context page/route, with no polling, mutation, retry, resend,
  admit, install, execute, dispatch, workflow, rollback, or deploy control.
- P5 completed cross-layer isolation, regression, authority, redaction, Home
  Assistant, and release validation evidence only, with no runtime change or
  release action.

V0.34 authority ends at an ephemeral read-only projection. Installation,
execution, dispatch, retry/resend, Agent invocation, worker/workflow/process
start, provider/repository/in-guest mutation, deployment, rollback, credential
access, and Home Assistant artifacts remain blocked.

P0–P5 are complete. V0.34 enables only authenticated inspection of the exact
released evidence chain; a later milestone must separately define any
execution-admission authority.

## Selected v0.33 plan — End-to-End Inert Delivery Receipt

Atlas v0.33 selects **End-to-End Inert Delivery Receipt**. The normative
documentation-only P0 contract is
[End-to-End Inert Delivery Receipt v1](docs/architecture/end-to-end-inert-delivery-receipt-v1.md).
It freezes the narrowest independently default-off composition of one v0.31
permanently reserved Core send attempt, one exact v0.32 inert envelope and
Agent admission response, and one append-only Core-owned verified receipt.

The complete same-owner v0.20–v0.32 evidence graph and inherited maximum
30-second window remain exact. V0.33 reuses the existing HTTPS path, fixed Core
principal, mode-0400 credential references, one-shot/no-retry transport, and
closed Agent result. It adds no callback, second Agent route, public Core API,
Mission Control surface, or claim that Core directly read Agent-local storage.

The phase order is P0 → P1 → P2 → P3 → P4 → P5:

- P0 freezes schemas, verification, fingerprints, linkage, ownership,
  transport/authentication, freshness, lifecycle, permanent no-replay,
  redaction/audit, API/UI, authority, threats, goldens, and invariants.
- P1 added closed immutable models and pure verification only.
- P2 added a default-off append-only Core verification service/store with no
  network or production consumer.
- P3 added the explicitly constructed one-shot composition through injected
  transport/credential dependencies, with terminal ambiguity and no retry.
- P4 keeps Mission Control and public Core API absent and now locks that
  absence structurally, including sensitive rendering and Home Assistant
  exceptions.
- P5 completed isolation/regression/authority validation: explicit internal-
  only composition, exact duplicate zero-I/O behavior, append-only secret-free
  evidence, fixed-false effect authority, zero production consumers, preserved
  v0.31 one-shot send and v0.32 admission-only boundaries, absent public Core
  and Mission Control surfaces, and Home Assistant blocking. It adds tests and
  release evidence only.

V0.33 authority ends after one authenticated inert POST and one verified Core
receipt. It enables only a later release to consider that fresh receipt as one
prerequisite for a separately confirmed execution-admission decision. Install,
runtime/process execution, dispatch, worker/workflow start, retry/resend,
provider/repository/in-guest mutation, deployment, rollback, public API/UI,
credential management, and Home Assistant artifacts remain blocked.

P0 through P5 are complete. Closure passed both Core and Agent Ruff gates, all
3107 Core tests, all 1045 Agent tests, and all 555 Mission Control tests plus
lint/build and `git diff --check`.

## Selected v0.32 plan — Agent Live Intake Admission

Atlas v0.32 selects **Agent Live Intake Admission**. The normative
documentation-only P0 contract is
[Agent Live Intake Admission v1](docs/architecture/agent-live-intake-admission-v1.md).
It defines the narrowest default-off production Agent registration that may
authenticate one fixed Core principal, receive one bounded inert v0.31
envelope, and append one durable evidence-only admission and acknowledgement.

The admission input binds the complete same-owner v0.20–v0.30 linkage and the
v0.31 permanently reserved send attempt. The Agent response is causally prior
to, and becomes input to, the v0.31 Core receipt/result; the receipt therefore
cannot be an Agent admission prerequisite. The inherited maximum freshness is
30 seconds. Authentication uses an injected mode-0400 credential reference;
secret material is never modeled, persisted, logged, returned, or exposed in
OpenAPI.

The phase order is P0 → P1 → P2 → P3 → P4 → P5:

- P0 freezes the exact schemas, fingerprints, lifecycle, ownership,
  authentication, freshness, no-replay, redaction, audit, API/OpenAPI, UI,
  authority, threat, golden, and must-not-change contracts.
- P1 added strict immutable mirrored Core/Agent models and pure validation.
- P2 added an explicitly constructed, default-off, append-only Agent admission
  service/store with permanent atomic reservations and owned readback.
- P3 added the sole production-registered Agent POST behind explicit settings,
  HTTPS enforcement, injected authentication, strict bounds, and exact
  internal OpenAPI; registration remains off by default.
- P4 keeps Mission Control absent and adds structural locks proving no v0.32
  client, type, hook, component, page, route, navigation, mutation, retry/
  resend/send-again, effect control, sensitive rendering, or Home Assistant
  exception. It adds no Core bridge or runtime behavior.
- P5 completed isolation/regression/authority validation: exact default-off
  single-route registration, permanent concurrent no-replay, append-only and
  secret-free evidence, zero effect consumers, Core one-shot/no-retry
  preservation, absent Mission Control, capability parity, and Home Assistant
  blocking. It adds tests and release documentation only.

V0.32 authority ends at durable receipt/admission evidence. It enables a later
release to consider a fresh linked admission as one prerequisite for a new,
separately confirmed execution-admission decision. It does not create an
execution token. Installation, runtime/container/process execution, dispatch,
workers, workflows, queues, retry/resend, provider/repository/in-guest
mutation, deployment, rollback, public Core or Mission Control surfaces,
credential management, and Home Assistant artifacts remain blocked.

P0 through P5 are complete. Closure passed both Ruff gates, all 3072 Core
tests, all 1045 Agent tests, and all 550 Mission Control tests plus lint/build.

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

Atlas v0.16 is **Grounded Installation Planning**. It creates
deterministic, immutable, provenance-linked, ephemeral `InstallationPlan` read
models answering: “What would be required to install this application here?”
The dependency order is P0 → P1 → P2 → P3 → P4 → P5. P0 through P5 are
complete, and v0.16.0 is ready for the separate explicit release commit and
tag procedure.

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

### P1 — Deterministic Home Assistant Installation-Plan assembler — complete

The pure, local, deterministic assembler consumes reviewed read-side inputs
only. The current Home Assistant `DeploymentBinding` refers exactly to
`compose/home-assistant.yaml`, which is absent. Therefore its current plan must
fail closed as `missing_deployment_artifact`. Do not fabricate the artifact,
substitute another Compose file, infer a mutable image, or treat image
grounding as deployment readiness. The accepted Home Assistant golden
fingerprint is
`34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a`.

### P2 — Readiness, blocker, and risk evaluation — complete

The evaluator implements the P0-frozen status/blocker vocabulary, risks,
missing facts, assumptions, prerequisite relationships, freshness, conflicts,
compatibility, and required confirmations deterministically. Hostile contract coverage and
multi-evidence risk deduplication are accepted. Evaluation remains descriptive;
it creates no approval or execution eligibility. Historical P1/P2 acceptance
covered 254 InstallationPlan tests plus 90 required discovery/parity
regressions (344 combined).

### P3 — GET-only API and Mission Control review — complete

Implemented a bounded, redacted GET projection for server-assembled plans,
with no POST/PUT/PATCH/DELETE sibling and no caller-supplied deployment document. It
must not persist a plan or reach the legacy analysis route, Agent, candidates,
approvals, providers, dispatch, repository execution, or workers.

Mission Control presents the complete plan as read-only review information with
no action or conversion controls.

### P4 — Fail-closed execution-candidate admission projection — complete

The pure projection preserves the complete InstallationPlan and exact
fingerprint linkage while refusing candidate creation. InstallationPlan v1 has
no approved target identity, the existing `ExecutionCandidate` contract
requires one, and Atlas Agent does not support installation planning or
execution. Every status therefore remains non-authoritative; blocked statuses
also retain an explicit plan-blocked reason. The projection has no route,
control, persistence, idempotency key, workflow, approval, queue, dispatch, or
side effect. Repeated projection is deterministic recomputation.

P4 closure validation passed Ruff; 16 projection tests; 343 InstallationPlan
tests; 90 discovery/parity regressions; 78 execution-candidate
model/projection/eligibility tests; 31 execution-candidate service tests; 60
Core route/operator-intent tests; and 434 Atlas Agent
candidate-planning/approval/workflow tests.

### P5 — Authority isolation, release validation, and closure — complete

Completed the P0–P4 integration matrix, exact authority/capability parity,
GET-only behavior, absence of persistence and side effects, and the exact Home
Assistant fail-closed golden. Focused Core, full Agent, and Mission Control
test/lint/build gates pass. The broader Core suite was also exercised through
the practical managed-sandbox boundary; ownership-transition and restricted
thread behavior remain environment limitations, not v0.16 authority or
production defects.

V0.16.0 is ready for a separate explicit release commit and annotated
`atlas-v0.16.0` tag. This milestone performs no automatic commit, push, tag, or
publication. The next future release must separately contract approved target
identity and a supported installation intent before candidate creation or
installation execution can be considered.

## 6. Selected v0.17 plan — Prospective Installation Destination Assessment

Atlas v0.17 ends after an authenticated operator can select one exact,
currently observed Proxmox QEMU guest incarnation as a bounded prospective
installation destination and request an ephemeral, deterministic,
non-authorizing assessment. The normative, decision-complete
[v1 architecture](docs/architecture/prospective-installation-destination-v1.md)
freezes identity, lifecycle, fingerprint, API/UI, isolation, and test
contracts. P0 through P5 are complete on the v0.17 release-candidate branch.
The implementation adds only prospective selection, ephemeral assessment, and
review surfaces; it adds no installation or execution capability.

### P0 — Prospective Destination and Non-Authority Contract — complete

Scope: freeze the exact existing-guest identity, operator-scoped durable
selection, ephemeral interest, deterministic assessment, lifecycle, API/UI,
fingerprint, and dependency boundaries. Acceptance: every required decision is
normative, the Home Assistant golden remains blocked, and all enduring
capability/authority contracts are explicitly preserved. Non-goals: every
runtime, route, store, UI, test, migration, candidate, Agent, workflow,
provider, worker, execution, commit, tag, and push change. Authority: the only
new statement is that Atlas may remember one exact prospective selection.
Later tests: documentation-to-schema traceability and structural no-authority
checks.

### P1 — Immutable Destination Selection — complete

Scope: implemented authenticated enumeration, exact re-resolution, opaque
identity, durable operator-scoped selection, expiry, cancellation, tombstones,
and concurrency. Acceptance: exact current fingerprint and state gates,
24-hour expiry, no rebinding/reactivation, and restore/downgrade invariants.
Non-goals: guest inspection, capability claims, interests, assessments, plans,
or execution. Authority: selection records only prospective operator choice.
Tests: state/identity/movement, bounds, expiry, cancellation, reselection,
idempotency, concurrency, principal isolation, persistence, and restore.

### P2 — Ephemeral Installation Interest and Blocked Assessment — complete

Scope: implemented one-request ephemeral interest and the pure assessment
read model with fixed Agent unsupported fact. Acceptance: exact linkage,
canonical ordered reasons/fingerprints, status precedence, no candidate
evaluation, and Home Assistant remains blocked. Non-goals: durable intent,
queue, consumer, candidate creation, compatibility probing, or mutation.
Authority: neither object grants any. Tests: replay/conflict, expiry/staleness,
all reason combinations, deterministic fingerprints, golden case, and absence
of consumers/side effects.

### P3 — Guarded Core API — complete

Scope: exposed only the frozen authenticated bounded routes. Acceptance:
CSRF/trusted-origin enforcement, server-enumerated targets, closed 8 KiB
bodies, precise method/idempotency behavior, sanitized errors, and exact
re-resolution. Non-goals: caller URLs/addresses/provider payloads/raw identity
or any candidate/planning/workflow/approval/action/dispatch route. Authority:
transport exposes only selection and assessment semantics. Tests: auth, CSRF,
origin, OpenAPI, bounds, methods, enumeration, redaction, isolation, and error
mapping.

### P4 — Mission Control Prospective Destination UI — complete

Scope: presents “Select as prospective installation destination”, explicit
non-approval/non-installability copy, lifecycle, and ordered assessment
blockers. Acceptance: sanitized models only and accessible fail-closed
rendering. Non-goals: Install, Execute, Plan, Approve, Convert, Dispatch, or
authority-suggesting workflow navigation. Authority: presentation creates no
new authority. Tests: labels/copy, blocker order/states, accessibility,
redaction, and absence of prohibited controls/network calls.

### P5 — Isolation, Golden Cases, and Release Closure — complete

Scope: closes structural, behavioral, lifecycle, golden, documentation,
and release evidence. Acceptance: exact unchanged repository/operational/
Provider Intent/Discovery/approval/worker/backup/no-replay contracts and all
focused suites pass. Non-goals: expanding capability or publishing a release
without a separate operator procedure. Authority: no v0.17 record is consumed
by execution and no v0.18 grandfathering. Tests: full isolation/parity,
Home Assistant golden, persistence/restore/downgrade, UI/API, Agent/candidate/
workflow regressions, and no side effects.

The first subject v0.18 may consider is a separately frozen authoritative
in-guest capability and identity contract for transport, runtime, privileges,
target-scoped compatibility, and independent Agent support before durable
installation intent or candidate creation.

## 7. Selected v0.18 plan — Installation Capability Assessment

Atlas v0.18 is **Installation Capability Assessment**. It combines the
complete v0.16 `InstallationPlan`, the exact current v0.17 prospective
destination selection, and bounded sanitized provider capability facts into
one ephemeral deterministic read model. The normative planning boundary is
[Installation Capability Assessment v1](docs/architecture/installation-capability-assessment-v1.md).

This release remains read-only and non-authorizing. Even the strongest outcome
is `requirements_satisfied_but_non_authorizing`; it creates no candidate,
approval, workflow, action request, dispatch, Agent execution, worker
invocation, provider or repository mutation, installation, or deployment.
The dependency order is P0 → P1 → P2 → P3 → P4 → P5. P0 through P5 are
complete; the release remains read-only and non-authorizing.

### P0 — Capability fact and non-authority contract — complete

Scope: freeze the closed provider-fact schema and provenance, exact allowed
Proxmox/QEMU control-plane fact vocabulary, freshness/conflict/unknown rules,
requirement-comparison table, assessment statuses and fingerprint, API/UI
shape, dependency isolation, threat model, and golden cases. Acceptance: no
runtime ambiguity remains; configured guest-agent state is explicitly not
reachability; every positive comparison is evidence-bound; the strongest
status remains non-authorizing. Non-goals: every runtime, route, UI, test,
store, migration, provider call, Agent, candidate, workflow, worker, execution,
commit, tag, and push change. Authority: none. Expected later tests:
documentation/schema traceability, exhaustive tables, and forbidden-authority
structure.

Inspection constraint: the released destination projection does not currently
publish configured CPU, configured disk capacity, or the QEMU guest-agent
configuration bit. P0 treats them as prospective P1 facts, never as already
available evidence. Utilization is not capacity, and no guest-agent or
in-guest read is permitted.

### P1 — Pure provider capability fact adapter — complete

Scope: add a bounded, local, read-only adapter over existing permitted Proxmox
QEMU control-plane reads, bound to exact current destination identity.
Acceptance: typed sanitized facts preserve source, observation time, identity,
absence, malformed, unavailable, stale, and conflict distinctions; no raw
payload enters the model. Non-goals: guest-agent calls, SSH, probing, scanning,
credentials, in-guest/runtime/filesystem inspection, persistence, caching that
becomes evidence, or mutation. Authority: facts are observations only. Tests:
complete adapter table, bounds/redaction, identity/freshness, determinism,
failure isolation, zero mutation, and forbidden imports/calls.

### P2 — Deterministic capability comparison and assessment — complete

Scope: purely combine the exact InstallationPlan, active/current selection,
current identity, and provider facts; map only explicit comparable plan
requirements to `satisfied`, `not_satisfied`, `unknown`, or `not_assessable`.
Acceptance: total precedence, canonical reasons and fingerprint, unchanged plan
blockers/provenance, fixed false authority invariants, and Home Assistant
remains blocked. Non-goals: plan repair, target-scoped compatibility invention,
installability/readiness claims, durable intent, candidate eligibility, queue,
or consumer. Authority: none. Tests: every status/reason combination,
fingerprint stability/sensitivity, stale/moved/conflicting inputs, hostile
facts, golden cases, and no side effects.

V1 comparable requirements are limited to CPU cores, memory, and storage
minimums against exact like-unit configured-capacity facts. GPU, architecture,
OS, runtime, device, port, network, relationship, capability-ID, and all
in-guest requirements remain `not_assessable`; configured guest-agent state
does not satisfy any of them.

### P3 — Authenticated GET-only Core projection — complete

Scope: expose one bounded redacted server-assembled capability assessment after
freezing its final route and closed wire schema. Acceptance: authenticated
GET-only/OpenAPI behavior, server-owned inputs and evaluation time, exact
selection ownership/current-identity checks, sanitized errors, and no mutation
sibling. Non-goals: caller facts, plan bodies, target selectors, provider
payloads, addresses, credentials, commands, POST assessment, candidate,
approval, workflow, dispatch, or Agent routes. Authority: transport grants
none. Tests: auth, methods/OpenAPI, bounds, ownership, redaction, error mapping,
dependency isolation, and zero provider mutation.

### P4 — Mission Control read-only capability review — complete

Scope: present plan/destination linkage, sanitized provider facts,
comparisons, unknowns, contradictions, freshness, and explicit non-authorizing
status. Acceptance: accessible fail-closed rendering and language that
distinguishes configuration from observed capability and capability facts from
permission. Non-goals: Install, Prepare, Approve, Execute, Convert, Create
candidate, Start workflow, Dispatch, Retry action, or authority-suggesting
navigation/network calls. Authority: presentation adds none. Tests: all states,
ordering, provenance/freshness, missing/error behavior, accessibility,
redaction, and absence of prohibited controls and requests.

### P5 — Isolation, regression, and release closure — complete

Scope: close the structural, behavioral, API/UI, golden, security, and release
evidence matrix. Acceptance: v0.16 and v0.17 contracts remain exact; capability
parity, Agent unsupported facts, approvals, no-replay, worker default, backup,
and Discovery boundaries are unchanged; full focused and regression gates
pass. Non-goals: adding capability or automatically committing, tagging,
pushing, publishing, migrating, or deploying. Authority: no v0.18 record is
consumed by an execution subsystem. Tests: full isolation/parity, Home
Assistant golden, provider-read-only proofs, candidate/Agent/workflow/dispatch
regressions, UI/API gates, and absence of persistence and side effects.

P5 locks the exact single-GET v0.18 OpenAPI surface, Mission Control's absence
of mutation controls/calls, and the absence of any v0.18 record consumer in
candidate, approval, workflow, dispatch, Agent, worker, provider, repository,
or in-guest execution paths. Home Assistant remains blocked by the missing
deployment artifact and unsupported `install-container` Agent intent.

### Must-not-change contracts for P0-P5

- `InstallationPlan v1` stays target-free, immutable, ephemeral,
  non-authorizing, and unchanged; provider facts never repair plan blockers.
- V0.17 selection, interest, and admission assessment stay unchanged and do
  not become an approved target, durable installation intent, or authority.
- Candidate creation and eligibility remain false; `install-container`
  remains unsupported by Atlas Agent.
- Repository execution remains `update-compose-stack`; operational capability
  remains `restart-service/proxmox/qemu`; Provider Intent remains Proxmox QEMU
  `monitoring-policy`; Discovery remains GET-only/non-authoritative.
- No approval, workflow, action request, dispatch, Agent execution, worker
  invocation, provider/repository mutation, install, update, restart, deploy,
  rollback, remediation, or interrupted-side-effect replay is added.
- Existing independent approvals, optional default-disabled worker, and
  operator-maintenance-only backup/restore remain unchanged.

## 8. Selected v0.19 plan — Installation Candidate Admission

Atlas v0.19 is **Installation Candidate Admission**. It defines the narrowest
non-executing boundary that may combine one exact v0.16 `InstallationPlan`, one
exact active/current v0.17 prospective destination selection, and one exact
v0.18 capability assessment into a bounded, ephemeral, immutable
`InstallationCandidateRecordV1`. The normative planning boundary is
[Installation Candidate Admission v1](docs/architecture/installation-candidate-admission-v1.md).

This is admission to a read model, not admission to execution. No durable
candidate is created, no existing `ExecutionCandidate` is created or changed,
and no subsystem may consume the record. The only positive status is
`admitted_but_non_executable`; every incomplete, stale, mismatched, blocked,
unknown, or weaker input returns `not_admitted` with `candidate_record=null`.
The dependency order is P0 → P1 → P2 → P3 → P4 → P5. P0 through
P5 are complete; the resulting surface remains read-only and non-authorizing.

### P0 — Admission contract and threat model — complete

Freeze the exact closed input linkage, status/reason precedence, candidate
record schema, fingerprint, freshness/identity rules, GET-only API and
read-only presentation shape, dependency isolation, threats, and golden cases.
Acceptance requires a decision-complete contract with no runtime, route, UI,
test, store, migration, candidate, Agent, worker, provider, repository,
in-guest, execution, commit, tag, push, or release behavior. Authority: none.

### P1 — Pure fail-closed admission evaluator — complete

Implement a local deterministic function over complete server-owned v0.16,
v0.17, and v0.18 records. It may emit a record only for exact item, catalog,
plan fingerprint, selection ID/fingerprint/current identity, and capability
assessment linkage when the plan is `plan_ready_for_review`, the selection is
active/current, and the assessment is
`requirements_satisfied_but_non_authorizing`. It persists nothing and invokes
nothing. Tests cover every reason, precedence, mismatch, freshness boundary,
fingerprint, hostile input, determinism, and zero side effects.

### P2 — Bounded candidate record projection — complete

Freeze and implement the minimal sanitized `InstallationCandidateRecordV1`:
schema/version, exact source fingerprints and destination identity
fingerprints, evaluation time, fixed non-authority invariants, and its own
domain-separated fingerprint. It contains no command, executable payload,
artifact body, credential, address, provider payload, approval, intent,
workflow/action/dispatch identifier, retry/replay token, or mutation recipe.
It is ephemeral and has no create/update/delete lifecycle or consumer.

### P3 — Authenticated GET-only Core projection — complete

Expose one bounded server-assembled GET projection only after its path and wire
schema are frozen. It accepts identifiers only, never caller facts or record
bodies; mutation siblings are absent and rejected. Authentication, ownership,
current re-resolution, bounds, redaction, OpenAPI, dependency isolation, and
zero-mutation tests are required. Transport adds no approval or authority.

### P4 — Mission Control read-only admission review — complete

Present exact source linkage, reasons, the nullable record, expiry/freshness,
and conspicuous non-executable semantics. There is no Admit, Create, Approve,
Install, Prepare, Execute, Convert, Start workflow, Dispatch, Deploy, Retry,
Rollback, or equivalent control or authority-suggesting navigation. Tests
cover every state, accessibility, redaction, error handling, and absence of
prohibited controls and requests.

### P5 — Isolation, regression, and release closure — complete

Prove no admission assessment or candidate record is persisted or consumed by
existing candidate, approval, workflow, dispatch, Agent, worker, provider,
repository, in-guest, deployment, rollback, tag, push, or release paths.
Reconfirm v0.16-v0.18 golden cases, capability parity, independent approvals,
no-replay, default-disabled worker, backup/restore, OpenAPI, UI, full regression,
and exact-source validation. P5 validates the boundary and grants no authority.

### Must-not-change contracts for P0-P5

- V0.16 `InstallationPlan v1` remains target-free, immutable, ephemeral, and
  non-authorizing; its schema, fingerprint, precedence, blockers, Home
  Assistant golden, and existing fail-closed candidate projection do not
  change.
- V0.17 selection, interest, and admission-assessment schemas, identity,
  ownership, lifecycle, expiry, storage, fingerprints, routes, and
  non-authority semantics do not change. A selection is not an approved target.
- V0.18 provider facts and capability assessment remain ephemeral read-side
  observations. Their schemas, comparison semantics, routes, strongest
  non-authorizing status, fixed-false authority fields, and lack of consumers
  do not change.
- `InstallationCandidateRecordV1` is not an existing `ExecutionCandidate`,
  approved target, installation intent, proposal, workflow, approval, action
  request, dispatch, deployment specification, executable plan, or permission.
  `admitted_but_non_executable` implies none of those things.
- No automatic admission or approval occurs. A read request may evaluate the
  closed boundary; it cannot accept confirmation, persist a decision, or
  trigger another request.
- Atlas Agent keeps repository support exactly `update-compose-stack` and
  operational handling exactly `restart-service`; `install-container` remains
  unsupported. Production operational capability remains exactly
  `restart-service/proxmox/qemu`, Provider Intent remains identity-bound
  Proxmox QEMU `monitoring-policy`, and Discovery remains GET-only and
  non-authoritative.
- No candidate execution, Agent install-container execution, worker invocation,
  provider mutation, repository mutation, in-guest read or mutation, automatic
  approval, workflow, action request, dispatch, installation, deployment,
  rollback, remediation, replay, migration, background probe, commit, tag,
  push, publication, or release is added.
- Existing independent approvals, interrupted-side-effect no-replay behavior,
  optional default-disabled worker, and operator-maintenance-only
  backup/restore remain unchanged.

## 9. Selected v0.20 plan — Installation Candidate Record Lifecycle

Atlas v0.20 is **Installation Candidate Record Lifecycle**. It adds the
narrowest durable, non-executable preservation boundary for one exact v0.19
`admitted_but_non_executable` result. The normative planning boundary is
[Installation Candidate Record Lifecycle
v1](docs/architecture/installation-candidate-record-lifecycle-v1.md).

Preservation is an explicit operator request, not approval or admission. It
stores the exact closed v0.19 candidate record and admission fingerprint under
an operator-scoped opaque identity. The stored snapshot is immutable and has
only `active` and `expired` derived lifecycle states. It cannot outlive the
v0.19 record's existing `valid_until`; expiration is passive and triggers no
work. Deletion removes only this advisory record. No state transition can make
the record approved, executable, deployable, dispatchable, or Agent-supported.

The dependency order is P0 → P1 → P2 → P3 → P4 → P5. P0 through P5 are
complete, and v0.20 is ready for the separate explicit release procedure.

### P0 — Lifecycle contract and threat model — complete

Freeze the closed durable envelope, exact v0.19 snapshot linkage, ownership,
state derivation, expiry boundary, idempotency, quotas, retention/deletion,
routes, presentation, storage isolation, failure behavior, threats, and golden
cases. Acceptance is a decision-complete planning contract and documentation
diff only: no runtime, route, UI, test, schema migration, database, worker,
Agent, provider, repository, in-guest, execution, commit, tag, or release
behavior.

### P1 — Closed preservation contract and pure lifecycle derivation — complete

Define an immutable operator-owned envelope around the exact complete closed
v0.19 candidate record and its exact admission fingerprint. Pure validation
accepts only a complete positive v0.19 result whose record is still valid at a
server-owned whole-second UTC time. Pure state derivation returns `active`
before `valid_until` and `expired` at or after it. It performs no I/O, refresh,
re-admission, repair, approval, or eligibility evaluation.

### P2 — Bounded durable store — complete

Persist the immutable envelope in one independent store with authenticated
operator ownership, conflict-safe idempotency, closed record-size and count
limits, atomic create/read/delete behavior, and fail-closed corruption
handling. The store must not persist upstream provider payloads, plans,
selections, capability facts, credentials, artifacts, commands, or executable
material. No background expiry, queue, event, audit-to-execution bridge, or
consumer is added; state is derived on read.

### P3 — Authenticated lifecycle API — complete

Add only an explicit preserve operation, bounded list/item reads, and deletion
under a separately frozen installation-candidate-record namespace. Preserve
re-evaluates current server-owned v0.19 inputs and stores only the exact still-
valid positive result; callers cannot submit a candidate body or authority
fields. Cross-operator lookup remains indistinguishable, mutation defenses and
idempotency are mandatory, and no approve/execute/convert endpoint exists.

### P4 — Mission Control record review — complete

Present saved linkage, fingerprint, creation time, fixed expiry, and explicit
active/expired non-executable state. The only mutation control is deletion of
the advisory saved record. There is no Approve, Install, Prepare, Execute,
Convert, Dispatch, Deploy, Retry, Reactivate, Extend, Refresh, or equivalent
control, navigation, or request.

### P5 — Isolation, regression, and release closure — complete

Prove exact v0.19 snapshot preservation, ownership, bounds, expiry, corruption
handling, restart durability, API/UI behavior, and absence of production
consumers. Reconfirm v0.16–v0.19 goldens, capability parity, approval
separation, no-replay, worker default, backup isolation, and full regression
gates. P5 grants no execution authority and does not automatically migrate,
commit, tag, push, publish, deploy, or release.

Release validation locks the durable envelope out of every Core and Agent
authority or mutation consumer, freezes the lifecycle-only OpenAPI surface,
and limits Mission Control to preserve, review, and delete. Home Assistant
remains `not_admitted` and cannot cross the preservation boundary. Backup v3
is intentionally unchanged: the independent advisory database is excluded
and must be handled through explicit operator maintenance.

### Must-not-change contracts for P0–P5

- V0.16–v0.18 schemas, fingerprints, routes, ownership, freshness, lifecycle,
  golden cases, and non-authority semantics remain exact.
- V0.19 admission remains ephemeral recomputation. Its schema, reason
  precedence, fingerprints, route, `valid_until`, fixed-false fields, and lack
  of consumers do not change. V0.20 stores only its exact positive output and
  does not create a second admission rule.
- A saved record is not an existing `ExecutionCandidate`, approved target,
  installation intent, proposal, approval, workflow, action request, dispatch,
  deployment specification, executable plan, or permission. `active` means
  only that the captured v0.19 validity deadline has not passed.
- Atlas Agent support stays exactly `update-compose-stack` for repository work
  and `restart-service` for operational handling; `install-container` remains
  unsupported. Production operational capability stays exactly
  `restart-service/proxmox/qemu`; Provider Intent stays identity-bound Proxmox
  QEMU `monitoring-policy`; Discovery stays GET-only/non-authoritative.
- No approval, execution, dispatch, Agent install-container support, worker
  invocation, provider mutation, repository mutation, in-guest read or
  mutation, installation, deployment, rollback, remediation, replay,
  background refresh, or automatic preservation is introduced.
- Existing ExecutionCandidate behavior, independent approval stages,
  interrupted-side-effect no-replay behavior, optional default-disabled
  worker, and operator-maintenance-only backup/restore remain unchanged.

## 10. Selected v0.21 plan — Installation Approval Intent

Atlas v0.21 is **Installation Approval Intent**. It defines the narrowest
durable evidence boundary through which an authenticated operator may record
one explicit approval statement for one exact, owned, active v0.20 durable
non-executable candidate identity. The normative planning boundary is
[Installation Approval Intent
v1](docs/architecture/installation-approval-intent-v1.md).

The approved identity is the closed tuple of v0.20 candidate-record ID,
envelope fingerprint, admission fingerprint, and embedded candidate-record
fingerprint. The intent also binds the authenticated operator, server-owned
recording time, and one fixed statement. It is immutable and append-only; it
has no approval state machine, revocation semantics, execution authorization,
consumer, or conversion path. Candidate expiry or deletion creates no work and
does not turn the historical statement into permission.

The dependency order is P0 → P1 → P2 → P3 → P4 → P5. P0 through P5 are
complete on the v0.21 release-candidate branch. The resulting surface records
operator-scoped evidence only and adds no execution authority or consumer.

### P0 — Approval-intent contract and threat model — complete

Freeze the exact approved-subject tuple, fixed statement, authenticated actor,
immutability, uniqueness, idempotency, bounds, isolated persistence, API/UI
shape, failure behavior, threats, backup posture, goldens, and P1–P5 gates.
Acceptance is this decision-complete documentation diff only; it adds no
runtime, route, UI, test, store, migration, Agent, worker, provider,
repository, guest, execution, workflow, commit, tag, push, or release behavior.

### P1 — Closed intent contract and pure validation — complete

Implement the closed model, domain-separated fingerprint, exact actor and
subject binding, and pure validation over a complete active v0.20 envelope at
server-owned time. It performs no I/O and grants no authority.

### P2 — Bounded append-only store — complete

Implement one independent operator-scoped store with atomic unique creation,
conflict-safe idempotency, closed count/size bounds, restart durability,
reads, and fail-closed corruption behavior. Add no runtime delete/update,
background task, event, queue, audit bridge, worker job, or consumer.

### P3 — Authenticated intent API — complete

Implement only create, bounded list, and item read routes under the new
candidate-approval-intent namespace. Creation accepts a candidate-record ID,
re-resolves ownership and active state server-side, and accepts no caller proof
or authority field. Freeze hardened mutation defenses, redaction, OpenAPI,
unsupported methods, and dependency isolation.

### P4 — Mission Control explicit statement and review — complete

Implement deliberate exact-record confirmation and immutable evidence review
with conspicuous language that recording approval neither starts nor permits
installation. Add no execute, install, dispatch, deploy, workflow, convert,
attach, retry, revoke, or rollback control, navigation, or request.

### P5 — Isolation, regression, and release closure — complete

Prove exact v0.20 linkage, authenticated actor proof, uniqueness, concurrency,
restart durability, quotas, corruption handling, API/UI contracts, and absence
of production consumers. Reconfirm v0.16–v0.20 goldens, capability parity,
approval separation, no-replay, worker default, backup isolation, and full
regression gates. Do not automatically migrate, commit, tag, push, publish,
deploy, or release.

P5 structurally locks the append-only store and operator-scoped service, zero
Core/Agent production consumers, the exact create/list/item-read OpenAPI
surface, and Mission Control's matching three calls with no authority control
or navigation. Home Assistant remains `not_admitted`, cannot be preserved, and
therefore cannot be approved or executed. Focused Core, full Agent, and Mission
Control test/lint/build gates pass; backup v3 remains intentionally unchanged.

### Must-not-change contracts for P0–P5

- V0.16–v0.19 contracts remain exact and non-authorizing.
- V0.20 remains an immutable, operator-scoped, durable non-executable record
  with passive active/expired derivation, unchanged deletion, five false
  authority fields, no consumers, and unchanged backup exclusion. V0.21 adds
  no field or state to the v0.20 envelope and never blocks its deletion.
- An approval intent is evidence of one operator statement, not an existing
  ExecutionCandidate, approved target, execution approval, installation
  intent, permission, workflow, action request, dispatch, deployment
  specification, executable plan, audit approval, or replay token.
- Existing ExecutionCandidate, approval, audit, workflow, dispatch, execution,
  independent approvals, and interrupted-side-effect no-replay behavior remain
  unchanged and never consume v0.21 data.
- Atlas Agent support stays exactly `update-compose-stack` for repository work
  and `restart-service` for operational handling; `install-container` remains
  unsupported. Operational capability remains
  `restart-service/proxmox/qemu`, Provider Intent remains Proxmox QEMU
  `monitoring-policy`, and Discovery remains GET-only/non-authoritative.
- No execution, dispatch, Agent or worker invocation, provider or repository
  mutation, guest read/mutation, install, deploy, rollback, remediation,
  replay, workflow start, background work, or authority-bearing event is added.
- The optional worker remains default-disabled and backup/restore remains
  explicit operator maintenance.

## 11. Selected v0.22 plan — Agent Install-Container Contract

Atlas v0.22 is **Agent Install-Container Contract**. It freezes the narrowest
Agent-side validation contract that a separately designed future Core
execution request could target, while adding no Core route, dispatch, worker,
installation, provider/repository/guest mutation, or runtime behavior. The
normative boundary is [Agent Install-Container Contract
v1](docs/architecture/agent-install-container-contract-v1.md).

The contract accepts only one exact same-owner v0.20 candidate envelope and
v0.21 approval-intent proof chain, one unchanged existing Proxmox QEMU guest
incarnation, and one digest-pinned normalized single OCI container. Its future
runtime policy is rootless Podman, network `none`, no host mounts, devices,
secrets, environment, command override, privilege, added capabilities,
writable root filesystem, port publication, or restart policy. Validation can
produce only `valid_but_unsupported` or `rejected`; all authority fields remain
false and validation evidence has no production consumer.

The dependency order is P0 → P1 → P2 → P3 → P4 → P5. P0–P5 are complete.
Every phase remains non-executing.

### P0 — Contract and threat-model freeze — complete

Freeze the exact request/result schemas, allowed subject, mandatory candidate
and approval fingerprints, artifact/runtime/filesystem/network bounds,
validation behavior, reason precedence, idempotency, no-replay, redaction,
audit evidence, default-disabled posture, risks, goldens, and refusal
boundaries. Change planning documentation only.

### P1 — Closed models and fingerprints — complete

Implement isolated pure Agent models, canonicalization, and domain-separated
fingerprints. Register no route, intent, adapter, service, worker, or consumer.

### P2 — Pure linkage and policy validation — complete

Validate injected closed proof fixtures, destination/artifact lineage,
freshness, and fixed runtime/filesystem/network policy with deterministic,
redacted failures and no I/O.

### P3 — Internal dry-run evidence boundary — complete

Compose a dependency-injected validation-only service returning closed audit
evidence. Add no HTTP intake, Core client call, persistence, audit bridge,
queue, dispatch, or mutation.

### P4 — Unsupported operator diagnostics — complete

Present bounded Agent capability/diagnostic evidence while keeping
`install-container` conspicuously unsupported and default-disabled. Add no
enable switch, install control, Mission Control workflow, or runtime call.
The existing Agent information route exposes only a closed static capability
diagnostic; Mission Control presents that local state and an explicit no-result
empty state because no validation-result route or Core bridge exists.

### P5 — Isolation, refusal, and regression closure — complete

Proved zero Core route/caller/dispatch, zero supported Agent intent, zero
worker/provider/repository/guest/runtime invocation, zero authority consumer,
exact no-replay/redaction behavior, Home Assistant rejection, and full
regression gates. Structural Mission Control locks also prove the diagnostic
has no install/execute/deploy/dispatch/send-to-Agent/start-workflow control,
navigation, or mutation call. P5 added tests and release evidence only; it did
not tag, push, publish, deploy, or release.

### Must-not-change contracts for P0–P5

- V0.16–v0.21 contracts remain exact; their identities and evidence do not
  become execution authority and their production packages gain no v0.22
  consumer.
- Existing ExecutionCandidate, approval, audit, workflow, dispatch, execution,
  repository candidate, operational handling, and interrupted-side-effect
  no-replay contracts remain unchanged.
- Agent support remains exactly `update-compose-stack` for repository work and
  `restart-service` for operational handling. `install-container` remains
  unsupported and absent from planning, conversion, dispatch, and execution.
- Operational capability remains `restart-service/proxmox/qemu`; Provider
  Intent remains Proxmox QEMU `monitoring-policy`; Discovery remains GET-only
  and non-authoritative.
- No Core execution request route, Core-to-Agent dispatch, worker invocation,
  install, provider mutation, repository read/mutation, guest read/mutation,
  runtime probe, image acquisition, container creation, network use,
  deployment, rollback, replay, workflow, background work, or authority event
  is added.
- The optional worker remains default-disabled and backup/restore remains
  explicit operator maintenance.

### Exact risks and what v0.22 enables

The closed threat model covers approval substitution, cross-operator or stale
proofs, destination replacement/confused deputy behavior, artifact
equivocation, container escape, filesystem traversal/persistence, network
exfiltration/lateral movement, resource exhaustion, replay after ambiguity,
validation being mistaken for authority, secret/error leakage, and accidental
feature activation.

V0.22 enables later design to reuse a frozen Agent parser, proof-linkage
validator, narrow runtime policy, redacted result, and audit-evidence shape. It
still refuses runtime intake and execution, general Compose, image pulls,
networked or persistent containers, Home Assistant deployment, and any request
without a separately frozen Core authority, dispatch, durable no-replay,
recovery, and rollback contract.

## 12. Selected v0.23 plan — Installation Execution Request Boundary

Atlas v0.23 is **Installation Execution Request Boundary**. It defines the
narrowest Core-side immutable request record that binds one same-owner active
v0.20 candidate envelope, its exact v0.21 approval intent, and one complete
fresh v0.22 Agent request/validation/evidence pair. The normative contract is
[Installation Execution Request v1](docs/architecture/installation-execution-request-v1.md).

The request is record-only and non-executing. Its lifecycle is derived as
`recorded` or terminal `expired`; all five authority fields are false. It is
not queued, dispatchable, executable, renewable, replayable, or convertible.
Core validates operator-submitted v0.22 evidence locally and never calls
Agent. The dependency order is P0 → P1 → P2 → P3 → P4 → P5. P0 through P5
are complete; P5 added validation and release evidence only.

### P0 — Core request contract and threat model — complete

Freeze the exact create/durable schemas, mandatory fingerprints, same-owner
linkage, freshness, lifecycle, atomic idempotency/no-replay reservation,
redaction/audit evidence, append-only store posture, default-disabled API/UI,
goldens, threats, and must-not-change contracts.

### P1 — Closed models and pure validation — complete

Implement isolated Core models, fingerprints, exact three-release linkage,
freshness/lifecycle derivation, and sanitized failures over injected values
only. Register no route, store, service, consumer, or Agent client.

### P2 — Bounded append-only request store — complete

Implement operator-scoped atomic append/read, multi-identity reservation,
idempotency, uniqueness, quotas, durability, and fail-closed corruption and
ambiguous-completion behavior. Add no update/delete, event, queue, audit
bridge, expiry task, worker job, migration, or consumer.

### P3 — Authenticated record-only Core API — complete

Implement create/list/item-read only. Resolve v0.20/v0.21 ownership locally,
validate the submitted v0.22 pair without Agent invocation, and lock bounds,
redaction, methods, OpenAPI, and dependency isolation.

### P4 — Mission Control evidence review — complete

Implement explicit non-executing confirmation and immutable review, including
operator-submitted evidence provenance and `recorded`/`expired` rendering.
Add no install, execute, dispatch, deploy, Agent, workflow, retry, cancel, or
rollback control or navigation.

### P5 — Isolation, no-replay, and release closure — complete

Prove ownership, linkage, freshness, reservations, concurrency/restart/timeout
ambiguity, quotas, corruption, API/UI boundaries, zero consumers, all prior
goldens and authority regressions, default-disabled posture, and full release
gates. Do not automatically migrate, tag, push, publish, deploy, or release.

P5 locks the default-disabled, record-only service and fixed-false authority
fields; scans all Core and Agent production modules for unauthorized v0.23
consumers; freezes the exact guarded create/list/get OpenAPI surface; confines
Mission Control calls to its dedicated create/list/get adapter; and excludes
prohibited controls and navigation. Home Assistant remains blocked with no
deployment artifact. The requested Core/Agent Ruff gates, 233 focused Core
tests, 948 Agent tests, 499 Mission Control tests, Mission Control lint/build,
and whitespace validation passed.

### Exact authority boundary and later enablement

V0.23 may append and read one operator-owned evidence record. That is its full
authority. It cannot dispatch, invoke Agent/worker/runtime/process execution,
mutate provider/repository/guest state, start a workflow, install, deploy, roll
back, or replay. It preserves existing capability sets and backup v3.

Later design may reference the durable, freshness-bounded, one-time linkage as
an input. Still blocked are a new independent execution approval, trusted
Agent evidence transport, execution-time identity checks, atomic consumption,
Core-to-Agent dispatch, worker/runtime behavior, interruption recovery,
side-effect audit, image acquisition, persistent/networked workloads,
deployment, rollback, and Home Assistant installation.

## 13. Selected v0.24 plan — Installation Dispatch Handoff

Atlas v0.24 is **Installation Dispatch Handoff**. Its normative
documentation-only P0 contract is [Installation Dispatch Handoff
v1](docs/architecture/installation-dispatch-handoff-v1.md).

Core may prepare one immutable, operator-owned, 60-second-maximum envelope
that binds the exact v0.20 candidate, v0.21 intent, v0.22 validation evidence,
and v0.23 execution request. It does not send the envelope. The only Agent
shape is a contract-only parser result, `valid_but_not_admitted`, with every
authority field false and no route or consumer.

The dependency order P0 → P1 → P2 → P3 → P4 → P5 is complete: the frozen
contract, isolated models and pure assembly, bounded append-only Core store,
preparation-only create/list/read API, Mission Control evidence review, and
isolation/no-replay release closure are implemented and validated.

The exact authority boundary is local owned-record resolution, pure validation,
and preparation of one evidence envelope. No live Core-to-Agent invocation,
Agent admission, delivery, worker/runtime/process execution, provider,
repository, or guest mutation, workflow, installation, deployment, rollback,
or replay is authorized.

V0.24 enables later work to reference a compact owner-bound handoff envelope
and frozen Agent intake vocabulary. Trusted transport, fresh execution
approval, live Agent intake, atomic consume/no-redelivery, execution-time
proof, worker/runtime behavior, recovery, side-effect audit, deployment,
rollback, and Home Assistant installation remain blocked.

P5 locks the release boundary structurally across Core, Agent, and Mission
Control. Handoff records have no live invocation, HTTP, delivery, worker,
workflow, provider/repository/guest mutation, candidate execution, deployment,
rollback, or replay-bypass consumer. The feature remains default-disabled and
record-only, and Home Assistant remains non-installable and non-executable.

## 14. Selected v0.25 plan — Agent Intake Simulation

Atlas v0.25 is **Agent Intake Simulation**. Its normative contract is
[Agent Intake Simulation v1](docs/architecture/agent-intake-simulation-v1.md).
P0 through P5 are complete.

P1–P2 provide closed immutable models and pure validation of explicitly
injected, owner-bound v0.24 envelopes. P3 provides the bounded append-only
simulation evidence store with atomic reservations, exact idempotency,
one-envelope no-replay semantics, restart durability, quotas, fail-closed
corruption handling, and owned in-process readback.

P3 also freezes the required no-surface boundary. There is no Agent HTTP,
OpenAPI, RPC, CLI, shell-command, application-container, settings, Core
consumer, delivery, worker, workflow, runtime, provider, repository, or guest
integration. The simulation package has no network or process dependency, and
filesystem mutation is confined to an explicitly constructed simulation
evidence store. Authentic delivery, live admission, consumption, execution,
installation, deployment, and rollback remain blocked.

### P4 — Mission Control presentation boundary — complete

The frozen contract exposes no UI-facing read model, so Mission Control adds
no v0.25 component, page, route, navigation, API client, hook, type, mutation,
or action control. Structural Mission Control and cross-service tests lock the
absence of install/intake/delivery controls, mutation calls, action navigation,
execution-suggesting labels, simulation evidence, and sensitive intake data.
Home Assistant remains blocked, non-installable, and non-executable with no
deployment artifact.

### P5 — Release validation and closure — complete

Release-wide structural and regression tests prove that v0.25 remains an
explicitly constructed, default-disabled, simulation-only in-process Agent
facility. No production Core or Agent module consumes its records; no live
delivery, HTTP/OpenAPI, command, container/settings registration, worker,
workflow, provider/repository/guest mutation, candidate execution, deployment,
rollback, or replay-bypass path exists. Owned readback remains a direct
in-process store operation. Mission Control has no v0.25 client, mutation,
route, navigation, control, execution label, or evidence surface.
`install-container` remains unsupported, and Home Assistant remains blocked
and non-executable with no deployment artifact. P5 adds no runtime behavior or
authority.

## 15. Selected v0.26 plan — Simulated Core-to-Agent Handoff Delivery

Atlas v0.26 is **Simulated Core-to-Agent Handoff Delivery**. Its normative P0
contract is [Simulated Handoff Delivery
v1](docs/architecture/simulated-handoff-delivery-v1.md). P0 through P5 are
complete.

The narrow boundary is an explicitly constructed in-process coordinator. Core
may preserve one immutable simulated-delivery attempt, pass the complete exact
v0.24 envelope to the unchanged v0.25 Agent simulation path, and preserve an
exact closed Agent acknowledgement copy. Agent may preserve only its existing
v0.25 intake evidence and one v0.26 acknowledgement. Every authority field is
false, and `agent_simulated_not_received` remains the provenance.

The delivery binds one same-owner v0.20 candidate, v0.21 approval intent, v0.22
validation evidence, v0.23 execution request, v0.24 dispatch envelope, and
v0.25 intake record through their exact IDs and domain-separated fingerprints.
It freezes `pending_acknowledgement`, `simulated_acknowledged`, and terminal
expired lifecycle states; upstream-bounded freshness; one-envelope/
one-delivery/one-intake/one-acknowledgement reservations; exact retry and
acknowledgement-copy reconciliation; redaction; and fail-closed ambiguity.

### P0 — Contract and threat-model freeze — complete

Freeze the exact simulated delivery, Core attempt record, and Agent
acknowledgement schemas; six-release linkage; ownership and identity rules;
freshness, lifecycle, idempotency/no-replay and recovery; evidence/redaction;
default-disabled no-surface posture; threats, goldens, authority boundary, and
must-not-change contracts. Change planning documentation only.

### P1 — Closed models and pure validation — complete

Implement isolated immutable values, strict parsing, canonical fingerprints,
lifecycle derivation, and hostile-input tests without I/O or registration.

### P2 — Core evidence and explicit coordinator — complete

Implement bounded append-only Core attempt/acknowledgement-copy stores and an
explicitly constructed coordinator with an injected Agent port, exact retries,
owned reads, quotas, restart durability, and fail-closed reconciliation.

### P3 — Agent acknowledgement adapter — complete

Map the exact delivery into the unchanged v0.25 in-process service, validate
the durable intake record, and append one closed acknowledgement. Add no
production route, command, listener, transport, container registration, event,
queue, execution adapter, or authority consumer.

### P4 — Offline golden harness — complete

Exercise only synthetic injected values and render bounded redacted test
evidence. Mission Control remains absent. Home Assistant remains a blocked
golden with no deployment artifact.

### P5 — Isolation, no-replay, and release closure — complete

Prove exact linkage, freshness/lifecycle, ownership, single-use identities,
recovery, concurrency/restart/ambiguity, corruption, quotas, redaction, zero
production surface, prior-contract goldens, capability parity, and regression
gates. Do not migrate, tag, push, publish, deploy, or release automatically.

Release-wide structural and regression tests prove that Core delivery and
Agent acknowledgement evidence remain explicitly constructed, in-process,
default-disabled, simulation-only, and fixed-false for every authority field.
No production consumer, HTTP/OpenAPI route, command, registration, setting,
network/transport client, worker, workflow, candidate execution, provider,
repository, guest, deployment, rollback, or replay-bypass path exists.
Mission Control remains absent for v0.26. `install-container` remains
unsupported, and Home Assistant remains blocked and non-executable with no
deployment artifact. P5 adds tests and release evidence only.

The exact authority is evidence-only simulation. Core cannot claim live send
or receipt, authenticate Agent, admit work, or authorize execution. Agent
cannot claim authentic Core origin, grant admission, consume authority, or
create work. Neither side may run Docker/Podman, execute a process, mutate a
provider/repository/guest, start workflow/worker execution, install, deploy, or
roll back.

V0.26 enables later design to reuse a deterministic simulated delivery and
acknowledgement state machine, six-release proof linkage, separate evidence on
both sides, and bounded ambiguous-copy reconciliation. Live authenticated
transport, receipt, atomic consumption/no-redelivery, fresh execution approval,
execution-time proof, runtime/worker authority, all target mutation, side-
effect recovery/audit, installation, deployment, rollback, and Home Assistant
installation remain blocked.

## 16. Selected v0.27 plan — Real Agent Intake Boundary

Atlas v0.27 is **Real Agent Intake Boundary**. Its normative P0 contract is
[Real Agent Intake Boundary
v1](docs/architecture/real-agent-intake-boundary-v1.md). P0 is selected and is
documentation only. P1–P5 are implemented and validated.

The narrow boundary accepts one authenticated Core request only when explicitly
constructed, validates the complete exact v0.20–v0.26 chain, and preserves one
operator-owned `admitted_for_evidence_only` record. Admission proves receipt
and evidence custody only. It is never execution admission, a job, a capability,
or permission to mutate a target.

### P0 — Contract and threat-model freeze — selected

Freeze the exact request, admission, result, fingerprint, seven-release
linkage, authentication/authorization, ownership, identity, freshness,
lifecycle, idempotency/no-replay, evidence/redaction, dormant API, authority,
golden, and must-not-change contracts. Change planning documentation only.

### P1 — Closed models and pure validation — implemented

Implement isolated immutable values, canonical fingerprints, lifecycle and
hostile-input validation with no I/O, registration, or side effects.

### P2 — Authenticated evidence-only admission — implemented

Implement an explicitly constructed service over an injected fixed Core
principal, operator assertion, trusted clock, local v0.25/v0.26 evidence
readers, and admission-store port. It validates and admits evidence only.

### P3 — Bounded intake evidence store — implemented

Implement the independent append-only Agent store with atomic reservations,
exact idempotency, one-envelope no-replay, quotas, restart durability, owned
reads, and fail-closed ambiguity/corruption. Add no authority consumer.

P3 adds no HTTP/OpenAPI route, route factory, command, production application
or container registration, setting, credential, Core consumer, or live
delivery listener. The explicitly constructed test-only dormant route factory
remains P4 work.

### P4 — Dormant route factory and offline goldens — implemented

Implement the bounded internal POST adapter only in an explicitly constructed
test application. Production Agent registration, settings, credentials,
deployment wiring, Core delivery, CLI, and UI remain absent. Home Assistant is
a blocked golden only.

### P5 — Isolation, no-replay, and release closure — complete

Prove exact linkage, authentication separation, freshness/lifecycle,
single-admission behavior, ownership, concurrency/restart/timeout ambiguity,
quotas, corruption, redaction, route bounds, zero production surface and Core
delivery, capability parity, prior goldens, and full regressions. Do not tag,
push, publish, deploy, or release automatically.

P5 locks concurrent single admission, fail-closed ambiguous reservations,
operator-owned direct readback, the exact dormant POST factory, and zero
production registration or Core delivery. Mission Control remains absent,
Home Assistant remains blocked with no deployment artifact, and P5 adds only
tests and release evidence.

The exact authority is authenticated receipt, validation, and bounded
preservation of evidence-only admission when the service is explicitly
constructed. Agent cannot execute installation, invoke Docker/Podman or a
process, access or mutate a provider/repository/guest, start workflow/worker
execution, deploy, or roll back. Core cannot deliver to the v0.27 surface, and
production Agent cannot register it, until a later release explicitly enables
both sides.

V0.27 enables later design to register the reviewed route, provision a
dedicated Core identity, deliver one owner-bound handoff, and use deterministic
receipt/freshness/no-redelivery evidence as input to a separate future
execution-admission contract. Production delivery, execution approval and
consumption, execution-time proof, all runtime and target effects, installation,
deployment, rollback, and Home Assistant installation remain blocked.

## 17. Selected v0.28 plan — Dormant Core-to-Agent Delivery Wiring

Atlas v0.28 is **Dormant Core-to-Agent Delivery Wiring**. Its normative P0
contract is [Dormant Core-to-Agent Delivery Wiring
v1](docs/architecture/dormant-core-agent-delivery-wiring-v1.md). P0 is selected
and documentation-only; P1–P5 are implemented and validated.

The boundary may later let explicitly constructed Core code assemble and
preserve one exact `not_sent` v0.27 intake request from the same-owner
v0.20–v0.26 chain and validate a directly injected v0.27 result. It has no
send-capable method, production registration, credential read, network call,
or Agent invocation.

### P0 — Dormant wiring and threat-model freeze — selected

Freeze the exact client/factory, disabled endpoint/authentication configuration,
request/preparation, injected-response validation, eight-release linkage,
ownership, freshness, lifecycle, idempotency/no-replay, redaction, no-surface,
authority, golden, and must-not-change contracts. Change planning docs only.

### P1 — Closed models and pure validation — implemented

Implement isolated immutable Core values, canonical fingerprints, exact
v0.20–v0.27 linkage, derived lifecycle, and hostile-input validation with no
I/O, registration, or effects.

### P2 — Dormant preparation service and bounded store — implemented

Implement an explicitly constructed service and append-only store that may
prepare and preserve one evidence-only `not_sent` request. Add no client
transport, Agent call, credential read, route, command, worker, or workflow.

### P3 — Explicit no-send client factory — implemented

Implement only `prepare`, owned readback, and pure supplied-response validation
over injected dependencies. Validate configuration shape without DNS, TLS,
HTTP, file reads, Authorization rendering, or any send/deliver method. Keep all
production construction absent.

### P4 — Offline structural goldens — implemented

Exercise synthetic same-owner v0.20–v0.27 preparation and injected response
validation without a socket or Agent application invocation. Lock the exact
future HTTP shape, Mission Control absence, and blocked Home Assistant golden.

### P5 — Isolation, no-replay, and release closure — complete

Prove exact linkage, freshness, concurrency/ambiguity, ownership, bounds,
redaction, one-preparation no-replay, zero network/send surface, zero production
Core construction and Agent registration, capability parity, prior goldens,
and full regressions. Add no release/deployment action automatically.

P5 locks explicit-only construction, the exact fixed-disabled configuration,
zero send/network/credential-loading capability, append-only evidence storage,
zero production Core consumer, and continued test-only Agent route isolation.
Mission Control remains absent, Home Assistant remains blocked with no
deployment artifact, and P5 adds only tests and release evidence.

The exact authority is dormant preparation and validation only. Explicitly
constructed Core code may validate fixed-disabled connection metadata, resolve
owned evidence, preserve one immutable `not_sent` request, and validate an
already supplied closed result. Core cannot read credentials, call Agent, open
a socket, perform DNS/TLS/HTTP, claim delivery, or expose a production consumer.
Agent remains dormant and test-only. Neither side gains execution, runtime,
worker, workflow, installation, mutation, deployment, or rollback authority.

V0.28 enables later review of a separate authenticated HTTPS transport,
credential/CA provisioning, production Agent route registration, and one
atomic no-redelivery send without redesigning the frozen client boundary.
Production delivery and receipt, execution approval/consumption, runtime and
target effects, installation, deployment, rollback, Mission Control delivery
controls, and Home Assistant installation remain blocked.

## 18. Selected v0.29 plan — Controlled Delivery Activation Preflight

Atlas v0.29 is **Controlled Delivery Activation Preflight**. Its normative P0
contract is [Controlled Delivery Activation Preflight
v1](docs/architecture/delivery-activation-preflight-v1.md). P0 through P5 are
implemented and validated.

The narrow boundary is a Core-local, operator-owned eligibility snapshot over
one exact v0.28 `not_sent` preparation and its complete v0.20–v0.27 lineage.
It may later preserve and read one short-lived `eligible_for_later_activation`
or terminal `ineligible` result. Eligibility is not activation approval,
delivery authority, execution admission, or installation authority.

### P0 — Contract and threat-model freeze — selected

Freeze the exact request/result/linkage schemas, fingerprints, decision and
lifecycle values, ownership, authentication/authorization, freshness/expiry,
idempotency/no-replay, redaction/audit, default-disabled API/UI, authority,
goldens, and must-not-change contracts. Change planning documentation only.

### P1 — Closed models and pure evaluation — complete

Implement isolated immutable Core models and pure validation of the complete
same-owner v0.20–v0.28 chain over injected values and time. Add no I/O,
registration, store, route, or side effect.

### P2 — Bounded append-only preflight evidence — complete

Implement an explicitly constructed evaluator and independent operator-scoped
append-only store with atomic reservations, exact retry/no-replay, quotas,
restart durability, fail-closed ambiguity/corruption, and owned reads. Add no
consumer or activation bridge.

### P3 — Authenticated Core-local API — complete

Add only guarded create/list/item-read with narrow authz, exact bounds,
redaction, OpenAPI/method isolation, and default-disabled registration. The
request path must not contact Agent or reach secrets, transport, runtime,
worker, workflow, dispatch, provider, repository, or guest modules.

### P4 — Mission Control evidence review — complete

Add explicit local-preflight confirmation and read-only temporary eligibility
or blocker presentation. Add no activation, delivery, execution, installation,
deployment, rollback, endpoint, credential, Agent, or workflow control.

### P5 — Isolation, no-replay, and release closure — complete

Prove linkage, freshness/expiry, ownership/authz, concurrency, ambiguity,
redaction, exact retry/no-replay, API/UI bounds, zero Agent contact, zero
transport/secret/runtime registration, zero consumers, prior goldens,
capability parity, and full regressions. Do not automatically migrate, tag,
push, publish, deploy, or release.

P5 locks the evidence-only service/store, exact guarded Core route surface,
zero production construction and downstream consumers, zero Agent awareness,
Mission Control's evidence-only create/read presentation, capability parity,
and Home Assistant's blocked state. P5 adds tests and release evidence only.

The exact v0.29 authority is local evidence evaluation and durable
operator-owned preflight create/list/item read.
V0.29 must not activate delivery, send to Agent, register production transport
or the Agent route, load credentials or secrets, invoke a worker/workflow/
dispatch/runtime/process, mutate provider/repository/in-guest state, install,
deploy, roll back, or create a Home Assistant artifact.

V0.29 enables a later release to require a fresh, exact, nine-release-linked
eligibility proof before separately authorizing activation. Activation itself,
live authenticated transport and receipt, atomic consumption, execution
approval and runtime authority, all target effects, deployment, rollback, and
Home Assistant installation remain blocked.

## 19. Completed v0.30 plan — Operator-Controlled Delivery Enablement

Atlas v0.30 is **Operator-Controlled Delivery Enablement**. Its normative P0
contract is [Operator-Controlled Delivery Enablement
v1](docs/architecture/operator-controlled-delivery-enablement-v1.md). P0–P5
are complete.

The narrow boundary is one explicit, authenticated, owner-bound confirmation
over a still-eligible v0.29 preflight and its exact v0.20–v0.29 lineage. V0.30
preserves a short-lived `operator_enabled_for_later_delivery_consideration`
record. Operator-enabled is not activated, sent, delivery-authorized,
execution-admitted, installed, or deployed.

### P0 — Enablement contract and threat model — complete

Freeze exact schemas, linkage, fixed confirmation wording, fingerprints,
ownership/authz, inherited freshness/expiry, permanent idempotency/no-replay,
redaction/audit, default-off API/UI, authority, threats, goldens, and
must-not-change contracts. Change planning documentation only.

### P1 — Closed models and pure validation — complete

Implement immutable models and pure exact v0.20–v0.29 linkage, confirmation,
fingerprint, and lifecycle validation over injected values/time. Add no I/O,
store, route, client, registration, or side effect.

### P2 — Bounded append-only enablement evidence — complete

Implement the explicitly constructed local service and independent owner-scoped
append-only store with atomic permanent reservations, exact retry/no-replay,
quotas, corruption/ambiguity closure, and current reads. Add no consumer.

### P3 — Authenticated Core-local API — complete

Add only guarded create/list/item-read with narrow permissions, mutation
protections, strict bounds/parsing, ownership, redaction, exact OpenAPI/methods,
and default-off injected construction. Add no Agent or runtime dependency.

### P4 — Mission Control enablement evidence review — complete

Add the exact two-step **Enable exact delivery for later consideration only**
confirmation and read-only status/linkage/audit display. Add no activation,
send, delivery, execution, installation, deployment, rollback, or navigation.

### P5 — Isolation, no-replay, and release closure — complete

Prove confirmation/linkage/fingerprint sensitivity, expiry, ownership/authz,
concurrency/ambiguity/corruption, exact retry, API/UI bounds, zero consumers,
zero Agent/transport/secret/runtime registration, capability parity, prior
goldens, and full regressions. Add tests/release evidence only.

The exact v0.30 authority is revalidating one current same-owner v0.29
preflight and creating/listing/reading bounded durable operator-enable evidence
that expires with that preflight. A later release may require this record as
one prerequisite for separately designed atomic activation and delivery.

V0.30 does not activate, authorize, send, deliver, consume, or invoke Agent;
register transport; load secrets; dispatch; start a worker/workflow; run
Docker/Podman/shell/process/container work; install; mutate provider,
repository, or guest state; deploy; roll back; or create a Home Assistant
artifact. All those capabilities remain blocked.

## 20. Selected v0.31 plan — Live Delivery Send Boundary

Atlas v0.31 is **Live Delivery Send Boundary**. Its normative P0 contract is
[Live Delivery Send Boundary
v1](docs/architecture/live-delivery-send-boundary-v1.md). P0 through P5 are
implemented and validated.

The narrow boundary is one authenticated, synchronous, permanently single-use
HTTPS POST of the exact inert v0.27 intake request, after Core revalidates the
same-owner v0.20–v0.30 chain inside the inherited v0.29/v0.30 30-second window.
Agent may admit and acknowledge evidence only. Evidence delivery is not
execution admission, installation, dispatch, deployment, or mutation authority.

### P0 — Live-send contract and threat model — selected

Freeze exact request/result/admission/acknowledgement, linkage, fingerprint,
transport/authentication/credential-reference, lifecycle, ownership,
freshness, permanent idempotency/no-replay, redaction/audit, default-off API/
UI, threats, goldens, and must-not-change contracts. Change planning docs only.

### P1 — Closed live-send models and pure validation — implemented

Add immutable Core models and pure exact v0.20–v0.30 validation while reusing
the unchanged v0.27 request/result and v0.28 response validation. Add no I/O,
route, registration, credential read, or send.

### P2 — Durable Core reservation service and store — implemented

Added the explicitly constructed default-off Core reservation service and
append-only attempt store with exact linkage/freshness, owner scope, permanent
idempotency/no-replay, bounded restart-safe reads, and fail-closed corruption.
It adds no route, Agent invocation, network, credential read, or runtime
authority.

### P3 — One-shot Core send service — implemented

Add one explicitly constructed default-off synchronous HTTPS adapter and an
append-only attempt/receipt store. Permanently reserve before I/O, load only
the fixed credential and CA references, send at most once, validate the closed
response, and make every timeout/crash/indeterminate result non-retryable.

### P4 — Mission Control presentation absence — complete

No guarded Core create/list/item-read live-send API or UI-facing read model
exists after P3, so P4 does not invent an API bridge or Mission Control
surface. Structural tests prove there is no v0.31 client, type, hook, page,
route, navigation, mutation, retry/resend/refresh/send-again control, sensitive
transport rendering, prohibited authority label, or Home Assistant exception.

### P5 — Isolation, no-replay, and release closure — complete

P5 locks explicit construction, default-off and one-shot/no-automatic-retry
posture, inert evidence-only envelopes, permanent reservation/no-replay,
terminal ambiguity, secret-free persistence, redaction, and fixed-false
install/execute/deploy/mutate/worker/workflow authority. Release-isolation
tests prove no live-send evidence consumer in Core, Agent, or the execution
worker; no production Core route or Agent intake registration; no Mission
Control v0.31 surface or effect control; capability parity; and Home Assistant
blocking with no artifact. P5 adds tests and release documentation only.

Validation passed both Ruff gates, 60 focused Core release-isolation tests,
10 focused Agent intake-closure tests, the full Core suite (`3071 passed, 246
warnings in 193.85s (0:03:13)`), the full Agent suite (`1020 passed, 22
warnings in 11.42s`), and Mission Control (`84` files, `545` tests), lint, and
production build. Lint retained the pre-existing exhaustive-deps warning and
the build retained its existing chunk-size advisory; neither was an error.

The exact v0.31 authority is one operator-triggered, synchronous delivery of
one inert evidence envelope to one fixed authenticated Agent route, plus
durable redacted attempt/receipt evidence. It adds no broad transport, retry
daemon, scheduler, callback, worker, workflow, dispatch, runtime, installation,
provider/repository/in-guest mutation, deployment, rollback, or Home Assistant
artifact.

V0.31 enables a later separately frozen release to consider a successfully
admitted receipt as one prerequisite for a distinct execution-admission
decision. Receipt consumption, installation, runtime execution, all mutation,
deployment, rollback, recovery, and retry remain blocked.

## 21. Explicitly deferred work

- durable execution-candidate generation and install-container execution;
- executable Core install-container authority and Core-to-Agent dispatch;
- executable installation-intent lifecycle and approved installation targets;
- conversational execution or installation;
- generic image collection;
- D11 semantic Discovery and D12 community/private catalogs;
- distributed orchestration; and
- general VM/container lifecycle management.

## 22. Uncommitted future directions

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
