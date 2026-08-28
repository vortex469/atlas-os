# Atlas OS Roadmap

## 1. Current released baseline — v0.21

Atlas v0.21.0 is released as `atlas-v0.21.0` at `1ca7081` and its completed
milestone is merged to current `main` at `8be5d7f`.

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

The dependency order is P0 → P1 → P2 → P3 → P4 → P5. P0–P3 are complete and
P4–P5 are planned. Every phase remains
non-executing.

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

### P4 — Unsupported operator diagnostics — planned

Present bounded Agent capability/diagnostic evidence while keeping
`install-container` conspicuously unsupported and default-disabled. Add no
enable switch, install control, Mission Control workflow, or runtime call.

### P5 — Isolation, refusal, and regression closure — planned

Prove zero Core route/caller/dispatch, zero supported Agent intent, zero
worker/provider/repository/guest/runtime invocation, zero authority consumer,
exact no-replay/redaction behavior, Home Assistant rejection, and full
regression gates. Do not tag, push, publish, deploy, or release automatically.

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

## 12. Explicitly deferred work

- durable execution-candidate generation and install-container execution;
- Core install-container request authority and Core-to-Agent dispatch;
- executable installation-intent lifecycle and approved installation targets;
- conversational execution or installation;
- generic image collection;
- D11 semantic Discovery and D12 community/private catalogs;
- distributed orchestration; and
- general VM/container lifecycle management.

## 13. Uncommitted future directions

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
