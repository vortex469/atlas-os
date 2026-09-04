# Atlas Release Checklist and Evidence

Historical sections preserve the evidence recorded for their release. An
unchecked item is not implied to have passed.

## Atlas v0.42 P0 One-Shot Live Enqueue Boundary - selected

Atlas v0.42 is **One-Shot Live Enqueue Boundary**. P0 freezes the
documentation-only [v1 contract](architecture/one-shot-live-enqueue-boundary-v1.md).

- [x] Inspect the repository-supported v0.41 Live Enqueue Admission contracts,
  implementation, and release-isolation tests before defining v0.42.
- [x] Freeze exactly one new future authority: one explicitly authorized,
  single-use enqueue of one inert reference-only queue item after a valid
  same-owner v0.41 Live Enqueue Admission.
- [x] Freeze exact closed create, lineage, queue item, record/status, result,
  collection, reservation, idempotency, audit, and error schemas.
- [x] Freeze dedicated scope `installation_one_shot_live_enqueue_only` and
  dedicated `installation.execution.one_shot_live_enqueue.record` and `.read`
  permissions.
- [x] Freeze exact same-owner v0.20-v0.41 lineage and fingerprints, active
  v0.41 live-enqueue-admission binding, active v0.40 worker-intake-admission
  binding, active v0.39 queue-reservation binding, v0.40 worker identity and
  intake-reference binding, queue-intake-reference and queue-item-reference
  identity, active lifecycle, freshness, earliest inherited expiry, and
  byte-exact inherited limit fingerprints.
- [x] Freeze `one_shot_live_enqueue_recorded | readiness_gated | blocked |
  indeterminate`, closed lifecycle, outcome, blocker, audit-event, error, and
  authority vocabularies, and permanent successful-record blockers for
  undefined dequeue, queue polling, worker start, and execution start.
- [x] Freeze reservation-before-effect: durable permanent idempotency-key and
  item-subject reservations must complete before appending the inert queue
  item, and no failure or indeterminate outcome may release, consume, refresh,
  replace, supersede, retry, resend, or bypass a reservation.
- [x] Freeze success, failure, and indeterminate outcomes. Success creates
  exactly one inert reference-only item; failure creates no item; indeterminate
  keeps the subject permanently reserved and grants no retry/resend authority.
- [x] Freeze authenticated ownership, foreign/not-found non-disclosure,
  maximum inherited 30-second freshness, strict request/record/collection/
  nesting/quota/identifier bounds, deterministic domain-separated
  fingerprints, closed audit/redaction, and exclusion of raw keys, payloads,
  credentials, commands, logs, paths, endpoints, addresses, queue names,
  broker details, and arbitrary metadata.
- [x] Freeze only candidate-scoped collection GET/guarded POST and item GET,
  plus an optional nested Mission Control evidence panel with no polling,
  selectors, editable limits, sensitive rendering, extra mutation, or effect
  control.
- [x] Freeze Home Assistant blocked/non-artifact behavior, Agent and
  execution-worker zero-consumer isolation, default-off explicit construction,
  exact authority boundary, later enablement, P0-P5, threat model, and
  must-not-change contracts.
- [x] Keep P0 planning-only: no runtime model/store/migration/setting/
  permission/route/OpenAPI operation/UI code, queue library, payload schema,
  serializer, worker client, credential, endpoint, background task, Agent
  change, execution-worker change, dequeue, queue polling, worker
  start/contact, Agent invocation, scheduler/workflow execution,
  Docker/Podman/container/shell/process execution, installation, mutation,
  deployment, rollback, artifact, tag, push, publication, or change to
  `compose.execution-smoke.override.yaml`.
- [ ] P1 - closed immutable Core contract models and pure validation only.
- [ ] P2 - explicitly constructed append-only Core evidence service/store with
  injected owner-scoped readers, reservation-before-effect, permanent
  no-replay, and indeterminate append handling.
- [ ] P3 - exact guarded Core create/list/get evidence API only.
- [ ] P4 - strict Mission Control evidence presentation only.
- [ ] P5 - release isolation, regression, authority, no-replay, redaction,
  Agent/execution-worker parity, Home Assistant, and release evidence only.

## Atlas v0.41 P0 Live Enqueue Admission Boundary - selected

Atlas v0.41 is **Live Enqueue Admission Boundary**. P0 freezes the
documentation-only [v1 contract](architecture/live-enqueue-admission-v1.md).

- [x] Freeze exact closed create, enqueue-subject, admission-decision,
  inherited-limit, linkage, record/status, reservation, idempotency, audit,
  error, result, and collection schemas.
- [x] Freeze dedicated scope
  `installation_live_enqueue_admission_only`.
- [x] Freeze exact same-owner v0.20-v0.40 linkage and fingerprints, active
  v0.40 worker-intake-admission binding, active v0.39 queue-reservation
  binding, v0.40 worker identity/intake-reference binding, active lifecycle,
  freshness, earliest inherited expiry, and byte-exact inherited limit
  fingerprints.
- [x] Freeze `live_enqueue_admission_recorded | readiness_gated | blocked`,
  closed lifecycle, eligibility, blocker, audit-event, error, and authority
  vocabularies, and permanent successful-record blockers for undefined enqueue
  operation, dequeue, worker start, and execution start.
- [x] Freeze the invariant that admission evidence is not an enqueue operation
  and cannot define, serialize, submit, poll, claim, lease, dequeue, start, or
  execute work.
- [x] Freeze authenticated ownership, dedicated
  `installation.execution.live_enqueue_admission.record` and `.read`
  permissions, foreign/not-found non-disclosure, maximum inherited 30-second
  freshness, and earliest expiry.
- [x] Freeze atomic permanent idempotency-key and
  enqueue-admission-subject reservations, exact-duplicate zero-I/O readback,
  and no consume/release/refresh/replacement/supersession/retry/resend/replay
  bypass.
- [x] Freeze strict request, record, collection, nesting, quota, and identifier
  bounds, deterministic domain-separated fingerprints, closed audit/redaction,
  and exclusion of raw keys, payloads, credentials, commands, logs, paths,
  endpoints, addresses, queue names, and arbitrary metadata.
- [x] Freeze only candidate-scoped collection GET/guarded POST and item GET,
  plus an optional nested Mission Control evidence panel with no polling,
  selectors, editable limits, sensitive rendering, extra mutation, or effect
  control.
- [x] Freeze Home Assistant blocked/non-artifact behavior, Agent and
  execution-worker zero-consumer isolation, exact authority boundary, later
  enablement, P0-P5, threat model, and must-not-change contracts.
- [x] Keep P0 planning-only: no runtime model/store/migration/setting/
  permission/route/OpenAPI operation/UI code, queue library, payload schema,
  serializer, worker client, credential, endpoint, background task, Agent
  change, execution-worker change, live enqueue/dequeue, worker start/contact,
  installation, dispatch, execution, retry/resend, mutation, deployment,
  rollback, artifact, tag, push, publication, or release action.
- [ ] P1 - closed immutable Core contract models and pure validation only.
- [ ] P2 - explicitly constructed append-only Core evidence service/store with
  injected owner-scoped readers and permanent no-replay.
- [ ] P3 - exact guarded Core create/list/get evidence API only.
- [ ] P4 - strict Mission Control evidence presentation only.
- [ ] P5 - release isolation, regression, authority, no-replay, redaction,
  Agent/execution-worker parity, Home Assistant, and release evidence only.

## Atlas v0.40 P0-P5 Worker Intake Admission Boundary - complete

Atlas v0.40 is **Worker Intake Admission Boundary**. P0-P5 are complete from
the frozen [v1 contract](architecture/worker-intake-admission-boundary-v1.md).

- [x] Inspect post-v0.39 `main` at
  `fc2bd1edeab334837516243e7cc12b9d1dc58009`, after annotated
  `atlas-v0.39.0` targeting
  `474cd83e6e8edbcaa2694dcb62aa8ee93c52e684`.
- [x] Freeze exact create, worker identity, worker intake reference,
  admission decision, inherited-limit, linkage, record/status, reservation,
  idempotency, audit, error, result, and collection schemas.
- [x] Freeze exact same-owner v0.20-v0.39 linkage and fingerprints, active
  v0.39 queue-reservation binding, server-owned trusted clock/reference
  dependencies, and byte-exact inherited limit fingerprints.
- [x] Freeze `worker_intake_admission_recorded | readiness_gated | blocked`,
  the closed blocker vocabulary, and permanent successful-record blockers for
  live enqueue, dequeue, worker start, and execution start.
- [x] Freeze authenticated ownership, dedicated
  `installation.execution.worker_intake_admission.record` and `.read`
  permissions, exact intake-admission-only scope, foreign/not-found
  non-disclosure, maximum inherited 30-second freshness, and earliest expiry.
- [x] Freeze atomic permanent idempotency and subject reservations, exact-
  duplicate zero-I/O readback, and no consume/release/refresh/replacement/
  supersession/retry/resend/replay bypass.
- [x] Freeze strict bounds, deterministic domain-separated fingerprints,
  closed audit/redaction, and exclusion of raw keys, payloads, credentials,
  commands, logs, paths, endpoints, addresses, queue names, and arbitrary
  metadata.
- [x] Freeze only candidate-scoped collection GET/guarded POST and item GET,
  plus an optional nested Mission Control evidence panel with no polling,
  selectors, editable limits, sensitive rendering, extra mutation, or effect
  control.
- [x] Freeze Home Assistant blocked/non-artifact behavior, Agent and
  execution-worker zero-consumer isolation, exact authority boundary, later
  enablement, P0-P5, threats, and must-not-change contracts.
- [x] Keep P0 planning-only: no runtime model/service/store/reader/route/
  permission/UI, persistence, migration, queue/worker/Agent/network/process
  call, installation, execution, dispatch, retry/resend, mutation, deployment,
  rollback, artifact, tag, push, publication, or release action.
- [x] P1 - closed immutable Core contract models and pure validation only.
- [x] P2 - explicitly constructed append-only Core evidence service/store with
  injected owner-scoped readers and permanent no-replay.
- [x] P3 - exact guarded Core create/list/get evidence API only.
- [x] P4 - strict Mission Control evidence presentation only.
- [x] P5 - release isolation, regression, authority, no-replay, redaction,
  Agent/execution-worker parity, Home Assistant, and release evidence only.

P5 validation evidence:

- [x] Integrated Core OpenAPI exposes only candidate-scoped
  `GET`/guarded `POST` collection and owned item `GET` for
  `worker-intake-admissions`; no enqueue, dequeue, worker-start, execution,
  dispatch, retry/resend, Agent/workflow, install, deploy, rollback, replay,
  release, or mutation sibling route is present.
- [x] Closed models remain evidence-only with fixed-false queue, worker,
  execution, Agent/workflow, process, provider/repository/guest mutation,
  installation, deployment, rollback, retry/resend, and replay-bypass fields.
- [x] Service/store/contract isolation has no forbidden authority imports or
  effect calls, and the append-only store exposes no consume/release/update/
  delete/effect API.
- [x] Permanent idempotency and subject reservations survive concurrent
  duplicate creates, restart readback, and expiry; exact duplicates return
  without re-reading evidence or reissuing IDs, same-subject/different-key
  replay conflicts before expiry, and expired replay attempts fail closed.
- [x] Agent, execution-worker, dispatch, provider-intent, action, and deploy
  code contain no v0.40 worker-intake-admission consumer.
- [x] Home Assistant remains the blocked golden:
  `installation_capability_unsupported`, no admission record, no queue or
  worker authority, no execution authority, no deployment artifact, and
  Mission Control blocked/non-installable/non-executable copy.

## Atlas v0.39 P0–P5 Worker Queue Reservation Boundary — complete

Atlas v0.39 is **Worker Queue Reservation Boundary**. P0–P5 are complete from
the frozen [v1 contract](architecture/worker-queue-reservation-v1.md). P5
validation started from P4 commit
`ead37036b4843a262ad4b46f3d7b24257ec43abc`.

- [x] Inspect post-v0.38 `main` at
  `570bb7c1ef103dfce1c377baf8b7be9f4ec509ff`, after annotated
  `atlas-v0.38.0` targeting
  `1c1229fa9ad38722c85da3fbe3d7574d3ffe72b7`.
- [x] Freeze exact create, queue-intake reference, payload-free queue-item
  reference, inherited-limit, linkage, record/status, reservation,
  idempotency, audit, error, result, and collection schemas.
- [x] Freeze exact same-owner v0.20-v0.37 linkage, active v0.38 worker-
  admission-stub binding, server-owned trusted clock/reference dependencies,
  and byte-exact inherited limit fingerprints.
- [x] Freeze `worker_queue_reservation_recorded | readiness_gated | blocked`,
  the closed blocker vocabulary, and permanent successful-record blockers for
  live enqueue, dequeue, worker start, and execution start.
- [x] Freeze authenticated ownership, dedicated
  `installation.execution.worker_queue_reservation.record` and `.read`
  permissions, exact reservation-only scope, foreign/not-found non-disclosure,
  maximum inherited 30-second freshness, and earliest expiry.
- [x] Freeze atomic permanent idempotency and subject reservations, exact-
  duplicate zero-I/O readback, and no consume/release/refresh/replacement/
  supersession/retry/resend/replay bypass.
- [x] Freeze strict bounds, deterministic domain-separated fingerprints,
  closed audit/redaction, and exclusion of raw keys, payloads, credentials,
  commands, logs, paths, endpoints, addresses, and arbitrary metadata.
- [x] Freeze only candidate-scoped collection GET/guarded POST and item GET,
  plus an optional nested Mission Control evidence panel with no polling,
  selectors, editable limits, sensitive rendering, extra mutation, or effect
  control.
- [x] Freeze Home Assistant blocked/non-artifact behavior, Agent and execution-
  worker zero-consumer isolation, exact authority boundary, later enablement,
  P0-P5, threats, and must-not-change contracts.
- [x] Keep P0 planning-only: no runtime model/service/store/reader/route/
  permission/UI, persistence, migration, queue/worker/Agent/network/process
  call, installation, execution, dispatch, retry/resend, mutation, deployment,
  rollback, artifact, tag, push, publication, or release action.
- [x] P1 — closed immutable Core contract models and pure validation only.
- [x] P2 — explicitly constructed append-only Core evidence service/store with
  injected owner-scoped readers and permanent no-replay.
- [x] P3 — exact guarded Core create/list/get evidence API only.
- [x] P4 — strict Mission Control evidence presentation only.
- [x] P5 — release isolation, regression, authority, no-replay, redaction,
  Agent/execution-worker parity, Home Assistant, and release evidence only.

P5 validation evidence:

- [x] Atlas Core and Atlas Agent Ruff gates: `All checks passed!`.
- [x] Focused Atlas Core release suite: `76 passed, 155 warnings in 18.24s`.
- [x] Full Atlas Agent pytest: `1049 passed, 32 warnings in 11.55s`.
- [x] Mission Control: `102 passed` test files / `610 passed` tests; lint
  completed with zero errors and one pre-existing `WorkflowShellPage.tsx`
  hook-dependency warning; production build completed with only the advisory
  chunk-size warning.
- [x] `git diff --check`.
- [x] No runtime behavior, authority expansion, migration, live queue,
  enqueue/dequeue, worker start, execution, workflow/Agent invocation,
  dispatch, retry/resend, process execution, mutation, installation,
  deployment, rollback, Home Assistant artifact, tag, push, publication, or
  release action.
- [x] P5 closure commit:
  `7e78747edf702629d7d2b6da26f7773a31bc9697 test(v0.39): close worker queue reservation`.
- [x] Full Atlas Core clean-environment gate:
  `3423 passed, 546 warnings in 261.17s (0:04:21)`.
- [x] Exact reviewed implementation/validation SHA after P5 review:
  `7e78747edf702629d7d2b6da26f7773a31bc9697`.
- [x] Final release-preparation commit:
  `474cd83e6e8edbcaa2694dcb62aa8ee93c52e684 docs(v0.39): prepare release checklist`.
- [x] Verified the tracked worktree was clean at the final release-preparation
  commit; unrelated untracked `compose.execution-smoke.override.yaml` remained
  untouched and uncommitted.
- [x] Verified immutable annotated tag `atlas-v0.39.0` targets
  `474cd83e6e8edbcaa2694dcb62aa8ee93c52e684`.
- [x] Verified branch `v039-worker-queue-reservation-clean` and annotated tag
  `atlas-v0.39.0` were pushed to `origin`; the remote branch and peeled tag
  target are `474cd83e6e8edbcaa2694dcb62aa8ee93c52e684`.
- [ ] Publish the GitHub release for `atlas-v0.39.0`.

## Atlas v0.38 P0–P5 Worker Admission Stub — complete

Atlas v0.38 is **Worker Admission Stub**. P0–P5 are complete from the frozen
[v1 contract](architecture/worker-admission-stub-v1.md). P5 validation started
from P4 commit `1ca2f0f46cc300dd19ed89b4952e23635eff0a41`.

- [x] Inspect current `main` at
  `83d08274a805ca3c972e9827c6a2ce9253982758` after annotated
  `atlas-v0.37.0` targeting
  `eee726fe68da80ca2e4ecab9478494881836e648`.
- [x] Freeze exact create, intent, intake-stub, worker-reference,
  inherited-limit, linkage, stub, lifecycle/status, reservation, audit,
  redacted-error, result, and collection schemas with bounds and fixed-false
  authority.
- [x] Freeze authoritative same-owner v0.20–v0.36 linkage plus exact v0.37
  plan/status, runner/worker identity/reference/capability, intent, and limits
  fingerprints, with no client-supplied raw evidence.
- [x] Freeze only `worker_admission_stubbed`, ordered blocker vocabulary, and
  permanent successful-record blockers `worker_not_started`,
  `queue_boundary_not_defined`, and `execution_start_boundary_not_defined`.
- [x] Freeze authenticated ownership, dedicated record/read permissions,
  trusted clock, inherited maximum 30-second freshness, earliest expiry,
  permanent reservations, quotas, and Home Assistant rejection.
- [x] Freeze byte-exact inheritance of v0.37 confined sandbox/resource/network/
  filesystem ceilings as evidence bounds that do not create or prove a
  sandbox, workspace, container, queue, worker, or runtime enforcement.
- [x] Freeze atomic permanent idempotency-key and stub-subject reservations,
  exact-duplicate zero-I/O readback, and no consume, release, refresh, retry,
  resend, replay, replacement, supersession, repair, or bypass.
- [x] Freeze closed sanitized audit/errors and exclude raw keys, credentials,
  worker/runner/provider payloads, endpoints, addresses, ports, queues,
  commands, arguments, environment, logs, images, repositories, internal paths,
  mount sources, and arbitrary metadata.
- [x] Freeze exact candidate-scoped collection GET/guarded POST and item GET,
  plus a nested Mission Control list/get evidence panel; retain no surfaced
  creation absent server-owned worker context, effect sibling, polling,
  selector, form, navigation, editable intent/limit, or prohibited control.
- [x] Freeze complete isolation from the pre-existing execution-worker backend,
  relay, ledger, runner, request contracts, Agent, queues, dispatch, workflows,
  providers, repositories, guests, deployments, and rollback systems.
- [x] Freeze the evidence-only authority boundary, P0–P5 scope, threats, later
  enablement, blocked/non-artifact Home Assistant golden, and must-not-change
  contracts.
- [x] Keep P0 planning-only: no runtime model/service/store/reader/route/UI,
  persistence, migration, worker/queue/Agent/network/process call,
  installation, execution, dispatch, retry/resend, mutation, deployment,
  rollback, artifact, tag, push, publication, or release action.
- [x] P1 — closed immutable models, exact intent/reference/intake/linkage and
  byte-exact inherited-limit validation, deterministic fingerprints, bounds,
  redaction, fixed blockers, and fixed-false authority.
- [x] P2 — explicitly constructed append-only Core stub-evidence service/store
  with injected owner-scoped readers, atomic permanent reservations,
  restart-safe reads, quotas, corruption closure, and no effect dependency.
- [x] P3 — exact guarded candidate-scoped collection GET/POST and item GET,
  strict auth/permission/origin/CSRF/rate/parsing gates, redaction, and no
  effect-bearing sibling route.
- [x] P4 — strict Mission Control stub-evidence presentation using only P3
  create/list/get, with no polling, sensitive rendering, standalone
  navigation, editable worker/intent/limits, extra mutation, or prohibited
  control.
- [x] P5 — exact API and zero-consumer isolation,
  `worker_admission_stubbed` fixed-false authority, concurrency/restart
  permanent no-replay, secret-free persistence, Agent/execution-worker parity,
  Mission Control structural closure, Home Assistant golden, and release
  evidence.

P5 validation evidence:

- [x] Atlas Core and Atlas Agent Ruff gates: `All checks passed!`.
- [x] Focused Atlas Core release suite: `98 passed, 144 warnings in 22.17s`.
- [x] Full Atlas Agent pytest: `1049 passed, 32 warnings in 11.54s`.
- [x] Mission Control: `100 passed` test files / `605 passed` tests; lint
  completed with zero errors and one pre-existing `WorkflowShellPage.tsx`
  hook-dependency warning; production build completed with only the advisory
  chunk-size warning.
- [x] `git diff --check`.
- [x] No runtime behavior, authority expansion, migration, worker start,
  queue/enqueue, runner binding, execution/workflow start, dispatch,
  retry/resend, Agent invocation, process execution, mutation, deployment,
  rollback, Home Assistant artifact, tag, push, publication, or release action.
- [x] P5 closure commit:
  `f1dffeb6bff79496562bdbb5d2555930a9e7e5da test(v0.38): close worker admission stub`.
- [x] Full Atlas Core clean-environment gate:
  `3373 passed, 496 warnings in 253.43s (0:04:13)`.
- [x] Exact reviewed implementation/validation SHA after P5 review:
  `f1dffeb6bff79496562bdbb5d2555930a9e7e5da`.
- [x] Final release-preparation commit:
  `1c1229fa9ad38722c85da3fbe3d7574d3ffe72b7 docs(v0.38): prepare release checklist`.
- [x] Verified the tracked worktree was clean at the final release-preparation
  commit.
- [x] Verified immutable annotated tag `atlas-v0.38.0` targets
  `1c1229fa9ad38722c85da3fbe3d7574d3ffe72b7`.
- [x] Verified branch `v038-worker-admission-stub` and annotated tag
  `atlas-v0.38.0` were pushed to `origin`; the remote branch and peeled tag
  target are `1c1229fa9ad38722c85da3fbe3d7574d3ffe72b7`.
- [ ] Publish the GitHub release for `atlas-v0.38.0`.

## Atlas v0.37 P0–P5 Runner Binding Plan — complete

Atlas v0.37 is **Runner Binding Plan**. P0–P5 are complete from the frozen
[v1 contract](architecture/runner-binding-plan-v1.md). P5 validation started
from P4 commit `25bb21c58bf465ddc9fcf2895c6beb2301ba4e21`.

- [x] Inspect current `main` at
  `0b23b2c292e65b293a8097c74c3ab11b5d3295dd` after annotated
  `atlas-v0.36.0` targeting
  `d02e04126fd4a897c9faaab0f68b49d84f218044`.
- [x] Freeze exact create, runner-reference, sandbox/resource/network/
  filesystem-limit, linkage, plan, lifecycle/status, reservation, audit,
  redacted-error, and result schemas with bounds and fixed-false authority.
- [x] Freeze authoritative same-owner v0.20–v0.35 linkage plus exact v0.36
  admission/status, runner identity/reference/capability, and limit
  fingerprints, with no client-supplied raw evidence.
- [x] Freeze only `binding_planned`, ordered blocker vocabulary, and permanent
  successful-record blockers `runner_not_bound` and
  `execution_start_boundary_not_defined`.
- [x] Freeze authenticated ownership, dedicated record/read permissions,
  trusted clock, inherited maximum 30-second freshness, earliest expiry, and
  Home Assistant rejection.
- [x] Freeze exact confined sandbox/resource ceilings, network `none`, and
  ephemeral-workspace-only filesystem semantics as evidence ceilings that do
  not create or prove a sandbox or runtime enforcement.
- [x] Freeze atomic permanent idempotency-key and binding-subject reservations,
  exact-duplicate zero-I/O readback, and no consume, release, refresh, retry,
  resend, replay, replacement, supersession, or bypass.
- [x] Freeze closed sanitized audit/errors and exclude raw keys, credentials,
  runner/provider payloads, endpoints, commands, logs, images, internal paths,
  mount sources, addresses, and arbitrary metadata.
- [x] Freeze exact candidate-scoped collection GET/guarded POST and item GET,
  plus one optional Mission Control two-step plan-evidence panel; retain no
  effect/action sibling, polling, live runner selector, editable limit, or
  prohibited control.
- [x] Freeze the exact evidence-only authority boundary, P0–P5 scope, threats,
  later enablement, blocked/non-artifact Home Assistant golden, and
  must-not-change contracts.
- [x] Keep P0 planning-only: no runtime model/service/store/reader/route/UI,
  persistence, migration, credential/network/Agent/runner call, installation,
  execution, worker/workflow, dispatch, retry/resend, Docker/Podman/shell,
  mutation, deployment, rollback, artifact, tag, push, publication, or release
  action.
- [x] P1 — closed immutable models, exact runner/limit/linkage validation,
  deterministic fingerprints, bounds, redaction, fixed blockers, and
  fixed-false authority.
- [x] P2 — explicitly constructed append-only Core plan-evidence service/store
  with injected owner-scoped readers, atomic permanent reservations,
  restart-safe reads, quotas, corruption closure, and no effect dependency.
- [x] P3 — exact guarded candidate-scoped collection GET/POST and item GET,
  strict auth/permission/origin/CSRF/rate/parsing gates, redaction, and no
  effect-bearing sibling route.
- [x] P4 — strict Mission Control plan-evidence presentation using only P3
  create/list/get, with no polling, sensitive rendering, standalone
  navigation, editable runner/limits, extra mutation, or prohibited control.
- [x] P5 — exact API and zero-consumer isolation, `binding_planned` fixed-false
  authority, concurrency/restart permanent no-replay, secret-free persistence,
  Agent parity, Mission Control structural closure, Home Assistant golden, and
  release evidence.

P5 validation evidence:

- [x] Atlas Core and Atlas Agent Ruff gates: `All checks passed!`.
- [x] Focused Atlas Core release suite: `104 passed, 129 warnings in 21.91s`.
- [x] Full Atlas Agent pytest: `1049 passed, 32 warnings in 13.03s`.
- [x] Mission Control: `97 passed` test files / `596 passed` tests; lint
  completed with zero errors and one pre-existing `WorkflowShellPage.tsx`
  hook-dependency warning; production build completed with only the advisory
  chunk-size warning.
- [x] `git diff --check`.
- [x] No runtime behavior, authority expansion, migration, runner binding,
  execution/worker/workflow start, dispatch, retry/resend, Agent invocation,
  process execution, mutation, deployment, rollback, Home Assistant artifact,
  tag, push, publication, or release action.
- [x] P5 closure commit:
  `0271f488a9a73f7badd530abf0ce0e9d489a804f test(v0.37): close runner binding plan`.
- [x] Full Atlas Core clean-environment gate:
  `3242 passed, 447 warnings in 237.14s (0:03:57)`.
- [x] Exact reviewed implementation/validation SHA after P5 review:
  `0271f488a9a73f7badd530abf0ce0e9d489a804f`.
- [x] Final release-preparation commit:
  `eee726fe68da80ca2e4ecab9478494881836e648 docs(v0.37): prepare release checklist`.
- [x] Verified the tracked worktree was clean at the final release-preparation
  commit.
- [x] Verified immutable annotated tag `atlas-v0.37.0` targets
  `eee726fe68da80ca2e4ecab9478494881836e648`.
- [x] Verified branch `v037-runner-binding-plan` and annotated tag
  `atlas-v0.37.0` were pushed to `origin`; the remote branch and peeled tag
  target are `eee726fe68da80ca2e4ecab9478494881836e648`.
- [ ] Publish the GitHub release for `atlas-v0.37.0`.

## Atlas v0.36 P0–P5 Installation Execution Admission Boundary — complete

Atlas v0.36 is **Installation Execution Admission Boundary**. P0 is the
documentation-only frozen [v1
contract](architecture/installation-execution-admission-v1.md).

- [x] Inspect current `main` at
  `adb74c2a49fee28483ebe48c703b6887bcee7ee9` after annotated
  `atlas-v0.35.0` targeting
  `5c56940e21db9e80a9470d2db434415d02dff9ac`.
- [x] Freeze exact create, linkage, runner-eligibility, admission, lifecycle,
  reservation, audit, redacted-error, and result schemas with bounds and
  fixed-false effect authority.
- [x] Freeze authoritative same-owner v0.20–v0.34 linkage plus exact v0.35
  grant/status/request/confirmation/operator fingerprints, with no
  client-supplied raw evidence.
- [x] Freeze `blocked | admission_gated`, ordered blocker vocabulary, and the
  permanent successful-record blockers `runner_binding_not_defined` and
  `execution_start_boundary_not_defined`.
- [x] Freeze authenticated ownership, dedicated record/read permissions,
  trusted clock, inherited maximum 30-second freshness, earliest expiry, and
  Home Assistant rejection.
- [x] Freeze atomic permanent idempotency-key and grant-subject reservations,
  exact-duplicate zero-I/O readback, and no consume, release, refresh, retry,
  resend, replay, replacement, or bypass.
- [x] Freeze closed sanitized audit/errors and exclude raw keys, credentials,
  provider payloads, commands, logs, internal paths, addresses, endpoints, and
  arbitrary metadata.
- [x] Freeze exact candidate-scoped collection GET/guarded POST and item GET,
  plus one optional Mission Control two-step admission-evidence panel; retain
  no effect/action sibling, polling, runner selector, or prohibited control.
- [x] Freeze the exact evidence-only authority boundary, P0–P5 scope, threats,
  later enablement, blocked/non-artifact Home Assistant golden, and
  must-not-change contracts.
- [x] Keep P0 planning-only: no runtime model/service/store/permission/route/UI,
  persistence, migration, credential/network/Agent/runner call, installation,
  execution, dispatch, retry/resend, worker/workflow/process, Docker/Podman/
  shell, mutation, deployment, rollback, artifact, tag, push, publication, or
  release action.
- [x] P1 — closed immutable models, deterministic domain-separated
  fingerprints, exact linkage, bounds, redaction, fixed blockers, and pure
  non-authorizing validation.
- [x] P2 — explicitly constructed append-only Core evidence service/store with
  owner-scoped injected readers, atomic permanent reservations, restart-safe
  reads, quotas, corruption closure, and no effect dependency.
- [x] P3 — exact guarded candidate-scoped collection GET/POST and item GET,
  strict auth/permission/origin/CSRF/rate/parsing gates, redaction, and no
  effect-bearing sibling route.
- [x] P4 — strict Mission Control admission-evidence presentation using only
  P3 create/list/get, with explicit evidence-only copy, no polling, sensitive
  rendering, navigation, extra mutation, or prohibited control.
- [x] P5 — exact API and consumer isolation, admission-gated fixed-false
  authority, concurrency/restart permanent no-replay, Agent zero-consumer,
  Mission Control regression, Home Assistant golden, and release evidence.

P5 validation evidence:

- [x] Atlas Core and Atlas Agent Ruff gates.
- [x] Targeted Atlas Core release suite: `97 passed, 111 warnings in 18.28s`.
- [x] Full Atlas Agent pytest: `1047 passed, 32 warnings in 11.78s`.
- [x] Mission Control: `94 passed` test files / `585 passed` tests; lint
  completed with zero errors and one pre-existing `WorkflowShellPage.tsx`
  hook-dependency warning; production build completed.
- [x] `git diff --check`.
- [x] No runtime behavior, authority expansion, migration, runner binding,
  execution start, dispatch, retry/resend, Agent invocation, effect,
  deployment, rollback, Home Assistant artifact, tag, push, publication, or
  release action.
- [x] P5 closure commit:
  `720c1be9d71ba8556b04ea34e7e96402f6711ab6 test(v0.36): close installation execution admission`.
- [x] Full Atlas Core clean-environment release-preparation gate passed:
  `3201 passed, 396 warnings in 230.74s (0:03:50)`.
- [x] Exact reviewed implementation/validation SHA after P5 review:
  `720c1be9d71ba8556b04ea34e7e96402f6711ab6`.
- [x] Final release-preparation commit:
  `d02e04126fd4a897c9faaab0f68b49d84f218044 docs(v0.36): prepare release checklist`.
- [x] Verified the tracked worktree was clean at the final release-preparation
  commit.
- [x] Created immutable annotated tag `atlas-v0.36.0` targeting
  `d02e04126fd4a897c9faaab0f68b49d84f218044`.
- [x] Pushed branch `v036-installation-execution-admission` and annotated tag
  `atlas-v0.36.0` to `origin`; the tag target is
  `d02e04126fd4a897c9faaab0f68b49d84f218044`.
- [ ] Publish the GitHub release for `atlas-v0.36.0`.

## Atlas v0.35 P0 Execution Permission Grant Boundary — selected

Atlas v0.35 is **Execution Permission Grant Boundary**. P0 is the
documentation-only frozen [v1 contract](architecture/execution-permission-grant-v1.md).

- [x] Inspect current `main` at
  `5965e3c016a4ee1e6d871d675964cbe40b04e353` after annotated
  `atlas-v0.34.0` targeting
  `fb3d9014574b5aa85a1024d77fe7b29bf35e1b88`.
- [x] Freeze the exact create, linkage, durable grant, derived status, audit,
  redacted-error, and result schemas with strict bounds and fixed-false effect
  authority.
- [x] Freeze exact same-owner v0.20–v0.33 linkage plus v0.34 review, audit, and
  operator fingerprints, with authoritative recomputation and no
  client-supplied linkage.
- [x] Freeze the exact confirmation text, dedicated operator permission,
  trusted-clock ownership rules, and maximum inherited 30-second freshness.
- [x] Freeze append-only durability, atomic permanent idempotency/subject
  reservations, exact-duplicate zero-I/O readback, and no refresh, retry,
  replay, revoke, consume, or replacement.
- [x] Freeze the guarded Core POST and owned GET readback, then apply the P3
  implementation amendment for owner-scoped collection GET only; retain no
  action, install, execute, dispatch, retry/resend, deploy, rollback, or
  mutation sibling.
- [x] Freeze the exact Mission Control confirmation/readback panel, explicit
  non-authorizing copy, ambiguous-write behavior, redaction, and absence of
  polling, sensitive data, or effect controls.
- [x] Freeze P0–P5 scope, exact authority increase, later enablement, threats,
  blocked Home Assistant golden, and must-not-change contracts.
- [x] Keep P0 planning-only: no runtime model/service/store/permission/route/UI,
  persistence, migration, credential/network/Agent call, installation,
  execution, dispatch, retry/resend, worker/workflow/process, Docker/Podman/
  shell, mutation, deployment, rollback, artifact, tag, push, publication, or
  release action.
- [x] P1 — closed immutable grant, linkage, lifecycle, idempotency,
  permanent-reservation, audit, error, and result models with deterministic
  fingerprints and pure ownership, permission, exact-confirmation, freshness,
  expiry, authority, and Home Assistant blocked-golden validation.
- [x] P2 — explicitly constructed default-off owner-scoped service and bounded
  append-only store with atomic durable grant/audit evidence, permanent
  idempotency and review-subject reservations, exact-duplicate zero-reader
  readback, quotas, corruption checks, derived lifecycle, and redaction.
- [x] P3 — dedicated create and owned-read permissions, exact candidate-scoped
  collection GET/guarded POST and item GET, strict security/parsing gates,
  redaction, locked OpenAPI, and independent durable database setting.
- [x] P4 — exact Mission Control confirmation and readback panel using only
  strict P3 create/list/get, with two-step exact-text evidence confirmation,
  lifecycle/linkage/audit readback, permanent no-replay posture, redaction,
  fixed-false authority, and blocked Home Assistant presentation.
- [x] P5 — exact route and consumer isolation, fixed-false authority,
  concurrent/restart permanent reservation and no-replay closure, sensitive
  persistence/rendering exclusion, Mission Control and Agent regression
  coverage, and blocked/non-artifact Home Assistant validation.

P5 validation evidence:

- [x] Atlas Core and Atlas Agent Ruff gates.
- [x] Full Atlas Core pytest: `3167 passed, 355 warnings in 222.62s
  (0:03:42)`.
- [x] Full Atlas Agent pytest: `1045 passed, 32 warnings in 13.61s`.
- [x] Mission Control: `91 passed` test files / `573 passed` tests; lint
  completed with zero errors and one pre-existing `WorkflowShellPage.tsx`
  hook-dependency warning; production build completed.
- [x] `git diff --check`.
- [x] No runtime behavior, authority expansion, migration, installation,
  execution, dispatch, Agent invocation, effect, deployment, rollback, Home
  Assistant artifact, tag, push, publication, or release action.
- [x] P5 closure commit:
  `42cbd86921e921edcc05aeeee0b4500fa177c13e test(v0.35): close execution permission grant`.
- [x] Full Atlas Core clean-environment release-preparation gate passed:
  `3167 passed, 355 warnings in 222.62s (0:03:42)`.
- [x] Exact reviewed implementation/validation SHA after P5 review:
  `42cbd86921e921edcc05aeeee0b4500fa177c13e`.
- [x] Final release-preparation commit:
  `5c56940e21db9e80a9470d2db434415d02dff9ac docs(v0.35): prepare release checklist`.
- [x] Verified the tracked worktree was clean at the final release-preparation
  commit.
- [x] Created immutable annotated tag `atlas-v0.35.0` targeting
  `5c56940e21db9e80a9470d2db434415d02dff9ac`.
- [x] Pushed branch `v035-execution-permission-grant` and annotated tag
  `atlas-v0.35.0` to `origin`; the tag target is
  `5c56940e21db9e80a9470d2db434415d02dff9ac`.
- [ ] Publish the GitHub release for `atlas-v0.35.0`.

## Atlas v0.34 P0 Installation Readiness Review — selected

Atlas v0.34 is **Installation Readiness Review**. P0 is the documentation-only
frozen [v1 contract](architecture/installation-readiness-review-v1.md).

- [x] Inspect current `main` at
  `343f683efb872b4b6322e27eaeffa64ccc4893ce` after annotated
  `atlas-v0.33.0` targeting
  `4bc30527b1c5a99eb090a43619494bb557791a50`.
- [x] Freeze the exact closed review, evidence-summary, linkage, blocker,
  audit, redacted-error, deterministic ID, and fingerprint contracts.
- [x] Freeze recomputation of every same-owner v0.20–v0.33 fingerprint and
  transitive identity, with no repair or inference for missing Agent evidence.
- [x] Freeze each released freshness, expiry, terminal ambiguity, and no-replay
  rule without extending, refreshing, or restarting any window.
- [x] Freeze one owner-scoped authenticated Core GET using the existing
  `installation.destination.select` permission and exact non-disclosing error
  behavior, with no collection or action/mutation sibling.
- [x] Freeze one read-only Mission Control page with no form, button, polling,
  retry/resend/admit/send/install/execute/dispatch/deploy/workflow control, raw
  evidence, secret, credential, endpoint, body, command, or internal path.
- [x] Freeze P0–P5 scope, exact read-only authority, later enablement, threats,
  blocked Home Assistant golden, and must-not-change contracts.
- [x] Keep P0 planning-only: no runtime model/service/reader/route/UI,
  persistence, credential access, Agent/network call, execution, mutation,
  deployment, rollback, artifact, migration, tag, push, publication, or
  release action.
- [x] P1 — closed models and pure review evaluation.
- [x] P2 — owner-scoped local read composition with deterministic ephemeral
  results, ownership isolation, redaction, and no persistence or reservation.
- [x] P3 — exact authenticated read-only Core GET, permission and ownership
  isolation, closed redacted errors, and locked OpenAPI surface.
- [x] P4 — strictly parsed read-only Mission Control presentation with ordered
  evidence, linkage, audit, redaction, authority copy, and no effect controls.
- [x] P5 — isolation, regression, authority closure, Home Assistant golden,
  and Core/Agent/Mission Control release validation evidence.

P5 closure validates both Python lint gates, the complete Core and Agent test
suites, the complete Mission Control test/lint/build gates, and
`git diff --check`. The frozen surface remains one Core GET and one read-only
Mission Control presentation. No tag, push, publication, release, deployment,
migration, or runtime effect is part of this closure commit.

Validation evidence for P5:

- Atlas Core: `3133 passed, 315 warnings in 219.09s`.
- Atlas Agent: `1045 passed, 32 warnings in 11.59s`.
- Mission Control: `89` test files and `566` tests passed; lint completed with
  the pre-existing `WorkflowShellPage.tsx` exhaustive-deps warning and no
  errors; the production TypeScript/Vite build passed.
- Both Python Ruff gates and `git diff --check` passed.
- [x] P5 closure commit:
  `9098c7f92d26c980d5739a7a3098e3d692777514 test(v0.34): close installation readiness review`.
- [x] Full Atlas Core clean-environment release-preparation gate passed:
  `3133 passed, 315 warnings in 219.09s (0:03:39)`.
- [x] Exact reviewed implementation/validation SHA after P5 review:
  `9098c7f92d26c980d5739a7a3098e3d692777514`.
- [x] Final release-preparation commit:
  `fb3d9014574b5aa85a1024d77fe7b29bf35e1b88 docs(v0.34): prepare release checklist`.
- [x] Verified the tracked worktree was clean at the final release-preparation
  commit.
- [x] Created immutable annotated tag `atlas-v0.34.0` targeting
  `fb3d9014574b5aa85a1024d77fe7b29bf35e1b88`.
- [x] Pushed branch `v034-installation-readiness-review` and annotated tag
  `atlas-v0.34.0` to `origin`; the remote branch and peeled tag target both
  resolve to `fb3d9014574b5aa85a1024d77fe7b29bf35e1b88`.
- [ ] Publish the GitHub release for `atlas-v0.34.0`.

## Atlas v0.33 P0–P5 End-to-End Inert Delivery Receipt — complete

Atlas v0.33 is **End-to-End Inert Delivery Receipt**. P0 is the
documentation-only frozen
[v1 contract](architecture/end-to-end-inert-delivery-receipt-v1.md).

- [x] Inspect current `main` after annotated `atlas-v0.32.0` and record the
  exact baseline and causal attempt/envelope/admission/receipt ordering.
- [x] Freeze the exact internal request, Core verification, receipt, status,
  redacted-error, audit, idempotency, and deterministic fingerprint schemas.
- [x] Freeze exact same-owner v0.20–v0.32 linkage and preserve the inherited
  maximum 30-second freshness window.
- [x] Reuse the exact v0.32 envelope/result and sole guarded Agent POST without
  a callback, second route, Agent action, or Core claim of Agent-store access.
- [x] Freeze the exact v0.31 HTTPS, fixed-principal, mode-0400 credential-
  reference, bounded timeout, independent default-off, one-shot/no-retry, and
  terminal ambiguity rules.
- [x] Freeze append-only durability, permanent reservation/no-replay,
  ownership, redaction/audit, absent public Core API/Mission Control surface,
  P0–P5 scope, threats, goldens, authority, blockers, and invariants.
- [x] Keep P0 planning-only: no runtime model/service/store/route/UI,
  credential read, network, Agent call, retry, execution, mutation, deployment,
  rollback, Home Assistant artifact, migration, tag, push, or release action.
- [x] P1 — closed Core receipt models and pure verification
  (`b9b39855ce4f994d42285c3de0f63925b4dd55ea`).
- [x] P2 — default-off durable Core verification service/store
  (`d4730f658880e31445ab1b8ed88969a6a53ab914`).
- [x] P3 — explicitly constructed one-shot end-to-end composition
  (`bf51afd860d4b8efe1c5014dcd16f0b8e51d1c2c`).
- [x] P4 — lock public Core API and Mission Control presentation absence;
  prohibit v0.33 clients/types/hooks/pages/routes/navigation, read or mutation
  calls, verification/retry/resend/effect controls, sensitive rendering, and
  Home Assistant exceptions without adding runtime behavior.
- [x] P5 — release isolation, regressions, authority closure, and evidence.

### P5 authority and isolation gates

- [x] Keep v0.33 explicitly constructed as internal composition only, with no
  production registration, public Core API, or Mission Control surface.
- [x] Keep verification one-shot, permanently reserved, append-only, durable,
  and secret-free, with exact duplicate zero I/O and no retry/resend path.
- [x] Keep receipt/result/acknowledgement evidence fixed false for effect
  authority and unconsumed by installation, workflow, worker, dispatch,
  provider/repository/in-guest mutation, deployment, rollback, or replay.
- [x] Preserve v0.31 Core live send as one-shot/no-retry and v0.32 Agent intake
  as admission-only on its exact guarded internal POST.
- [x] Keep Mission Control free of a v0.33 API client, UI, route, navigation,
  and retry/resend/admit/send/install/execute/deploy/workflow/mutation control.
- [x] Preserve Home Assistant as blocked, non-installable, non-executable, and
  without a deployment artifact.
- [x] Add only release-isolation/authority tests and release-status documents;
  add no runtime behavior, authority, API/UI, migration, tag, push, release,
  or deployment.

### P5 observed validation evidence

- [x] Both requested Atlas Core and Atlas Agent Ruff gates passed.
- [x] Full Atlas Core regression passed:
  `3107 passed, 293 warnings in 208.00s (0:03:28)`.
- [x] Full Atlas Agent regression passed:
  `1045 passed, 32 warnings in 10.62s`.
- [x] Mission Control passed 86 test files and 555 tests, lint, and production
  build. Lint retained one pre-existing exhaustive-deps warning and no errors;
  build retained only the existing chunk-size advisory.
- [x] `git diff --check` passed.
- [x] P5 closure commit:
  `b7107be4f73d1e4eddd1861517463942455a9d5f test(v0.33): close inert delivery receipt`.
- [x] Full Atlas Core clean-environment release-preparation gate passed:
  `3107 passed, 293 warnings in 206.46s (0:03:26)`.
- [x] Exact reviewed implementation/validation SHA after P5 review:
  `b7107be4f73d1e4eddd1861517463942455a9d5f`.
- [x] Final release-preparation commit:
  `4bc30527b1c5a99eb090a43619494bb557791a50 docs(v0.33): prepare release checklist`.
- [x] Verified the tracked worktree was clean at the final release-preparation
  commit.
- [x] Created immutable annotated tag `atlas-v0.33.0` targeting
  `4bc30527b1c5a99eb090a43619494bb557791a50`.
- [x] Pushed branch `v033-inert-delivery-receipt` and annotated tag
  `atlas-v0.33.0` to `origin`; the remote branch and peeled tag target both
  resolve to `4bc30527b1c5a99eb090a43619494bb557791a50`.
- [ ] Publish the GitHub release for `atlas-v0.33.0`.

## Atlas v0.32 P0–P5 Agent Live Intake Admission — complete

Atlas v0.32 is **Agent Live Intake Admission**. P0–P5 are complete from the
frozen [v1 contract](architecture/agent-live-intake-admission-v1.md). P5
validation started from `2ca93dbfb24bcfe85f92440595fb0f6c56c6e2ce`.

- [x] Inspect current `main` after annotated `atlas-v0.31.0` and record the
  exact planning baseline and causal send/admission/receipt ordering.
- [x] Freeze the exact inert request envelope and Agent admission,
  acknowledgement, result, record, lifecycle, redacted-error, audit, and
  deterministic fingerprint schemas.
- [x] Freeze exact same-owner v0.20–v0.30 linkage plus the v0.31 reserved send
  attempt, with Agent output feeding the downstream v0.31 Core receipt/result.
- [x] Preserve the inherited maximum 30-second freshness/expiry window.
- [x] Freeze permanent atomic no-replay, idempotency, ownership, append-only
  durability, fail-closed corruption, quota, and record-bound rules.
- [x] Freeze fixed HTTPS/path registration, default-off production settings,
  fixed-Core-principal authentication, and injected mode-0400
  credential-reference verification without secret persistence or disclosure.
- [x] Freeze the single internal Agent POST and exact OpenAPI boundary, absent
  public Core/Mission Control surfaces, P0–P5 scope, threats, goldens,
  authority, later enablement, blockers, and must-not-change contracts.
- [x] Keep P0 planning-only: no model/service/store/route/UI implementation,
  production registration, credential read, Agent call, retry, install,
  execution, worker/workflow/dispatch, mutation, deployment, rollback, Home
  Assistant artifact, migration, tag, push, publication, or release action.
- [x] P1 — closed mirrored Agent/Core models and pure validation
  (`64ff2e4526f8d3904ca37f3fb0f91d21d3d4bc18`).
- [x] P2 — default-off durable Agent admission service/store
  (`d4ff6f480a6a1b945947c1f5d78e3fa7a9c74b1b`).
- [x] P3 — guarded default-off production Agent route registration
  (`c9b6a8a0be035575bc91d9181013fde736eef34c`).
- [x] P4 — keep Mission Control absent; structural locks prohibit a v0.32
  client, hook, component, page, route, navigation, mutation, admit/retry/
  resend/send-again or effect control, sensitive rendering, and Home Assistant
  exception. No Core API bridge or runtime behavior is added.
- [x] P5 — isolation, no-replay, regressions, and release closure.

### P5 authority and isolation gates

- [x] Keep admission default-off and production-registered only through the
  exact guarded `POST /api/v1/internal/installation-intake` route.
- [x] Keep admission evidence-only, append-only, one-envelope no-replay, and
  secret-free in durable records, logs, audit evidence, and redacted errors.
- [x] Keep install, execute, deploy, mutate, dispatch, worker, workflow, and
  replay authority fixed false with no downstream evidence consumer.
- [x] Preserve the Core live-send boundary as explicitly constructed,
  one-shot, and without automatic retry or broader delivery machinery.
- [x] Keep Mission Control free of v0.32 clients, UI, routes, navigation,
  mutation/retry/resend/admit/send/install/execute/deploy/workflow controls,
  raw envelopes, credentials, tokens, or sensitive evidence.
- [x] Preserve capability parity and Home Assistant as blocked,
  non-installable, non-executable, and without a deployment artifact.
- [x] Add only release-isolation/authority tests and the five release-status
  documents; add no runtime, migration, tag, push, release, or deployment.

### P5 observed validation evidence

- [x] Both requested Atlas Core and Atlas Agent Ruff gates passed.
- [x] Focused Core release-isolation validation passed:
  `61 passed, 47 warnings in 9.93s`.
- [x] Focused Agent v0.32 closure validation passed:
  `5 passed, 20 warnings in 0.82s`.
- [x] Full Atlas Core clean-environment validation passed:
  `3072 passed, 246 warnings in 195.20s (0:03:15)`.
- [x] Full Atlas Agent validation passed:
  `1045 passed, 32 warnings in 10.93s`.
- [x] Mission Control passed 85 test files and 550 tests, lint, and production
  build. Lint retained one pre-existing exhaustive-deps warning and no errors;
  build retained only the existing chunk-size advisory.
- [x] `git diff --check` passed.
- [x] P5 closure commit:
  `611890a9bbf1bbee7f16663659695a2e0ad77a1f test(v0.32): close agent live intake admission`.
- [x] Full Atlas Core clean-environment release-preparation gate passed:
  `3072 passed, 246 warnings in 195.20s (0:03:15)`.
- [x] Exact reviewed implementation/validation SHA after P5 review:
  `611890a9bbf1bbee7f16663659695a2e0ad77a1f`.
- [x] Final release-preparation commit:
  `74264b1f8f9e20f72e8c02c262dcfa97252e2ed5 docs(v0.32): prepare release checklist`.
- [x] Verified the tracked worktree was clean at the final release-preparation
  commit.
- [x] Created immutable annotated tag `atlas-v0.32.0` targeting
  `74264b1f8f9e20f72e8c02c262dcfa97252e2ed5`.
- [x] Pushed branch `v032-agent-live-intake-admission` and annotated tag
  `atlas-v0.32.0` to `origin`; the remote branch and peeled tag target both
  resolve to `74264b1f8f9e20f72e8c02c262dcfa97252e2ed5`.
- [ ] Publish the GitHub release for `atlas-v0.32.0`.

## Atlas v0.31 P0 Live Delivery Send Boundary — selected

Atlas v0.31 is **Live Delivery Send Boundary**. P0 is the documentation-only
frozen [v1 contract](architecture/live-delivery-send-boundary-v1.md).

- [x] Inspect current `main` after annotated `atlas-v0.30.0`.
- [x] Freeze the exact operator create request, unchanged v0.27 Agent wire
  request/result/admission/acknowledgement, attempt, receipt, status, error,
  audit, and deterministic fingerprint contracts.
- [x] Freeze exact same-owner v0.20–v0.30 linkage and recomputation rules.
- [x] Preserve the v0.29/v0.30 maximum 30-second freshness/expiry window.
- [x] Freeze fixed HTTPS endpoint, mutual Core/Agent default-off registration,
  service authentication, CA and mode-0400 credential-reference boundaries.
- [x] Freeze permanent reservation-before-I/O, exact retry with zero I/O,
  terminal ambiguity, no resend, ownership, redaction, and audit rules.
- [x] Freeze the exact three-route Core API, single Agent POST, narrow Mission
  Control confirmation/read view, P0–P5 scope, threats, goldens, authority,
  later enablement, remaining blockers, and must-not-change contracts.
- [x] Keep P0 planning-only: no runtime model/service/store/route/UI change,
  production registration, transport, credential read, Agent call, install,
  execution, worker/workflow/dispatch, mutation, deployment, rollback, Home
  Assistant artifact, migration, tag, push, publication, or release action.
- [x] P1 — closed live-send models and pure validation.
- [x] P2 — default-off durable Core reservation service and attempt store.
- [x] P3 — default-off one-shot injected Core send boundary and terminal
  receipt/audit store.
- [x] P4 — keep Mission Control absent because no guarded Core live-send API
  or UI-facing read model exists; structural tests lock out clients, routes,
  navigation, mutation/retry/resend controls, sensitive rendering, prohibited
  authority labels, and Home Assistant exceptions.
- [x] P5 — isolation, no-replay, regressions, and release closure.

### P5 authority and isolation gates

- [x] Keep live send explicitly constructed, default-disabled, one-shot,
  synchronous, inert-evidence-only, permanently no-replay, and without an
  automatic retry path.
- [x] Keep credentials ephemeral: no credential value, Authorization header,
  secret, raw body, endpoint address, or internal path is persisted or
  disclosed through evidence or errors.
- [x] Keep every install, execute, deploy, mutate, worker, workflow, and replay
  authority field fixed false.
- [x] Keep live-send attempt/result/receipt/acknowledgement evidence isolated
  from Core authority subsystems, Agent consumers, and the execution worker.
- [x] Keep Core free of a production live-send route and Agent intake dormant,
  default-off, unregistered, and available only through explicit test
  construction.
- [x] Keep Mission Control free of a v0.31 client, type, UI, route, navigation,
  retry/resend/send-again, execute/install/deploy/rollback, workflow/worker, or
  mutation control.
- [x] Preserve capability parity and Home Assistant as blocked,
  non-installable, non-executable, and without a deployment artifact.
- [x] Add release-isolation tests and documentation only; add no runtime,
  migration, tag, push, release, publication, or deployment action.

### P5 observed validation evidence

- [x] P5 validation started from P4 commit
  `0e754a42ecc9dfd8e5aa702b15facd6aecfa5ed8`.
- [x] Both requested Atlas Core and Atlas Agent Ruff gates passed.
- [x] Focused Core release-isolation validation passed:
  `60 passed, 46 warnings in 9.58s`.
- [x] Focused Agent intake-closure validation passed:
  `10 passed, 15 warnings in 1.30s`.
- [x] Full Atlas Core validation passed:
  `3071 passed, 246 warnings in 193.85s (0:03:13)`.
- [x] Full Atlas Agent validation passed:
  `1020 passed, 22 warnings in 11.42s`.
- [x] Mission Control passed 84 test files and 545 tests, lint, and production
  build. Lint retained one pre-existing exhaustive-deps warning and no errors;
  build retained only the existing chunk-size advisory.
- [x] `git diff --check` passed.
- [x] P5 closure commit:
  `28a817daf3a1b4591c11cc4a294832c9ab5414b5 test(v0.31): close live delivery send`.
- [x] Full Atlas Core clean-environment release-preparation gate passed:
  `3071 passed, 246 warnings in 192.37s (0:03:12)`.
- [x] Exact reviewed implementation/validation SHA after P5 review:
  `28a817daf3a1b4591c11cc4a294832c9ab5414b5`.
- [x] Final release-preparation commit:
  `01e6fc40378f4f38f2559691768fc8880e69a96b docs(v0.31): prepare release checklist`.
- [x] Verified the tracked worktree was clean at the final release-preparation
  commit.
- [x] Created immutable annotated tag `atlas-v0.31.0` targeting
  `01e6fc40378f4f38f2559691768fc8880e69a96b`.
- [x] Pushed branch `v031-live-delivery-send-boundary` and annotated tag
  `atlas-v0.31.0` to `origin`; the remote branch and peeled tag target both
  resolve to `01e6fc40378f4f38f2559691768fc8880e69a96b`.
- [ ] Publish the GitHub release for `atlas-v0.31.0`.

## Atlas v0.30 P0–P5 Operator-Controlled Delivery Enablement — complete

Atlas v0.30 is **Operator-Controlled Delivery Enablement**. P0–P5 are complete
from the frozen [v1 contract](architecture/operator-controlled-delivery-enablement-v1.md).
P5 validation started from `1957d1774436055ebc6f87732e51101c555a9203`.

- [x] Inspect current `main` after released `atlas-v0.29.0`.
- [x] Freeze exact request, linkage, record, result, status, error, audit, and
  deterministic fingerprint contracts over v0.20–v0.29.
- [x] Freeze exact operator confirmation, authentication, ownership, authz,
  freshness/expiry, idempotency/no-replay, redaction, and audit rules.
- [x] Freeze default-off create/list/item-read API and two-step Mission Control
  evidence boundary for later phases.
- [x] Freeze P0–P5 scope, authority, threats, goldens, must-not-change
  contracts, later enablement, and remaining blockers.
- [x] Keep P0 planning-only: no model/runtime/store/route/UI implementation,
  Agent contact, transport, credential loading, dispatch, command, execution,
  mutation, installation, deployment, rollback, or Home Assistant artifact.
- [x] P1 — closed models and pure validation.
- [x] P2 — bounded append-only enablement evidence.
- [x] P3 — authenticated Core-local create/list/item-read API.
- [x] P4 — Mission Control two-step enablement evidence review.
- [x] P5 — isolation, no-replay, regressions, and release closure.

### P5 authority and isolation gates

- [x] Keep enablement durable-evidence-only, append-only, default-off,
  non-sending, non-executing, and permanently no-replay.
- [x] Keep Core limited to guarded create/list/item-read with no send, deliver,
  activate, install, execute, or deploy sibling route.
- [x] Keep live delivery, Agent, transport, credential, dispatch, worker,
  workflow, provider/repository/in-guest mutation, candidate execution,
  deployment, rollback, and replay-bypass consumers absent.
- [x] Keep Mission Control limited to enablement evidence reads and the single
  explicit v0.30 evidence-create mutation, without prohibited controls or
  navigation.
- [x] Preserve Home Assistant as blocked, non-installable, non-executable, and
  without a deployment artifact.

### P5 observed validation evidence

- [x] P5 validation closure commit:
  `ff9beae22c541334c27c6b0fe6c5c81fdc5680e2 test(v0.30): close delivery enablement`.
- [x] Both requested Core and Agent Ruff gates passed.
- [x] Focused Core release-isolation and route validation passed:
  `62 passed, 64 warnings in 9.97s`.
- [x] Full Atlas Core suite passed in a clean environment:
  `3046 passed, 238 warnings in 189.22s (0:03:09)`.
- [x] Full Agent regression validation passed:
  `1018 passed, 22 warnings in 10.72s`.
- [x] Mission Control passed 83 test files and 540 tests, lint, and production
  build. Lint retained the pre-existing `WorkflowShellPage.tsx`
  exhaustive-deps warning and no errors; build retained only the existing
  chunk-size advisory.
- [x] P5 changes only isolation/authority tests and the four release documents.
- [x] No migration, tag, push, release, deployment, or rollback was performed.

### Final release actions

- [x] Record the exact reviewed implementation/validation SHA after P5 review:
  `ff9beae22c541334c27c6b0fe6c5c81fdc5680e2`.
- [x] Final release-preparation commit:
  `9fe2f9e9b8d3e7332abaa013fb5893beb916f290 docs(v0.30): prepare release checklist`.
- [x] Confirmed the tracked worktree was clean at the final
  release-preparation commit.
- [x] Created the immutable annotated `atlas-v0.30.0` tag targeting
  `9fe2f9e9b8d3e7332abaa013fb5893beb916f290`.
- [x] Pushed the final release branch and `atlas-v0.30.0` tag to `origin`.
- [ ] Publish the Atlas v0.30 release as `atlas-v0.30.0`.

## Atlas v0.29 P0–P5 Controlled Delivery Activation Preflight — complete

Atlas v0.29 is **Controlled Delivery Activation Preflight**. P0–P5 are complete
from the frozen [v1 contract](architecture/delivery-activation-preflight-v1.md).
P5 validation started from `70faa4bb69206d332d037914464f22c66f651ce4`.

- [x] Inspect current `main` after the released `atlas-v0.28.0` boundary.
- [x] Freeze exact request/result/linkage schemas and deterministic fingerprint.
- [x] Freeze decision, lifecycle, freshness/expiry, ownership, authentication,
  authorization, idempotency/no-replay, redaction, and audit rules.
- [x] Freeze the default-disabled create/list/item-read API and non-authorizing
  Mission Control evidence boundary for later P phases.
- [x] Freeze P0–P5 scope, authority, threats, goldens, must-not-change
  contracts, later enablement, and remaining blockers.
- [x] Keep P0 planning-only: no runtime, route, store, UI, Agent contact,
  transport, secret, command, mutation, installation, deployment, rollback, or
  Home Assistant artifact change.
- [x] P1 — closed models, fingerprints, pure evaluation, and exact injected
  same-owner v0.20–v0.28 linkage validation.
- [x] P2 — bounded append-only preflight evidence with permanent reservations,
  exact retry/no-replay, quotas, corruption closure, and owned reads.
- [x] P3 — authenticated Core-local create/list/item-read API with narrow
  permissions, mutation gates, strict parsing, ownership, and redaction.
- [x] P4 — Mission Control strict client and non-authorizing status, linkage,
  expiry, fingerprint, audit, and fixed-false authority review.
- [x] P5 — isolation, no-replay, regressions, capability parity, Home Assistant
  blocking, and release closure.

### P5 authority and isolation gates

- [x] Keep the service/store durable-evidence-only, append-only,
  default-disabled/default-absent, non-activating, non-sending, and without an
  activation or downstream-consumption method.
- [x] Keep Core limited to guarded create/list/item-read and exclude every
  activate/send/deliver/execute/deploy sibling method or route.
- [x] Keep Agent calls, transport/route registration, credential loading,
  dispatch, worker/workflow/runtime, provider/repository/in-guest mutation,
  candidate execution, deployment, rollback, and replay-bypass consumers absent.
- [x] Keep Mission Control limited to strict reads and the explicit v0.29
  evidence-create call, with no prohibited control, navigation, or mutation.
- [x] Preserve Home Assistant as blocked, non-installable, non-executable, and
  without a deployment artifact.

### P5 observed validation evidence

- [x] P5 validation closure commit:
  `227e93f test(v0.29): close delivery activation preflight`.
- [x] P5 validation started from P4 commit `70faa4b`.
- [x] Both requested Core and Agent Ruff gates passed.
- [x] Focused Core release-isolation and route validation passed: 55 tests.
- [x] Full Atlas Core suite passed in a clean environment:
  `3022 passed, 206 warnings in 185.95s (0:03:05)`.
- [x] Full Agent regression validation passed: 1,018 tests.
- [x] Mission Control passed 530 tests, lint, and production build. Lint retained
  the pre-existing `WorkflowShellPage.tsx` exhaustive-deps warning and no errors;
  build retained only the existing chunk-size advisory.
- [x] `git diff --check` passed before the closure commit.
- [x] P5 changes only isolation/authority tests and the four release documents.
- [x] No migration, tag, push, release, deployment, or rollback was performed.

### Final release actions

- [x] Record the exact reviewed implementation/validation SHA after P5 review:
  `227e93f8e29cd308d2623e33f3d38a691ba0502f`.
- [x] Final release-preparation commit:
  `8eae3f4 docs(v0.29): prepare release checklist`.
- [x] Confirm the tracked worktree was clean at the final release-preparation
  commit.
- [x] Created the immutable annotated `atlas-v0.29.0` tag targeting
  `8eae3f4238da0eba2322b2297a97ec6aa77715bf`.
- [x] Pushed the final release branch and `atlas-v0.29.0` tag to `origin`.
- [ ] Publish the Atlas v0.29 release as `atlas-v0.29.0`.

## Atlas v0.28 P0–P5 Dormant Core-to-Agent Delivery Wiring — complete

Atlas v0.28 is **Dormant Core-to-Agent Delivery Wiring**. P0–P5 are complete
from the frozen [v1 contract](architecture/dormant-core-agent-delivery-wiring-v1.md).
P5 validation started from `701d6ba9e675816ec1ccca5d7260c5930f8da984`.

- [x] P1 — implement closed immutable Core models, strict validation, exact
  v0.20–v0.27 linkage, fixed-disabled configuration, and fingerprints.
- [x] P2 — implement the explicitly constructed no-send preparation client
  and bounded append-only store with owned reads and injected-response validation.
- [x] P3 — lock strict bounded configuration parsing and explicit inert
  construction without production settings, registration, secrets, or network.
- [x] P4 — lock Mission Control to no v0.28 type, API client, mutation, route,
  navigation, component, control, evidence rendering, or Home Assistant exception.
- [x] P5 — close production isolation, no-replay, authority, capability-parity,
  Agent-route dormancy, regression, and Home Assistant blocked gates.

### P5 authority and isolation gates

- [x] Keep the client/factory/store explicitly constructed, default-disabled,
  no-send, non-networking, non-executing, non-mutating, and non-authorizing.
- [x] Keep credential material loading, Authorization rendering, DNS, sockets,
  TLS, HTTP clients, network calls, and production Agent invocation absent.
- [x] Keep all production API, command, app/container/settings, workflow,
  worker, provider/repository/in-guest mutation, candidate execution,
  deployment, rollback, and replay-bypass consumers absent.
- [x] Keep the v0.27 Agent intake route dormant, explicitly constructed in
  tests only, and absent from production Agent registration and OpenAPI.
- [x] Keep Mission Control free of v0.28 UI/API/navigation/mutation/control
  surfaces and prohibited delivery/execution labels.
- [x] Preserve Home Assistant as blocked, non-installable, non-executable, and
  without a deployment artifact.

### P5 observed validation evidence

- [x] P5 validation closure commit:
  `5b53a48 test(v0.28): close dormant delivery wiring`.
- [x] Both requested Core and Agent `rc1-python-ruff-gate` commands passed.
- [x] Focused Core release-isolation and dormant-wiring validation passed:
  92 tests.
- [x] Full Atlas Core suite passed in a clean environment:
  `3000 passed, 186 warnings in 180.28s (0:03:00)`.
- [x] Full Agent regression validation passed: 1,016 tests.
- [x] Mission Control passed 522 tests, lint, and production build. Lint retained
  the pre-existing `WorkflowShellPage.tsx` exhaustive-deps warning and reported
  no errors; the build retained only its existing chunk-size advisory.
- [x] `git diff --check` passed before the closure commit.
- [x] P5 changes only isolation/authority tests and release documentation.
- [x] No migration, tag, push, release, deployment, or rollback was performed.

### Final release actions

- [x] Record the exact reviewed implementation/validation SHA after P5 review:
  `5b53a48ab2c27e19c66044c633e8d6dae25e471e`.
- [x] Final release-preparation commit:
  `c95d580 docs(v0.28): prepare release checklist`.
- [x] The tracked worktree was clean at the final release-preparation commit.
- [x] Created the immutable annotated `atlas-v0.28.0` tag targeting
  `c95d580b3cdc9d4cb52d2cfe3e7b764506c2ae9c`.
- [x] Pushed the final release branch and `atlas-v0.28.0` tag to `origin`.
- [ ] Publish the Atlas v0.28 release as `atlas-v0.28.0`.

## Atlas v0.27 P0–P5 Real Agent Intake Boundary — complete

Atlas v0.27 is **Real Agent Intake Boundary**. P0–P5 are complete from the
frozen [v1 contract](architecture/real-agent-intake-boundary-v1.md). P5
validation started from `2710b66`.

- [x] P1 — implement closed immutable models, strict validation, exact
  v0.20–v0.26 linkage, server-owned time, and deterministic fingerprints.
- [x] P2 — implement the explicitly constructed default-disabled evidence
  service and bounded append-only store with owned reads and no authority.
- [x] P3 — lock out every production HTTP/OpenAPI, command, registration,
  setting, Core consumer, and live-listener surface.
- [x] P4 — add the dormant route factory only for explicitly constructed test
  apps and exercise its exact authenticated bounded POST contract.
- [x] P5 — close isolation, no-replay, concurrency/ambiguity, authority,
  capability-parity, Mission Control absence, and Home Assistant blocked gates.

### P5 authority and isolation gates

- [x] Keep the service and route explicitly constructed, default-disabled,
  evidence-only, non-executing, non-mutating, and non-authorizing.
- [x] Keep the test-only POST factory absent from production Agent app,
  container, settings, OpenAPI, CLI, credentials, and deployment wiring.
- [x] Keep production Core delivery, transport/listener, worker, workflow,
  provider/repository/in-guest mutation, candidate execution, deployment,
  rollback, and replay-bypass consumers absent.
- [x] Lock authentication/authorization, HTTPS, JSON, header/body bounds,
  duplicate-key/unknown-field rejection, idempotency/no-replay, ownership,
  linkage/freshness, redaction, and fixed-false authority behavior.
- [x] Expose no install/run/execute/deploy/dispatch/deliver/start-workflow/
  runtime sibling route or command.
- [x] Lock Mission Control to no v0.27 client, mutation, route, navigation,
  control, evidence rendering, or prohibited action label.
- [x] Preserve Home Assistant as blocked, non-installable, non-executable, and
  without a deployment artifact.

### P5 observed validation evidence

- [x] P5 validation closure commit:
  `2746814 test(v0.27): close real agent intake boundary`.
- [x] Both requested Core and Agent `rc1-python-ruff-gate` commands passed.
- [x] Focused Core release-isolation validation passed: 41 tests.
- [x] Full Atlas Core suite passed in a clean environment:
  `2949 passed, 176 warnings in 175.35s (0:02:55)`.
- [x] Full Agent regression validation passed: 1,016 tests.
- [x] Mission Control passed 517 tests, lint, and production build. Lint
  retained the pre-existing `WorkflowShellPage.tsx` exhaustive-deps warning
  and reported no errors; the build retained only its existing chunk-size
  advisory.
- [x] `git diff --check` passed before the closure commit.
- [x] P5 changes only isolation/authority tests and release documentation.
- [x] No migration, tag, push, release, deployment, or rollback was performed.

### Final release actions

- [x] Record the exact reviewed implementation/validation SHA after P5 review:
  `274681422eb2b3ae392c3283d15c3d96f760c0cb`.
- [x] Final release-preparation commit:
  `d0a36dd docs(v0.27): prepare release checklist`.
- [x] The tracked worktree was clean at the final release-preparation commit.
- [x] Created the immutable annotated `atlas-v0.27.0` tag targeting
  `d0a36dd41eeec7a04acf500a3c21cfd98b882d4e`.
- [x] Pushed the final release branch and `atlas-v0.27.0` tag to `origin`.
- [ ] Publish the Atlas v0.27 release as `atlas-v0.27.0`.

## Atlas v0.26 P0–P5 Simulated Handoff Delivery — complete

Atlas v0.26 is **Simulated Core-to-Agent Handoff Delivery**. P0–P5 are complete
from the frozen [v1 contract](architecture/simulated-handoff-delivery-v1.md).
P5 validation started from `696c98e773823e054ce86ce11f64d4ccbd57fba9`.

- [x] P1 — implement closed immutable Core and Agent models, strict parsing,
  canonical fingerprints, lifecycle derivation, and hostile-input bounds.
- [x] P2 — implement bounded append-only Core attempt and acknowledgement-copy
  stores plus an explicit default-disabled coordinator with an injected port.
- [x] P3 — implement the explicit default-disabled Agent acknowledgement
  adapter, reuse the unchanged v0.25 simulation path, and preserve one closed
  acknowledgement without registration or transport.
- [x] P4 — exercise synthetic same-owner v0.20–v0.26 delivery goldens entirely
  in process and lock Mission Control to no v0.26 presentation surface.
- [x] P5 — close isolation, regression, authority, no-replay, owned-readback,
  capability-parity, and Home Assistant blocked-golden gates.

### P5 authority and isolation gates

- [x] Scan production Core and Agent modules outside the isolated packages;
  no v0.26 evidence consumer, live Agent invocation, transport delivery,
  candidate execution, or replay bypass exists.
- [x] Keep both services explicitly constructed, default-disabled,
  simulation-only, in-process, and fixed false for delivery/receipt,
  admission, execution, worker, mutation, and replay authority.
- [x] Keep Core and Agent HTTP/OpenAPI, CLI/shell, app/container registration,
  settings enablement, worker, workflow, provider, repository, in-guest,
  deployment, and rollback surfaces absent.
- [x] Constrain Core and Agent readback to direct operator-owned store calls;
  expose no public list, route, API client, or UI surface.
- [x] Lock Mission Control to no v0.26 type, API client, mutation, component,
  page, route, navigation, control, prohibited action label, or evidence
  rendering.
- [x] Preserve `install-container` as unsupported and outside executable Agent
  intent sets.
- [x] Preserve Home Assistant as blocked, non-installable, and non-executable;
  no `.yaml` or `.yml` deployment artifact exists.
- [x] Add no runtime behavior, authority, migration, tag, push, release,
  deployment, or rollback.

### P5 observed validation evidence

- [x] P5 validation closure commit:
  `33b976d test(v0.26): close simulated handoff delivery`.
- [x] Both requested Core and Agent `rc1-python-ruff-gate` commands passed.
- [x] Focused Core release-isolation and v0.26 closure validation passed:
  43 tests.
- [x] Full Atlas Core suite passed in a clean environment:
  `2946 passed, 176 warnings in 176.13s (0:02:56)`.
- [x] Full Agent regression validation passed: 983 tests.
- [x] Mission Control passed 513 tests, lint, and production build. Lint
  retained the pre-existing `WorkflowShellPage.tsx` exhaustive-deps warning
  and reported no errors; the build retained only its existing chunk-size
  advisory.
- [x] `git diff --check` passed before the closure commit.
- [x] No migration, tag, push, release, deployment, or rollback was performed.

### Final release actions

- [x] Record the exact reviewed implementation/validation SHA after P5 review:
  `33b976d0e1f17ba8bc4ea831d13ae17cc8eaccb6`.
- [ ] The tracked worktree is clean at the final release commit.
- [ ] Create the immutable annotated `atlas-v0.26.0` tag.
- [ ] Push the final release branch and `atlas-v0.26.0` tag to `origin`.
- [ ] Publish the Atlas v0.26 release as `atlas-v0.26.0`.

## Atlas v0.25 P0–P5 Agent Intake Simulation — complete

Atlas v0.25 is **Agent Intake Simulation**. P0–P5 are complete from the frozen
[v1 contract](architecture/agent-intake-simulation-v1.md). P5 validation
started from `978bbc4110ca108621d3fe794b6969d750932c19`.

- [x] P1 — implement closed immutable models, strict parsing, canonical
  fingerprints, lifecycle derivation, and hostile-input bounds without I/O.
- [x] P2 — implement pure injected validation of the exact owner-bound v0.24
  envelope with fixed-false authority and sanitized closed errors.
- [x] P3 — implement the isolated bounded append-only evidence store, atomic
  identity reservations, exact idempotency/no-replay, quotas, restart
  durability, owned reads, and fail-closed corruption behavior.
- [x] P4 — lock Mission Control to no v0.25 presentation because the frozen
  contract exposes no UI-facing read model.
- [x] P5 — close release isolation, regression, authority, no-replay,
  owned-readback, capability-parity, and Home Assistant blocked-golden gates.
- [x] Prove there is no v0.25 Mission Control API client, hook, type, component,
  page, route, navigation, or mutation call.
- [x] Prove there is no install/run/execute/deploy/dispatch/deliver/send-to-
  Agent/start-workflow/rollback control or simulated-intake action label.
- [x] Prove Mission Control cannot render v0.25 simulation evidence, raw
  provider payloads, credentials, commands, logs, internal paths, or addresses.
- [x] Lock Agent OpenAPI to zero v0.25 paths, operations, tags, or schemas.
- [x] Lock out CLI/shell commands, application-container registration, and
  settings-driven production enablement.
- [x] Scan Agent production modules to prove no v0.25 Core-to-Agent consumer,
  live delivery, worker, workflow, provider, repository, runtime, route, or
  registration exists.
- [x] Prove the isolated package imports no Docker/Podman, shell/process,
  target/provider/Core network, worker, workflow, route, or mutation adapter.
- [x] Confine filesystem access to the explicitly constructed simulation
  evidence store; keep readback an owner-scoped in-process store operation.
- [x] Preserve `install-container` as unsupported and default-disabled, with
  no installation, deployment, rollback, Home Assistant artifact, tag, push,
  publication, or release action.
- [x] Keep Home Assistant blocked, non-installable, and non-executable; confirm
  `compose/home-assistant.yaml` remains absent.

### P5 authority and isolation gates

- [x] Scan all production Core modules and every Agent module outside the
  isolated package; no v0.25 record consumer, Core-to-Agent delivery bridge,
  candidate execution, replay bypass, or authority expansion exists.
- [x] Keep the service default-disabled and simulation-only with delivery,
  admission, execution, worker, mutation, and replay authority fixed false.
- [x] Keep Agent HTTP/OpenAPI, CLI/shell commands, app/container registration,
  settings enablement, worker, workflow, provider, repository, in-guest,
  deployment, and rollback surfaces absent.
- [x] Constrain readback to direct operator-owned `get` and lifecycle calls on
  the explicitly constructed in-process store; no public list/API/UI surface
  exists.
- [x] Lock Mission Control to no v0.25 API client, mutation, component, page,
  route, navigation, control, prohibited action label, or evidence rendering.
- [x] Preserve `install-container` as unsupported and outside executable Agent
  intent sets.
- [x] Preserve the Home Assistant blocked golden as non-installable and
  non-executable; no `.yaml` or `.yml` deployment artifact exists.
- [x] Add no runtime behavior, API route, command, registration, authority,
  migration, tag, push, release, or deployment.

P4 validation passed 509 Mission Control tests, Mission Control lint and build,
the Agent Ruff gate, and 968 Agent tests. Mission Control lint retained one
pre-existing `WorkflowShellPage.tsx` exhaustive-deps warning; there were no
lint errors. `git diff --check` passed. No runtime surface, tag, push, release,
or deployment was added or performed.

### P5 observed validation evidence

- [x] P5 validation closure commit:
  `407669b test(v0.25): close agent intake simulation`.
- [x] Both requested Core and Agent `rc1-python-ruff-gate` commands passed.
- [x] Focused Core release-isolation validation passed: 35 tests.
- [x] Full Atlas Core suite passed in a clean environment:
  `2931 passed, 171 warnings in 177.48s (0:02:57)`.
- [x] Full Agent regression validation passed: 969 tests.
- [x] Mission Control passed 509 tests, lint, and production build. Lint
  retained the pre-existing `WorkflowShellPage.tsx` exhaustive-deps warning
  and reported no errors; the build retained only its existing chunk-size
  advisory.
- [x] `git diff --check` passed before the closure commit.
- [x] No migration, tag, push, release, deployment, or rollback was performed.

### Final release actions

- [x] Record the exact reviewed implementation/validation SHA after P5 review:
  `407669b6d82572e8255e4b7b4f847abf5b04a3a1`.
- [x] Final release-preparation commit:
  `d4d7424 docs(v0.25): prepare release checklist`.
- [x] The tracked worktree was clean at the final release commit.
- [x] Created the immutable annotated `atlas-v0.25.0` tag at
  `d4d7424b86af1510f200d92f628cf80b779638f9` (`d4d7424`).
- [x] Pushed the final release branch and `atlas-v0.25.0` tag to `origin`.
- [ ] Publish the Atlas v0.25 release as `atlas-v0.25.0`.

## Atlas v0.24 P0–P5 release validation and closure — complete

Atlas v0.24 is **Installation Dispatch Handoff**. P0–P5 are complete. P5
validation started from `c50c09c850451f68a4b267d99d3e95b8a6197a52`.

- [x] Start from current `main` after v0.23.0 and freeze the documentation-only
  [v1 planning contract](architecture/installation-dispatch-handoff-v1.md).
- [x] Define the exact closed Core create/envelope and contract-only Agent
  intake/admission schemas, domain-separated fingerprints, bounds, and closed
  status vocabulary.
- [x] Bind exact same-owner v0.20 candidate, v0.21 approval, v0.22 request/
  validation/evidence, and v0.23 execution-request IDs and fingerprints.
- [x] Freeze `prepared`/terminal `expired`, 60-second maximum lifetime,
  one-envelope-per-v0.23-request reservation, exact retry, and fail-closed
  ambiguity/no-replay rules.
- [x] Define operator ownership, redaction, audit evidence, closed errors,
  default-disabled posture, preparation-only API/UI boundaries, P0–P5 scope,
  must-not-change contracts, threats, and goldens.
- [x] Confirm the exact authority is local resolution, pure validation, and
  append-only preparation evidence—not delivery, admission, or execution.
- [x] Keep Home Assistant blocked and add no deployment artifact or exception.
- [x] Confirm P0 changes planning documentation only: no runtime model, test,
  route, store, UI, Agent/worker invocation, network delivery, Docker/Podman/
  shell/process execution, provider/repository/guest mutation, workflow,
  installation, deployment, rollback, tag, push, publication, or release.
- [x] P1 — implement closed models and pure assembly/admission validation.
- [x] P2 — implement the bounded append-only Core handoff store.
- [x] P3 — implement the authenticated preparation-only Core API.
- [x] P4 — implement Mission Control handoff evidence review.
- [x] P5 — close isolation, no-replay, goldens, regressions, and release gates.

### P0 authority and blocked-work gates

- [x] `prepared handoff != delivered request != Agent admission != execution`.
- [x] Every envelope and admission authority field is fixed false; exact replay
  performs no revalidation, time extension, delivery, or work.
- [x] Agent intake/admission is schema-only with no listener, route, transport,
  application wiring, persistence, or runtime consumer.
- [x] Trusted transport, independent execution approval, live intake, atomic
  consume/no-redelivery, execution-time proof, worker/runtime execution,
  recovery, side-effect audit, deployment, and rollback remain blocked.

### P5 authority and isolation gates

- [x] The service constructor and configuration default remain disabled;
  envelopes are record-only and both Core and contract-only Agent authority
  field sets remain schema-fixed false.
- [x] Every Core and Agent production Python module is scanned: only the
  isolated handoff contract/store/service, guarded route, router, and
  application wiring recognize v0.24 records. No live Agent invocation or
  HTTP call, delivery, worker, workflow, provider/repository/in-guest mutation,
  candidate execution, deployment, rollback, or replay-bypass consumer exists.
- [x] Core OpenAPI exposes only guarded POST/list/item-read under
  `/api/v1/installation/dispatch-handoffs`; it exposes no install, execute,
  dispatch, deliver, deploy, send-to-Agent, start-workflow, rollback, or replay
  route.
- [x] Mission Control confines endpoint calls to the dedicated adapter's two
  guarded reads and one explicit record-only create. The view has no prohibited
  authority control, navigation, label, Agent bridge, or other mutation.
- [x] Home Assistant remains blocked before candidate preservation and by the
  v0.22 artifact policy; no deployment artifact was added.

### P5 observed validation evidence

- [x] P5 validation closure commit:
  `7f909f8 test(v0.24): close installation dispatch handoff`.
- [x] Both requested `rc1-python-ruff-gate` commands passed.
- [x] Focused Core release-isolation, route, and service validation passed:
  237 tests. It ran from `services/atlas-core`, the expected working directory;
  host access was needed only for the existing provider-secret permission
  check.
- [x] Full Atlas Core suite passed in a clean environment:
  `2929 passed, 171 warnings in 172.03s (0:02:52)`.
- [x] Full Agent validation passed: 948 tests, using isolated `/tmp` XDG state
  and host execution for the existing local integration-test boundary.
- [x] Mission Control passed 506 tests, lint with zero errors (one pre-existing
  hook-dependency warning), and production build (with the existing chunk-size
  advisory).
- [x] `git diff --check` passed.
- [x] P5 changes only release-isolation/authority tests and these release
  documents. No runtime behavior, migration, tag, push, release, installation,
  execution, deployment, rollback, or external mutation was added or run.

### Final release actions

- [x] Record the exact reviewed implementation/validation SHA after P5 review:
  `7f909f8bf57647315e505819fee88d12eb62f869`.
- [x] Final release-preparation commit:
  `a15ab39 docs(v0.24): prepare release checklist`.
- [x] The tracked worktree was clean at the final release commit.
- [x] Created the immutable annotated `atlas-v0.24.0` tag at
  `a15ab39ee53a2af2fae8711d1a74ab508b378dc6` (`a15ab39`).
- [x] Pushed the final release branch and `atlas-v0.24.0` tag to `origin`.
- [ ] Publish the Atlas v0.24 release as `atlas-v0.24.0`.

## Atlas v0.23 P0–P5 release validation and closure — complete

Atlas v0.23 is **Installation Execution Request Boundary**. P0–P5 are complete.
P5 validation started from `b6148294039c295b9e781ac13079403c4deee69b`.

- [x] Start from current `main` after v0.22.0 and freeze the documentation-only
  [v1 planning contract](architecture/installation-execution-request-v1.md).
- [x] Define the exact closed create and durable record schemas, all mandatory
  v0.20/v0.21/v0.22 IDs and fingerprints, same-owner linkage, and Core
  domain-separated fingerprint.
- [x] Freeze `recorded`/terminal `expired` lifecycle, exact 60-second evidence
  intake freshness, five-minute maximum record lifetime, and fail-closed clock
  behavior.
- [x] Freeze atomic reservation of the idempotency key, approval intent, Agent
  request ID/fingerprint, validation fingerprint, and Core fingerprint; exact
  replay returns the original without revalidation or work.
- [x] Define operator-scoped append-only ownership, quotas, corruption and
  ambiguity behavior, redaction, closed errors, audit evidence, and unchanged
  backup-v3 posture.
- [x] Limit future API scope to authenticated create/list/item-read and UI scope
  to explicit non-executing submission/review with operator-submitted evidence
  provenance and no authority controls.
- [x] Keep the feature default-disabled through release closure and keep
  `install-container` unsupported with no execution consumer or enable switch.
- [x] Preserve all v0.16–v0.22 and existing approval/audit/workflow/dispatch/
  execution/no-replay/capability contracts unchanged.
- [x] Confirm P0 adds planning documentation only: no runtime, test, route,
  store, UI, Agent/worker invocation, Core-to-Agent dispatch, process/shell/
  Docker/Podman command, provider/repository/guest mutation, workflow, install,
  deployment, rollback, migration, tag, push, publication, or release.
- [x] P1 — implement closed Core models and pure validation.
- [x] P2 — implement the bounded append-only request store.
- [x] P3 — implement the authenticated record-only Core API.
- [x] P4 — implement Mission Control evidence submission and review.
- [x] P5 — close isolation, no-replay, goldens, regressions, and release gates.

### P0 authority and golden gates

- [x] `recorded request != execution approval != dispatch != execution`; all
  five authority fields are fixed false in every lifecycle state.
- [x] Core performs only local owned-record reads, pure validation, and a
  future append; v0.23 never calls Agent or any mutation/authority subsystem.
- [x] V0.22 evidence is explicitly operator-submitted and fingerprint-checked,
  not promoted into trusted Agent attestation, liveness, or runtime readiness.
- [x] One approval intent can create at most one request. Expiry, restart,
  timeout, lost response, or source deletion cannot open a replay path.
- [x] Home Assistant remains blocked before v0.20 and by v0.22 artifact policy;
  no deployment artifact or golden exception is added.
- [x] What remains blocked is explicit: independent execution approval,
  trusted Agent transport, execution-time proof, consumption/dispatch, worker/
  runtime, recovery/audit, image acquisition, deployment, and rollback.

### P5 authority and isolation gates

- [x] The service constructor and configuration default remain disabled;
  durable records are `record-only`, and all five authority fields remain
  schema-fixed false.
- [x] Every Core and Agent production Python module is scanned: only the
  v0.23 contract/store/service, guarded route, configuration, and application
  wiring recognize execution-request records. No invocation, dispatch,
  worker, workflow, provider/repository/in-guest mutation, deployment,
  rollback, candidate execution, or replay-bypass consumer exists.
- [x] Core OpenAPI exposes only guarded POST/list/item-read under
  `/api/v1/installation/execution-requests`; it exposes no install, execute,
  deploy, dispatch, send-to-Agent, start-workflow, or rollback sibling.
- [x] Mission Control confines endpoint calls to the dedicated adapter's two
  guarded reads and one explicit record-only create. The view has no
  prohibited control, label, navigation, Agent bridge, or other mutation.
- [x] Home Assistant remains blocked before candidate preservation and by the
  v0.22 artifact policy; no deployment artifact was added.

### P5 observed validation evidence

- [x] P5 validation closure commit:
  `c387d0d test(v0.23): close installation execution request`.
- [x] Gate-alignment commit included in the reviewed release branch:
  `c47ee20 test(v0.23): align selection corruption fail-closed gate`.
- [x] Both requested `rc1-python-ruff-gate` commands passed.
- [x] Focused Core release-isolation, route, and service validation passed:
  233 tests. The suite was run from `services/atlas-core`, its expected
  working directory, because one pre-existing structural test uses an
  `app/...` relative path; host access was needed only for the existing
  provider-secret permission check.
- [x] Full Atlas Core suite passed in a clean environment: `2,907 passed`.
- [x] Full Agent validation passed: 948 tests, using the established isolated
  `/tmp` XDG state directory because the sandboxed default state directory is
  read-only.
- [x] Mission Control passed 499 tests, lint with zero errors (one pre-existing
  hook-dependency warning), and production build (with the existing chunk-size
  advisory).
- [x] P5 changes only release-isolation/authority tests and these release
  documents. No runtime behavior, migration, tag, push, release, installation,
  execution, deployment, rollback, or external mutation was added or run.

### Final release actions

- [x] Record the exact reviewed implementation/validation SHA after full
  clean-environment review:
  `c47ee204b72563dc471ef06c589b820a3b87d415`.
- [x] Final release-preparation commit:
  `2e69785 docs(v0.23): prepare release checklist`.
- [x] The tracked worktree was clean at the final release commit.
- [x] Created the immutable annotated `atlas-v0.23.0` tag at
  `2e69785049ce863d36e1007bf67ae8da69ca1f86` (`2e69785`).
- [x] Pushed the final release branch and `atlas-v0.23.0` tag to `origin`.
- [ ] Publish the Atlas v0.23 release as `atlas-v0.23.0`.

## Atlas v0.22 P0–P5 release validation and closure — complete

Atlas v0.22 is **Agent Install-Container Contract**. P0–P5 are complete. P5
validation started from `1a399533a2e320fe7f8ee4f4096209316bb40e32`.

- [x] Freeze the exact closed request/result schemas, canonical fingerprinting,
  five-minute freshness, size bounds, and duplicate/unknown-field rejection in
  the normative [v1 contract](architecture/agent-install-container-contract-v1.md).
- [x] Limit the subject to one exact existing Proxmox QEMU incarnation and
  require the complete same-owner v0.20 candidate-envelope and v0.21
  approval-intent ID/fingerprint chain.
- [x] Limit the artifact to one normalized digest-pinned OCI container under
  rootless Podman with network `none`, no host mounts/devices/ports/secrets/
  environment/commands/privilege/capabilities/restart, read-only rootfs, and
  one bounded `/tmp` tmpfs.
- [x] Freeze deterministic `valid_but_unsupported`/`rejected` validation,
  fixed-false authority fields, ordered reason codes, redaction, idempotency,
  no-replay semantics, and non-authorizing audit evidence.
- [x] Record exact threats: proof substitution, confused deputy/destination
  replacement, artifact equivocation, escape, filesystem/network abuse,
  exhaustion, ambiguous replay, validation-as-authority, leakage, and
  accidental activation.
- [x] Preserve all v0.16–v0.21 contracts and existing execution/approval/audit/
  workflow/dispatch/no-replay boundaries unchanged.
- [x] Keep `install-container` unsupported and default-disabled with no Core
  execution route, Core-to-Agent dispatch, worker/provider/repository/guest/
  runtime invocation, mutation, installation, or Home Assistant deployment.
- [x] Confirm P0 changes planning documentation only and performs no tag, push,
  publication, release, or deployment.
- [x] P1 — implement closed models and pure canonical fingerprints.
- [x] P2 — implement pure proof-linkage and boundary validation.
- [x] P3 — implement the internal dry-run evidence service with no route.
- [x] P4 — add unsupported/default-disabled Agent diagnostics only.
- [x] P5 — close isolation, refusal, Home Assistant golden, and regressions.

### P5 authority and isolation gates

- [x] No Core production path, route, caller, or Core-to-Agent bridge consumes
  the v0.22 validation or audit-evidence record.
- [x] No Agent dispatch, worker, workflow, provider/repository/in-guest
  mutation, deployment, rollback, candidate execution, or no-replay path
  imports or recognizes the v0.22 record.
- [x] The isolated validator has no runtime, process, socket, container,
  persistence, repository, execution, workflow, route, or application-
  container dependency.
- [x] Agent exposes only the closed static diagnostic: validation-only,
  unsupported, default-disabled, non-executing, non-dispatching, non-mutating,
  non-replayable, and without an install/execute/deploy command or route.
- [x] Mission Control uses only the existing Agent-info GET and contains no
  install/execute/deploy/dispatch/send-to-Agent/start-workflow control,
  authority navigation, or install-container mutation call.
- [x] Home Assistant remains blocked, non-preservable, non-approvable,
  non-installable, and non-executable; its deployment artifact remains absent.
- [x] Backup v3 remains unchanged; v0.22 validation records remain excluded.

### P5 observed validation evidence

- [x] P5 validation closure commit:
  `9adaf93 test(v0.22): close agent install-container validation`.
- [x] Core and Agent baseline-aware Ruff gates passed.
- [x] Focused Core release-isolation suite passed: `26 passed, 5 warnings`.
- [x] Full Atlas Core suite passed in a clean environment:
  `2885 passed, 121 warnings in 169.76s (0:02:49)`.
- [x] Full Atlas Agent suite passed: `948 passed, 4 warnings in 6.98s`.
- [x] Mission Control passed 67 files / 492 tests; lint completed with one
  pre-existing `WorkflowShellPage.tsx` hook-dependency warning and no errors;
  production build completed successfully.
- [x] `git diff --check` passed; P5 adds tests and release documentation only.
- [x] No migration, tag, push, publication, deployment, or release action
  occurred.

### Final release actions

- [x] Record the exact reviewed implementation/validation SHA after P5 review:
  `9adaf937140ed2f05399bcdb44682ddef8ed677e`.
- [x] Final release-preparation commit:
  `3ecf91d docs(v0.22): prepare release checklist`.
- [x] The tracked worktree was clean at the final release commit.
- [x] Created the immutable annotated `atlas-v0.22.0` tag at
  `3ecf91dc4b501d6ac3bbfbc4ab99bd8dba283169` (`3ecf91d`).
- [x] Pushed the final release branch and `atlas-v0.22.0` tag to `origin`.
- [x] Published the Atlas v0.22 release as `atlas-v0.22.0`.

## Atlas v0.21 P0–P5 release closure

Atlas v0.21 is **Installation Approval Intent**. P0–P5 are complete. P5
validation started from `1d84187aea2f187e9b408324ecc6c31bc9882499`.

### P0 authority and scope gates

- [x] The approved subject is exactly the v0.20 candidate-record ID, envelope
  fingerprint, admission fingerprint, and embedded candidate-record
  fingerprint; aliases and partial identities are forbidden.
- [x] Creation is an explicit authenticated owner action over a complete active
  v0.20 record and binds one fixed statement plus server-owned recording time.
- [x] The intent is immutable append-only evidence, not execution
  authorization, and has no state machine, runtime deletion, consumer,
  conversion, event, queue, workflow, dispatch, or replay path.
- [x] V0.16–v0.20 contracts, Home Assistant golden, five false authority fields,
  v0.20 deletion, existing approvals, no-replay, capability parity,
  default-disabled worker, and backup v3 exclusion remain unchanged.
- [x] P0 changes only `ROADMAP.md`, `CHANGELOG.md`, this checklist, and the
  normative v0.21 architecture contract. It adds no runtime behavior or tests.

### P1–P5 authority and release gates

- [x] Complete closed-contract, store, API, Mission Control, isolation, and
  full regression acceptance defined in the normative v0.21 contract.
- [x] Prove no Core or Agent authority/mutation consumer recognizes a v0.21
  schema, intent ID, statement, or fingerprint.
- [x] Lock OpenAPI to create/list/item-read only and Mission Control to exact-
  record confirmation and evidence review only.
- [x] Reconfirm Home Assistant cannot cross the v0.19 admission or v0.20
  preservation boundary and therefore cannot be approved or executed.
- [x] Preserve approval, execution, dispatch, Agent install-container, worker,
  provider/repository/in-guest mutation, workflow, deployment, rollback,
  eligibility, and no-replay boundaries with no v0.21 consumer.
- [x] Keep backup v3 unchanged. The independent approval-intent database is
  excluded and requires explicit operator maintenance with Atlas Core stopped;
  older releases do not consume it.

### P5 observed validation evidence

- [x] P5 validation closure commit:
  `de5f751 test(v0.21): close installation approval intent validation`.
- [x] Stabilization commit:
  `ea58c31 test(v0.21): stabilize image grounding consumer check`.
- [x] Core and Agent baseline-aware Ruff gates passed.
- [x] Focused approval-intent, route, and release-isolation suite passed:
  `38 passed, 25 warnings in 6.76s`.
- [x] Full Atlas Core suite passed in a clean environment:
  `2882 passed, 121 warnings in 168.98s (0:02:48)`.
- [x] Full Atlas Agent suite passed outside the managed sandbox (required for
  TestClient threading), using a temporary `XDG_STATE_HOME`:
  `912 passed, 1 warning in 6.84s`.
- [x] Mission Control passed 65 files / 485 tests; lint completed with one
  pre-existing `WorkflowShellPage.tsx` hook-dependency warning and no errors;
  production build completed successfully.
- [x] `git diff --check` passed; P5 adds tests and release documentation only.
- [x] No migration, tag, push, publication, deployment, or release action
  occurred.

### Final release actions

- [x] Record the exact reviewed implementation/validation SHA after P5 review:
  `ea58c31927dcb685f66f542f5ec6cdc3d5603ca0`.
- [x] Final release-preparation commit:
  `1ca7081 docs(v0.21): prepare release checklist`.
- [x] The tracked worktree was clean at the final release commit.
- [x] Created the immutable annotated `atlas-v0.21.0` tag at
  `1ca708198bb0098a64ed442dd50c4ad9171d69e5` (`1ca7081`).
- [x] Pushed the final release branch and `atlas-v0.21.0` tag to `origin`.
- [x] Published the Atlas v0.21 release as `atlas-v0.21.0`.

## Atlas v0.20 P0–P5 release closure

Atlas v0.20 is **Installation Candidate Record Lifecycle**. P0–P5 are
complete. P5 validation started from `e198f4870f0b2517c1dda3fcc5301aa7745f7473`.

### Authority, isolation, and golden gates

- [x] Durable records retain the exact v0.19 candidate and all five false
  authority fields; `active` is only a passive unexpired-facts projection.
- [x] No Core or Agent approval, execution, dispatch, install-container,
  worker, provider, repository, in-guest, workflow, deployment, rollback, or
  no-replay path consumes a v0.20 envelope.
- [x] Integrated OpenAPI exposes only list/preserve and item get/delete under
  `/api/v1/installation/candidate-records`; it exposes no approval, execution,
  dispatch, install, deployment, or rollback route.
- [x] Mission Control contains only preserve, review, and delete controls and
  only list/get/preserve/delete calls for the v0.20 surface, with no authority
  navigation or mutation call.
- [x] Home Assistant remains v0.19 `not_admitted` with no candidate and is
  rejected by the v0.20 preservation boundary.
- [x] Backup v3 remains closed and intentionally excludes
  `installation_candidate_records.db`; explicit operator maintenance is
  required and older releases cannot consume the store.

### P5 observed validation evidence

- [x] Atlas Core and Atlas Agent baseline-aware Ruff gates passed.
- [x] Focused lifecycle/admission/capability/route/release-isolation suite
  passed.
- [x] Full Core clean-environment result after fixture update:
  `2859 passed, 104 warnings in 162.46s (0:02:42)`.
- [x] P5 needed the follow-up fixture commit:
  `8fbba9f test(v0.20): update lifespan settings fixture`.
- [x] Full Atlas Agent suite passed.
- [x] Mission Control tests, lint, and production build passed.
- [x] `git diff --check` passed; closure contains tests and documentation only.
- [x] No migration, tag, push, publication, deployment, or release action
  occurred.

### Final release actions

- [ ] Record the exact reviewed implementation/validation SHA after P5 review.
- [ ] Confirm the tracked worktree is clean at the final release commit.
- [ ] Create and push an immutable v0.20 release tag through the separate
  authorized release procedure.
- [ ] Publish and deploy only through separate explicit authorization.

## Atlas v0.19 P0–P5 release closure

Atlas v0.19 is **Installation Candidate Admission**. P0–P5 are complete; the
reviewed implementation and validation head after P5 review is
`c23f4c405b4c7261c59a6cff36bee145527c1b51`.

### Authority, isolation, and golden gates

- [x] V0.16 InstallationPlan, v0.17 prospective destination, v0.18 capability
  assessment, and v0.19 candidate admission remain non-authorizing.
- [x] No ExecutionCandidate creation, approval, workflow, dispatch, Agent,
  worker, provider, repository, deployment, or in-guest mutation production
  path consumes a v0.19 admission or candidate record.
- [x] Integrated OpenAPI exposes only
  `GET /api/v1/installation/candidate-admissions/{item_id}/{selection_id}` for
  v0.19 and no mutation sibling.
- [x] Mission Control uses only the authenticated GET projection and exposes no
  admission action control, authority navigation, or mutation call.
- [x] Home Assistant remains exactly `not_admitted` with no candidate because
  `compose/home-assistant.yaml` is absent and Agent `install-container` remains
  unsupported.
- [x] Existing approval separation, no-replay, default-disabled worker,
  provider/repository/in-guest mutation, and backup-format boundaries remain
  unchanged.

### P5 validation evidence

- [x] P5 validation closure commit:
  `c23f4c4 test(v0.19): close installation candidate admission validation`.
- [x] Atlas Core and Atlas Agent baseline-aware Ruff gates passed.
- [x] Focused v0.16–v0.19 Core and release-isolation matrix passed: `151
  passed, 17 warnings in 12.55s`.
- [x] Full Atlas Core suite passed in the latest clean-environment run:
  `2813 passed`.
- [x] Full Atlas Agent suite passed: `912 passed, 1 warning in 8.54s`.
- [x] Mission Control passed: `61 files, 471 tests`; lint completed with one
  existing non-blocking React hook warning, and the production build completed
  with the existing bundle-size advisory.
- [x] The focused Core command used `ATLAS_PROVIDER_SECRET_FILE` at a writable
  temporary path because the managed sandbox makes the legacy
  `/opt/atlas/data/secrets` fixture read-only. The Agent process-isolation
  suite used its established writable temporary `XDG_STATE_HOME` and approved
  validation boundary. Neither changed tracked runtime behavior.
- [x] `git diff --check` passed; closure contains tests and documentation only.
- [x] No migration, tag, push, publication, deployment, or release action
  occurred.

### Final release actions

- [x] Record the exact reviewed implementation/validation SHA after P5 review:
  `c23f4c405b4c7261c59a6cff36bee145527c1b51`.
- [ ] Confirm the tracked worktree is clean at the final release commit.
- [ ] Create the immutable annotated `atlas-v0.19.0` tag at the reviewed
  implementation/validation commit.
- [ ] Push the final release commit and tag.
- [ ] Publish the Atlas v0.19 release.

## Atlas v0.18 P0–P5 release closure

Atlas v0.18 is **Installation Capability Assessment**. P0–P5 are complete on
the release-validation branch based at
`5ac32ecedc845ac6b1614b112b48325014aa527a`.

### Authority, isolation, and golden gates

- [x] V0.16 `InstallationPlan v1` remains immutable, target-free, ephemeral,
  and non-authorizing; provider facts cannot repair its blockers or enable its
  fail-closed candidate projection.
- [x] V0.17 destination selection, interest, and admission assessment retain
  their exact ownership, lifecycle, route, storage, and non-authority
  contracts; no v0.18 grandfathering or conversion exists.
- [x] No candidate creation, approval, workflow, action request, dispatch,
  Atlas Agent execution, worker invocation, provider mutation, repository
  mutation, or in-guest mutation subsystem consumes a v0.18 assessment or
  provider-fact record.
- [x] Integrated OpenAPI exposes exactly
  `GET /api/v1/installation/capability-assessments/{item_id}/{selection_id}`
  for v0.18 and has no POST, PUT, PATCH, DELETE, or other mutation sibling.
- [x] Mission Control uses only the authenticated GET projection, rejects
  authority-bearing or open-schema responses, and contains no Install,
  Prepare, Approve, Execute, Convert, candidate, workflow, dispatch, retry, or
  equivalent control/navigation/mutation call.
- [x] Home Assistant remains `blocked`: `compose/home-assistant.yaml` is absent,
  provider facts do not repair that deployment-artifact blocker, Atlas Agent
  repository support remains exactly `update-compose-stack`, and
  `install-container` remains unsupported.
- [x] Existing approval separation, conservative interrupted-side-effect
  no-replay, default-disabled worker, closed backup format, GET-only Discovery,
  Provider Intent, operational capability, and repository execution boundaries
  remain unchanged.

### P5 observed validation evidence

- [x] P5 validation closure commit:
  `b7c0b15 test(v0.18): close installation capability validation`.
- [x] Atlas Core and Atlas Agent Ruff gates passed.
- [x] Focused Core installation/capability/release-isolation matrix passed:
  `130 passed, 12 warnings in 12.11s`.
- [x] Full Atlas Core suite passed in the latest clean-environment run:
  `2813 passed`.
- [x] Full Atlas Agent suite passed: `912 passed, 1 warning in 7.01s`.
- [x] Mission Control passed: `59 files, 465 tests`; lint completed with one
  existing non-blocking React hook warning; production build completed with
  the existing bundle-size advisory.
- [x] The focused Core command was rerun with
  `ATLAS_PROVIDER_SECRET_FILE` directed to a writable temporary file because
  the managed validation sandbox makes `/opt/atlas/data/secrets` read-only.
  The Agent suite used the repository's established writable temporary
  `XDG_STATE_HOME` for the same reason. Neither workaround changed tracked
  files or runtime behavior.
- [x] `git diff --check` passed and the closure contains tests/docs only.
- [x] No migration, backup widening, tag, push, publication, deployment, or
  release action occurred.

### Final release actions

- [ ] Record the final reviewed release commit SHA.
- [ ] Confirm the tracked worktree is clean at the final release commit.
- [ ] Create the immutable annotated `atlas-v0.18.0` tag at that commit.
- [ ] Push the final release commit and tag.
- [ ] Publish the Atlas v0.18 release.

## Atlas v0.17 P0–P5 release closure

Atlas v0.17 is **Prospective Installation Destination Assessment**. P0–P5 are
implemented. P5 began from `beb427dd9b77ed5c0442e8521b83ac90b01a7c41`;
the reviewed v0.17 implementation and validation head is
`78094ebf2cdbe2546a3b658aaee9abd05fa73883`.

### Decision-complete authority and golden gates

- [x] The only installation routes are `GET /api/v1/installation/destinations`,
  `POST /api/v1/installation/destination-selections`, `GET` and `DELETE
  /api/v1/installation/destination-selections/{selection_id}`, and `POST
  /api/v1/installation/admission-assessments`; OpenAPI exposes no broader
  installation route or method.
- [x] Every route requires authenticated operator identity; mutation routes
  retain CSRF, trusted-origin, permission, rate-limit, 8 KiB body, nesting,
  duplicate-key, visible-ASCII idempotency-key, and sanitized-error controls.
- [x] Cross-operator selection lookup is indistinguishable `404`; exact
  provider identity is re-resolved without exposing raw identity, secrets,
  provider payload, addresses, or internal paths.
- [x] Selection remains immutable, operator-scoped, bounded to 16 active
  records, and exactly 24 hours at a half-open boundary. Cancellation, expiry,
  and staleness are terminal; reselection creates a new identity; movement or
  replacement cannot rebind an old selection.
- [x] Interest remains exactly five minutes, process-local and non-durable;
  retry replay is bounded and deterministic, conflicts fail `409`, restart
  clears cache, and no execution consumer or work queue exists.
- [x] Home Assistant remains `missing_deployment_artifact`; the deployment
  artifact `compose/home-assistant.yaml` remains absent and the exact plan
  fingerprint is
  `34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a`.
- [x] With exact current selection and interest, Home Assistant assessment is
  `blocked` with ordered reasons `installation_plan_missing_deployment_artifact`,
  `destination_installation_capability_unknown`, and
  `agent_install_container_unsupported`; candidate eligibility is false.
- [x] Existing projection remains `candidate_created=false`,
  `planning_allowed=false`, `candidate=null`; no candidate creation or
  eligibility path consumes v0.17 records.
- [x] Atlas Agent supported repository intent remains exactly
  `update-compose-stack`; `install-container` remains unsupported; operational
  planning/handling remains exactly `restart-service`.
- [x] Provider Intent remains identity-bound Proxmox QEMU `monitoring-policy`;
  operational production capability remains exactly
  `restart-service/proxmox/qemu`; the provider identity facade remains
  read-only and prospective selection cannot update or dispatch either path.
- [x] Discovery remains GET-only/non-authoritative; target facts cannot mutate
  or repair InstallationPlan blockers. Repository execution remains exactly
  `update-compose-stack` and worker default-disabled behavior is unchanged.
- [x] Mission Control explicitly says selection cannot install or plan, renders
  every ordered blocker and explicit false candidate eligibility, and contains
  no candidate, Agent, workflow, approval, dispatch, or prohibited action
  control/navigation.
- [x] Backup v3 uses a closed managed-state inventory and does not automatically
  include the independent `installation_destination_selections.db`. V0.17
  documents separate maintenance retention/removal instead of widening v3;
  interests/cache are never restored and older code cannot consume the store.

### Validation and release-preparation gates

- [x] Record the exact reviewed implementation/validation SHA after P5 review:
  `78094ebf2cdbe2546a3b658aaee9abd05fa73883`.
- [x] Full Atlas Core pytest passes in the CI-like environment.
- [x] Atlas Core Ruff gate passes according to repository convention.
- [x] Full Atlas Agent tests pass.
- [x] Atlas Agent Ruff passes.
- [x] Mission Control `npm test` passes.
- [x] Mission Control `npm run lint` passes.
- [x] Mission Control `npm run build` passes.
- [x] `git diff --check` passes.
- [x] Tracked worktree is clean after the separate reviewed release commit.
- [x] Only an intentionally untracked local smoke override outside the tracked
  release tree is present, if applicable.
- [x] Final release commit, annotated tag, and push are performed in the
  separate release step.

### P5 observed local evidence

- Required Core installation/assessment/isolation/candidate boundary group:
  `154 passed`, with 22 existing HTTPX cookie deprecation warnings and two
  sandbox cleanup warnings.
- Additional focused destination/assessment group: `120 passed, 1 deselected`;
  the deselection is the production-root permission case described below.
- Full Core: `2780 passed, 63 warnings in 155.05s (0:02:35)` in the clean
  CI-like environment with `PYTHON_DOTENV_DISABLED=true`. The production
  `/opt/atlas/.env` had leaked Provider Intent legacy-import activation
  overrides into the local test process; the earlier collection failure was
  local environment contamination, not a v0.17 defect.
- Full Agent: `912 passed, 1 warning in 6.70s`.
- Mission Control: `57 files, 456 tests` passed; lint passed with one existing
  non-blocking React hook warning; production build passed with the existing
  bundle-size advisory.
- Changed-file Core and Agent Ruff gates passed; `git diff --check` passed.

## Atlas v0.17 P1 conformance correction

- [x] Record the P0 normative amendment explicitly rather than rewriting the
  historical P0 contract: exact `resource_id` fingerprint participation,
  non-retrograde terminal timestamps, and the restricted JCS subset.
- [x] Confirm the amendment adds no installation, mutation, workflow,
  candidate, dispatch, worker, provisioning, or execution authority.
- [ ] Commit the amendment with P1, or in an explicit documentation commit
  before the P1 runtime commit.

## Atlas v0.17 P0 architecture freeze — complete

Atlas v0.17 is **Prospective Installation Destination Assessment**. P0 is
documentation-only; P1–P5 are not implemented. The normative
[v1 contract](architecture/prospective-installation-destination-v1.md) is
decision-complete.

- [x] Confirm baseline `atlas-v0.16.0` at
  `538a70cd34ce758bda40c5a200acdbdc837694a5` and P0 branch baseline
  `6ddb87234dae37c859216ff9c4faa564f0df7dd8`.
- [x] Freeze existing-guest versus VM-provisioning semantics and deny every
  unobserved in-guest capability, compatibility, readiness, and permission.
- [x] Freeze the exact Proxmox/QEMU/existing-guest tuple, opaque fingerprint,
  exact re-resolution, node-movement invalidation, selectable states, and no
  raw `vmgenid`, wildcard, rebinding, or in-place refresh.
- [x] Freeze durable operator-scoped immutable selection, 24-hour expiry,
  cancellation/tombstone, reselection, retention, concurrency, backup/restore,
  downgrade, migration, and irreversible terminal semantics.
- [x] Freeze one-request ephemeral interest with exact plan/item/catalog/
  selection linkage, five-minute expiry, retry/conflict semantics, bounded
  audit, and no durable intent, queue, Agent, candidate, or grandfathering.
- [x] Freeze the pure assessment inputs/output, two statuses, all-applicable
  canonical 16-reason precedence, fixed unsupported Agent fact,
  `candidate_eligibility_evaluated=false`, and narrow unsupported status rule.
- [x] Freeze domain-separated JCS/NFC SHA-256 selection, interest, and
  assessment fingerprints, exact null/timestamp/order/linkage semantics, and
  exclusions.
- [x] Freeze Home Assistant as `missing_deployment_artifact` at fingerprint
  `34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a`,
  with missing artifact ahead of capability-unknown and Agent-unsupported.
- [x] Preserve candidate projection exactly `candidate_created=false`,
  `planning_allowed=false`, `candidate=null`.
- [x] Freeze forbidden dependencies, sanitized UI boundary, and the rule that
  no execution subsystem consumes any v0.17 record.
- [x] Freeze future guarded API methods, auth, CSRF/trusted-origin, bounds,
  server enumeration, idempotency, sanitized errors, and no-authority routes.
- [x] Freeze future Mission Control label/copy/blockers and prohibit Install,
  Execute, Plan, Approve, Convert, Dispatch, and authority-suggesting workflow
  navigation.
- [x] Select P0 → P1 → P2 → P3 → P4 → P5 with scope, acceptance, non-goals,
  authority boundaries, and later expected tests in `ROADMAP.md`.
- [x] Preserve repository execution `update-compose-stack`, operational
  `restart-service/proxmox/qemu`, Provider Intent Proxmox QEMU
  `monitoring-policy`, GET-only Discovery, unchanged approvals,
  default-disabled optional worker, maintenance-only backup/restore,
  no automatic remediation/conversational execution/release publication, and
  conservative interrupted-side-effect no-replay.
- [x] Confirm P0 changed documentation only and performed no commit, tag, push,
  or release publication.

## Atlas v0.16 P0–P5 release validation and closure — complete

Atlas v0.16 is **Grounded Installation Planning**. The normative
[InstallationPlan v1 contract](architecture/installation-plan-v1.md) remains
frozen. P1's deterministic assembler, P2's readiness/blocker/risk evaluator,
P3's bounded GET API and read-only Mission Control review, P4's fail-closed
candidate-admission projection, and P5 release validation are complete.
V0.16.0 is ready for a separate explicit release commit and annotated
`atlas-v0.16.0` tag.

- [x] Freeze the exact schema version, immutable closed field set, field types,
  required/optional classification, bounds, normalization, compatibility and
  unknown-field rules, exact versioned status vocabulary and semantics,
  evaluation/transition and unknown-value rules, and closed blocker vocabulary.
- [x] Freeze canonical fingerprint inputs/serialization, provenance links,
  freshness windows/evaluation instant, and the complete status/freshness/
  conflict/blocker precedence table.
- [x] Freeze the exact `Fingerprint.value` domain-separated byte derivation,
  NUL framing, JCS/NFC input, SHA-256 encoding, exclusions, and non-authority
  semantics so golden vectors require no implementation invention.
- [x] Freeze the bounded `RawEvidenceObservation` adapter boundary, valid-only
  nullable `EvidenceDecisionInput`, and the exhaustive allowed disposition /
  eligibility / reason relation without invented malformed-record values.
- [x] Freeze closed `CatalogDecisionInputV1` and
  `CompatibilityDecisionInputV1` schemas and every domain-separated typed
  provenance identity input.
- [x] Freeze every nested `FingerprintInputV1` object, typed absence/conflict/
  optional-unavailability fact, null rule, bound, and exact total array sort.
- [x] Freeze catalog item/release-claim release projection, every image state,
  and every prerequisite category without target-capacity invention.
- [x] Freeze the exact deterministic code-owned description template and typed
  placeholder source for every v1 prerequisite producer.
- [x] Freeze the only allowed assumption and confirmation producers, their
  blocker relations, and the reachability of every runtime blocker/state.
- [x] Freeze exactly one deterministic producer, severity, subject,
  confirmation behavior, and fingerprint participation for every runtime risk;
  remove the unreachable `artifact_content_change` and
  `environment_variance` values so the closed risk vocabulary is total.
- [x] Freeze the one exact non-authorizing human-review prompt template for
  each v1 `prompt_template_id`, including normalized subject interpolation and
  punctuation.
- [x] Freeze the payload allowlist and require validation of prohibition and
  redaction of secrets,
  credentials, commands, shell/argv/scripts, environment, executable or opaque
  payloads, raw provider data, and secret-bearing URLs.
- [x] Confirm plans are ephemeral, assembled on GET, and have no durable store,
  cache authority, replay semantics, or mutation sibling.
- [x] Choose item-scoped-only v1 with no target field or selector; no approved
  target contract is introduced and Proxmox/QEMU restart identity grants no
  guest-install power.
- [x] Freeze bounded failure behavior and the threat model, including authority
  confusion, injection, leakage, spoofing, mutable-image substitution, path
  escape, stale replay, conflict suppression, fingerprint ambiguity, unsafe
  rendering, and mutation/execution dependency coupling.
- [x] Freeze dependency/import isolation and its required structural proof
  from Agent, candidates, approvals,
  provider mutation, operational/repository execution, workers, maintenance,
  and the legacy deployment planner.
- [x] Freeze and require proof that both legacy deployment-analysis mounts
  remain isolated caller-document analysis/proposal routes and neither is
  expanded nor reused by v0.16.
- [x] Specify the complete schema, status/blocker, determinism,
  provenance, freshness, conflict, artifact/path, image, compatibility,
  prerequisite, target, redaction/injection, no-persistence/network/side-effect,
  import/legacy-route, GET/OpenAPI/method, Home Assistant, UI/accessibility, and
  authority-regression matrix in `ROADMAP.md`.
- [x] Require explicit proof that `plan_ready_for_review` is not approved,
  executable, or deployable and cannot convert to a candidate, intent,
  workflow, action request, or dispatch.
- [x] Confirm the exact Home Assistant binding remains
  `compose/home-assistant.yaml`, the artifact remains absent, and the plan
  returns `missing_deployment_artifact` without substitution or synthesis.
- [x] Reconfirm capability parity and freeze regression coverage for all
  enduring security contracts:
  operational `restart-service/proxmox/qemu`, repository
  `update-compose-stack`, default-deny unsupported intents, separately
  activated/default-disabled worker, unchanged no-replay/persistence and
  backup/restore ownership, inactive generic collector, and no autonomous
  mutation or release publication.

- [x] Validate exact P0 relations, deterministic fingerprinting, evidence
  precedence/freshness, provenance, compatibility, prerequisites, image/status
  projection, hostile inputs, isolation, and authority boundaries.
- [x] Accept the Home Assistant golden fingerprint
  `34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a`.
- [x] Close duplicate-risk handling across multiple qualifying evidence
  records.
- [x] Pass 254 InstallationPlan tests and 90 required discovery/parity
  regressions (344 combined).
- [x] P3 — expose the bounded, read-only InstallationPlan GET API without a
  mutation sibling, persistence writer, or new authority.
- [x] P4 — Mission Control read-only review and pure fail-closed projection
  toward existing ExecutionCandidate admission; create no candidate.
- [x] P5 — final isolation, release validation, and documentation closure.

### Atlas v0.16 P5 observed validation evidence

Validated from clean baseline
`4f5de974674090cd4ad65cccb834a28b2798cad8` with only the known untracked
`compose.execution-smoke.override.yaml` present. P5 changed no production
behavior; three Core integration tests were closed so stable endpoint and
production-wiring scanners account for the v0.16 read-only route and structural
forbidden-import tests.

- [x] Ruff passed for every Python production/test file changed by v0.16.
- [x] InstallationPlan contract, evaluator, descriptor-snapshot reads, route
  guards, isolation, fingerprint, and Home Assistant golden: 343 passed.
- [x] InstallationPlan candidate-admission projection: 16 passed.
- [x] Required catalog/binding/Compose-observation/image-evidence/parity group:
  90 passed.
- [x] Directly affected execution-candidate model/service/route/operator-intent
  group, using the thread-free harness: 156 passed.
- [x] Full Atlas Agent candidate-planning, approval, workflow, planning-engine,
  and worker-journal regression suite with isolated state: 911 passed, one
  accepted dependency deprecation warning.
- [x] Mission Control: 54 files and 440 tests passed; lint passed with one
  existing non-blocking React hook warning; production build passed with the
  existing bundle-size advisory.
- [x] Operational capability parity passed exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`.
- [x] Broader Core validation was attempted in the repository-compatible form.
  After closing three integration-test omissions, more than 1,500 tests passed
  without failure before the managed sandbox reached its restricted-thread
  limitation. The ownership-transition test also cannot call `chown` in this
  sandbox. Neither limitation is a production defect or a v0.16 authority
  widening; the directly affected thread-free and required suites pass.
- [x] Home Assistant at fixed clock `2026-08-25T00:00:00Z` remains
  `missing_deployment_artifact` with fingerprint
  `34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a`.
- [x] Mission Control review contains no install, execute, approve, deploy,
  dispatch, candidate-creation, or confirmation-acceptance control.
- [x] Structural and behavioral isolation proves no InstallationPlan path to
  Docker execution, subprocess, outbound network mutation, worker execution,
  queue publication, operational dispatch, automatic approval, Provider Intent
  mutation, workflow mutation, hidden persistence, synthesized approved
  targets, or synthesized installation intents.
- [x] No staging, commit, tag, push, or release publication occurred during P5.
  The final tree is intended for a separate explicit release commit/tag step.

## Atlas v0.15-P0 scope-selection and boundary sign-off

Atlas v0.15 has the theme **Deployment Image Grounding Operator Surface**.
P0 is documentation-only: it selects the v0.15 scope and signs off the
boundaries without changing runtime code, provider state, configuration,
permissions, gates, handlers, ACLs, or production execution.

- [x] Record the selected v0.15 theme in `ROADMAP.md`.
- [x] Replace every repository statement that no v0.15 scope is selected.
- [x] Record v0.15-P0 under `CHANGELOG.md` Unreleased.
- [x] Update the Discovery Center roadmap and context for the selected
  Discovery-facing theme.
- [x] Confirm the milestone dependency order is
  P0 → P1 → P2 → P3 → P4 → P5.
- [x] Confirm initial evidence breadth remains the accepted Home Assistant
  `2026.8.3` registry-attested proof only.
- [x] Confirm the non-goals: no generic collectors, no startup, scheduled, or
  request-time collection, no execution authority, no automatic remediation,
  and no
  Discovery-to-dispatch coupling.
- [x] Confirm documentation-only scope: no runtime, configuration, script,
  Compose, authentication, execution, approval, provider, or mutation change.
- [x] Confirm capability parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`; LXC remains unsupported.

P0 through P5 and production acceptance are complete. Atlas v0.15.0 is
released as `atlas-v0.15.0` at
`850480ce6c5f86a5bf4a783e33f7e08a7f29a2ab`. Unchecked evidence items below
remain an accurate record of evidence not captured at the earlier candidate.

### Atlas v0.15 P1–P5 implementation and release gates

Checked P1–P4 items record the implemented and validated P4 state. Checked P5
items record evidence established for pre-release closure SHA
`1eeb6d2bb195ea653faf9e7d19f1523982f8cbf0`; an unchecked item is not implied
to have passed.

#### P1 — binding-driven image-grounding read model

- [x] Reuse the existing `DeploymentBinding`, bounded repository Compose
  observation, accepted image evidence, and `ground_deployment_image`
  semantics in one deterministic, read-only composition path.
- [x] Preserve input and evidence provenance and every fail-closed status,
  including missing, unknown, mutable, mismatched, untrusted, and conflict
  results; introduce no silent source precedence or clock-derived authority.
- [x] Keep Home Assistant `2026.8.3` as the sole accepted
  `REGISTRY_ATTESTED` proof; add no evidence row or `DeploymentBinding`.
- [x] Prove no network, registry acquisition, Sigstore runtime verification,
  collector activation, persistence, mutation, or execution is reachable.

#### P2 — GET-only Core grounding/provenance projection

- [x] Add only a bounded, additive, redacted GET response schema at
  `GET /api/v1/discovery/items/{item_id}/image-grounding`, retaining
  exact fail-closed statuses and provenance/source-class distinctions.
- [x] Select the exact endpoint and route placement during repository-grounded
  P2 implementation review.
- [x] Prove there is no mutation sibling, persistence, Agent dependency,
  provider mutation, or proposal, candidate, intent, workflow, approval,
  action-request, or dispatch creation.
- [x] Pass contract, OpenAPI, unsupported-method, redaction, authority-import,
  and route-isolation tests.

#### P3 — Mission Control advisory surface

- [x] Display grounding status and sanitized evidence provenance, visibly
  distinguish `REGISTRY_ATTESTED` from `CURATED`, and render grounded,
  conflict, missing, unknown, and error states as informational/advisory.
- [x] Prove there is no Apply, Execute, Update, Pull, Restart, Remediate,
  approval, proposal/candidate/workflow conversion, or mutation request.
- [x] Pass rendering, error-state, accessibility, lint, and production-build
  checks for the bounded surface.

#### P4 — security, isolation, and authority gates

P4 acceptance is the union of the existing authoritative behavioral,
structural/isolation, capability-parity, and Mission Control
security/rendering suites. No single monolithic P4 test proves the entire
authority model.

##### V0.15 P4 validation matrix

1. **Collector inactivity** — Authoritative coverage:
   `services/atlas-core/app/discovery/test_image_release_collector_isolation.py`,
   `services/atlas-core/app/discovery/test_home_assistant_ghcr_acquisition_isolation.py`,
   `services/atlas-core/app/discovery/test_home_assistant_sigstore_verifier_isolation.py`,
   `services/atlas-core/app/discovery/test_dynamic_refresh_isolation.py`, and
   `services/atlas-core/app/routes/test_discovery_image_grounding_isolation.py`.
   Contract: empty production registries and no startup, scheduled/background,
   or request-time acquisition, verification, or refresh.
2. **P1/P2 isolation** — Authoritative coverage:
   `services/atlas-core/app/services/test_image_grounding_read_model_isolation.py`,
   `services/atlas-core/app/services/test_home_assistant_image_grounding_isolation.py`,
   `services/atlas-core/app/services/test_home_assistant_image_evidence_provenance_isolation.py`,
   `services/atlas-core/app/routes/test_discovery_image_grounding_isolation.py`,
   `services/atlas-core/app/discovery/test_image_release_evidence_isolation.py`,
   and
   `services/atlas-core/app/discovery/test_repository_compose_observation_isolation.py`.
   Contract: reviewed local, read-only grounding and provenance reads only; no
   acquisition or verification and no mutation, Agent, provider, execution,
   operational, startup, scheduler, route, worker, or maintenance authority.
3. **Redaction** — Authoritative coverage:
   `services/atlas-core/app/routes/test_discovery_image_grounding.py`,
   `services/atlas-core/app/discovery/test_image_grounding.py`, and
   `services/mission-control/src/features/discovery/DiscoveryImageGroundingPanel.test.tsx`.
   Contract: closed bounded public projection and bounded UI errors; no
   sensitive or internal material.
4. **Trust/conflict** — Authoritative coverage:
   `services/atlas-core/app/discovery/test_image_grounding.py`,
   `services/atlas-core/app/services/test_image_grounding_read_model.py`,
   `services/atlas-core/app/routes/test_discovery_image_grounding.py`, and
   `services/mission-control/src/features/discovery/DiscoveryImageGroundingPanel.test.tsx`.
   Contract: `CURATED`, `REGISTRY_ATTESTED`, and `UPSTREAM_SIGNED` remain
   distinct; conflicts fail closed; no precedence, newest-wins, voting,
   fallback, or trust promotion.
5. **Provider Intent** — Authoritative coverage:
   `services/atlas-core/app/provider_intents/test_models.py`,
   `services/atlas-core/app/provider_intents/test_target_resolver.py`,
   `services/atlas-core/app/provider_intents/test_resolver.py`, and
   `services/atlas-core/app/execution_candidates/test_operator_intents.py`.
   Contract: identity-bound Proxmox QEMU `monitoring-policy` only; LXC and
   mismatches fail closed.
6. **Operational parity** — Authoritative coverage:
   `services/atlas-core/app/test_operational_capability_parity.py`,
   `services/atlas-core/app/execution_candidates/test_operational_capabilities.py`,
   and `scripts/operational-capability-parity`. Contract: exactly
   `restart-service/proxmox/qemu`.
7. **Repository execution parity** — Authoritative coverage:
   `services/atlas-agent/tests/candidate_planning/test_models.py`,
   `services/atlas-agent/tests/test_worker_contracts.py`,
   `services/atlas-agent/tests/candidate_planning/test_execution.py`, and
   `scripts/operational-capability-parity`. Contract: exactly
   `update-compose-stack`.
8. **Approval authority** — Authoritative coverage:
   `services/atlas-agent/tests/test_approval_engine.py`,
   `services/atlas-agent/tests/candidate_planning/test_execution.py`,
   `services/atlas-agent/tests/candidate_planning/test_commit.py`, and the
   P1/P2 isolation suites. Contract: stage-specific approvals remain
   independent; grounding grants no approval authority.
9. **No-replay** — Authoritative coverage:
   `services/atlas-core/app/operational_dispatch/test_service.py`,
   `services/atlas-core/app/operational_dispatch/test_lifecycle.py`, and
   `services/atlas-agent/tests/test_operational_execution.py`. Contract:
   uncertain effects are not replayed or redispatched.
10. **Worker** — Authoritative coverage:
    `services/atlas-execution-worker/tests/test_config.py`,
    `services/atlas-execution-worker/tests/test_worker.py`,
    `services/atlas-agent/tests/test_auth_stager.py`, and the P1/P2 isolation
    suites. Contract: the worker remains optional, separately activated,
    default-disabled, and unrelated to grounding.
11. **Backup/restore** — Authoritative coverage:
    `scripts/test_atlas_data_tool.py`,
    `services/atlas-core/app/core/test_restore_interlock.py`, the operational
    and repository parity gates, and the P1/P2 isolation suites. Contract:
    operator-maintenance tooling only; not Discovery, Agent, repository, or
    operational execution authority.
12. **Mission Control** — Authoritative coverage:
    `services/mission-control/src/api/discoveryImageGrounding.test.ts`,
    `services/mission-control/src/features/discovery/DiscoveryImageGroundingBoundary.test.ts`,
    `services/mission-control/src/features/discovery/DiscoveryImageGroundingPanel.test.tsx`,
    and
    `services/mission-control/src/pages/DiscoveryItemPage.test.tsx`. Contract:
    GET-only advisory rendering, bounded errors, and no
    mutation/action/workflow authority.

##### P4 validation commands

All entries remain unchecked until their commands actually pass. Validation
must execute against the v0.15 candidate source tree at
`/opt/atlas-worktrees/v015-planning`; commands may use the tool environment at
`/opt/atlas/.venv`. Results obtained by validating `/opt/atlas` main do not
validate this candidate.

- [x] Core focused authority/isolation suite.
- [x] Core full suite.
- [x] Agent Ruff and full suite.
- [x] Execution Worker full suite.
- [x] Backup/restore focused suite.
- [x] `scripts/operational-capability-parity`.
- [x] Mission Control full tests, lint, and build.
- [x] `git diff --check`.
- [x] `container-release-gate`.

P4 validation completed against candidate
`2032d4ebc8631848a10d594ececd76faaccd2503` with these results:

- Core focused authority/isolation suite: `336 passed`.
- Core full suite: `2286 passed`, `41 warnings`. It executed hermetically
  with `PYTHON_DOTENV_DISABLED=1` and candidate-source `PYTHONPATH` because
  `/opt/atlas/.env` otherwise contaminates candidate tests.
- Agent Ruff: passed. Agent full suite: `911 passed`, `1 warning`.
- Execution Worker full suite: `51 passed`, `1 warning`.
- Backup/restore focused suite: `231 passed`.
- Operational capability parity: passed, with exact operational capability
  `restart-service/proxmox/qemu` and exact repository execution
  `update-compose-stack`.
- Mission Control: `427 passed`; lint passed with zero errors and one
  pre-existing warning; production build passed with the existing large-chunk
  advisory.
- `git diff --check`: passed.
- `container-release-gate`: passed with exit code `0`.

The mandatory container gate initially exposed a pre-existing linked-worktree
compatibility defect in the release gate. Commit
`2032d4e fix(release): support linked worktree candidates` stages an
independent, self-contained Git checkout at the exact candidate HEAD,
preserves the worker's Git-worktree security requirement, and allows linked
candidate worktrees to be validated without exposing shared `/opt/atlas/.git`
metadata. The real gate passed after the fix on a clean committed candidate.

P4 is complete. The authoritative validation matrix found no widening of
collector authority, grounding/provenance authority, Provider Intent
authority, operational capability, repository execution, approval authority,
no-replay behavior, worker activation, backup/restore authority, or Mission
Control execution authority. P5 final evidence closure is recorded below.

#### P5 — release validation and closure

P5 final release-evidence closure is recorded here and remains separate from
the completed P4 validation matrix. The pre-release closure candidate C was
`1eeb6d2bb195ea653faf9e7d19f1523982f8cbf0`. Results recorded for earlier SHAs
remain attributed to those SHAs and are not silently promoted to release-commit
evidence. The final release commit is
`850480ce6c5f86a5bf4a783e33f7e08a7f29a2ab`.

##### Pre-release exact-SHA and clean-tree evidence

- [x] **Pre-release closure SHA C:**
  `1eeb6d2bb195ea653faf9e7d19f1523982f8cbf0`; exact deployed source and
  `origin/main` at final evidence collection matched C. The self-contained
  production source checkout was `/opt/atlas-release-v015-final`.
- [ ] **Clean-tree proof:** pending; record command, timestamp, and output for
  the committed C worktree.
- [ ] **Local exact-SHA P4 rerun:** no complete exact-C P4 rerun is recorded.
  Exact-C local evidence is limited to the final Core suite (`2287 passed`,
  `41 warnings`), the GHCR acquisition module (`105 passed`), and 20 repeated
  selections of the repaired deadline tests passing. Commit C changed tests
  only; production acquisition code did not change. Agent, Worker,
  backup/restore, parity, Mission Control, and container results recorded in
  the P4 section remain attributed to
  `2032d4ebc8631848a10d594ececd76faaccd2503`.

##### CI evidence for exact C

- [x] **Quality gates:** GitHub main-push run `32797990417`, event `push`,
  `headSha=1eeb6d2bb195ea653faf9e7d19f1523982f8cbf0`, conclusion `success`.
- [x] **Container release gate:** GitHub main-push run `32797990447`, event
  `push`, `headSha=1eeb6d2bb195ea653faf9e7d19f1523982f8cbf0`, conclusion `success`.
- [x] Both workflow `headSha` values equal final C exactly.

##### Container validation for exact C

- [ ] **GitHub-integration container gate:** no separately recorded exact-C
  local result for
  `ATLAS_CONTAINER_GATE_MODE=github-integration ./scripts/container-release-gate`.
- [ ] **Production-mode runsc container gate:** no separately recorded exact-C
  local result for
  `./scripts/container-release-gate`; this invocation is the production runsc
  proof, not the CI runc proof.

##### Production identity evidence

- [x] **Production service/image manifest:** exact deployed source C used the
  running identities recorded below.
- [x] **Immutable image IDs:** accepted production identities:
  `atlas-agent=sha256:0e1bafa09eac14aafcf1ef4b130dfbea32c22a2652d0e40fa9d87f2e17fe2955`;
  `atlas-agent-auth-stager=sha256:0b3519fdf4089f7389427ca91cbeb8e02b6729d645edf104101898132ff49340`;
  `atlas-core=sha256:4c437acc0602403121f6ecb607bb547627df98e38814ba4067389d56ae505f45`;
  `atlas-core-agent-auth-stager=sha256:925f6ac3169bc9994fdf4e5dc893768dc3f67f071bfacfeea847214f38c0300c`;
  `atlas-execution-auth-stager=sha256:4052f833ad3ef7261a6393622462d4feefee16662a3662e5f456f01a8d2c2277`;
  `atlas-execution-worker=sha256:b1706b3348fbb7393191307c4b1758531bfd74470ccfa973cafe79ed87e0f65c`;
  `atlas-execution-worker-relay=sha256:37864b442cb40f40623b7af10bd850a2fff21466931d2c06bafe73795236cdb7`;
  `mission-control=sha256:71711e7bd96e65cc78b97aa065e33fc7049ba4ddf063a1237549fca78f885a17`;
  pinned upstream
  `atlas-edge=sha256:0c79d56aee561a1d81c63f00eee5fb5fe29279560cdc55e91425133104c7fbe6`;
  and pinned upstream
  `atlas-egress-proxy=sha256:6a097f68bae708cedbabd6188d68c7e2e7a38cedd05a176e1cc0ba29e3bbe029`.
- [ ] **RepoDigests:** pending where present.
- [ ] **Container IDs and `.Image` values:** pending.
- [ ] **Deployment build timestamp:** pending.

At acceptance, `atlas-core`, `atlas-agent`, `atlas-execution-worker`,
`atlas-execution-worker-relay`, `mission-control`, and `atlas-edge` were
healthy with `restart_count=0` for each.

##### Read-only production acceptance

The acceptance interval must issue only the following GETs and visual checks.
No `POST`, `PUT`, `PATCH`, or `DELETE` is permitted.

- [ ] **HermesII acceptance interval:** the production interval was
  `2026-08-25T01:38:34Z` through `2026-08-25T01:38:48Z`; operator/environment
  identity was not supplied, so the combined item remains incomplete.
- [x] `GET /api/v1/discovery/items/home-assistant/image-grounding`: HTTP 503
  with the exact sanitized, bounded public message
  `Image grounding is unavailable.` The response must expose no internal path
  or exception details and make no positive grounding claim. This is the
  expected fail-closed result because the Home Assistant `DeploymentBinding`
  names the exact repository artifact `compose/home-assistant.yaml` and that
  artifact is deliberately absent.
- [x] `GET /api/v1/discovery/items/frigate/image-grounding`: HTTP 200 with
  `status=no_deployment_binding`.
- [x] `GET /api/v1/discovery/items/definitely-not-an-atlas-item-v015/image-grounding`:
  HTTP 404 with a sanitized, bounded not-found response.
- [ ] **Mission Control visual acceptance:** pending Home Assistant bounded
  local-source-unavailable / grounding-unavailable advisory, with no positive
  grounded presentation, no action control, and no deployment or execution
  authority; and Frigate no-deployment-binding advisory evidence.
- [x] **Explicit zero mutation/execution result:** the acceptance runtime
  authority scan was empty. No `POST`, `PUT`, `PATCH`, `DELETE`, dispatch,
  execution, approval, proposal, candidate, workflow, provider action,
  collector, Sigstore, GHCR, refresh, or remediation activity was observed in
  the acceptance interval.

The expected Home Assistant HTTP 503 does not mean accepted image evidence is
missing, evidence has become untrusted, deployment is authorized, or execution
is authorized. The conditional `grounded` contract remains available when the
exact bound Compose artifact genuinely exists and matches accepted evidence;
tests prove that path by synthesizing a temporary Home Assistant Compose
artifact. No v0.15 contract requires shipping
`compose/home-assistant.yaml`; its absence remains a future
`missing_deployment_artifact` reference case.

Registry-attested evidence is informational. It is not deployment approval,
authorization, install readiness, or execution authority. Image grounding
grants no deployment or execution authority, and no action controls were added.

##### Production collector-inactivity evidence

Prove inactivity without activating anything:

- [x] Production collector descriptor and adapter registries are empty:
  `PRODUCTION_DESCRIPTORS_COUNT=0` and
  `PRODUCTION_SOURCE_ADAPTERS_COUNT=0`. The production collector was
  constructed, and collector inactivity passed without activating production
  acquisition authority.
- [x] Rendered configuration contains no collector enablement. Final rendered
  production Compose had
  `ATLAS_ENABLE_DISCOVERY_DYNAMIC_REFRESH=false`, and the running `atlas-core`
  retained `ATLAS_ENABLE_DISCOVERY_DYNAMIC_REFRESH=false`. `atlas-agent` and
  `atlas-execution-worker` contained no collector/acquisition enablement. The
  absence of environment enablement is configuration evidence; the separately
  recorded runtime observations and empty production registries establish the
  corresponding inactivity evidence without overclaiming from environment
  strings alone.
- [x] No startup acquisition was observed in the recorded production evidence.
- [x] No scheduled or background acquisition was observed in the recorded
  production evidence.
- [x] No request-time acquisition was observed during acceptance.
- [x] No GHCR acquisition traffic correlated with the acceptance interval.
- [x] No runtime Sigstore verification was observed during acceptance.
- [x] No collector invocation was observed during acceptance.
- [x] No evidence refresh was observed during acceptance.

##### Rollback and release evidence

The prior accepted release is `atlas-v0.14.0` at
`4d2526e1b022c5c36eaced65bf5b71703da5d2d7`. Rollback uses its prior accepted
image/configuration. It requires no data migration, no evidence rollback, no
side-effect replay, no action/dispatch recreation, and no automated remediation.

- [x] **Rollback evidence:** the prior accepted image/configuration is retained.
  Rollback image tags were created before v0.15 deployment for all eight
  Compose-built v0.14 images. The contract requires no data migration, evidence
  rollback, side-effect replay, action/dispatch recreation, or automated
  remediation; rollback was not executed merely to create evidence.
- [ ] **Release-evidence artifact checksum:** no repository-native retained
  artifact location is established by prior tracked release records. A pre-tag
  `atlas-release-evidence-v1` run against
  `1eeb6d2bb195ea653faf9e7d19f1523982f8cbf0` was intentionally blocked only
  because this checklist was a dirty tracked path, so its checksum is not
  final and the artifact remains incomplete. Before blocking, the command
  observed HEAD and `origin/main` equal to the expected SHA; Quality gates run
  `32797990417` and Container release gate run `32797990447` passed;
  capability parity, base/hardened Compose render, and running image
  inspection passed; and security findings were empty. A clean-tree
  release-evidence run was not recorded for that candidate. No artifact or
  checksum is invented here.
- [x] **Final tag identity:** `atlas-v0.15.0` exists and peels to
  `850480ce6c5f86a5bf4a783e33f7e08a7f29a2ab`.

## Atlas v0.14 final release — 2026-08-24

The immutable `atlas-v0.14.0` tag exists and peels to
`4d2526e1b022c5c36eaced65bf5b71703da5d2d7`.

Recorded release lineage and supplied validation evidence:

- [x] RC1 existed at `4abace1` and exposed a Mission Control asynchronous test
  race.
- [x] A test-only fix produced
  `4d2526e1b022c5c36eaced65bf5b71703da5d2d7`.
- [x] RC2 points to `4d2526e1b022c5c36eaced65bf5b71703da5d2d7`.
- [x] Quality gates succeeded on the final commit.
- [x] Container release gate succeeded on the final commit.
- [x] Local full Atlas Core validation reported `2161 passed`.
- [x] The production `atlas-core` image build succeeded.
- [x] `pip check` succeeded.
- [x] Sigstore 4.5.0 was installed.
- [x] Reviewed trust-root SHA-256:
  `6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66`.
- [x] Reviewed bundle SHA-256:
  `733e4755b02bb6786eeb51942dff588e8f043dcca13bc99a2b9fe0dd3e225520`.
- [x] Final tag `atlas-v0.14.0` exists at the final commit.

Unavailable or unreconciled evidence (not marked complete):

- [ ] Exact Ruff and `ruff format --check` command evidence is unavailable.
- [ ] Environment-only ownership-test handling evidence is unavailable.
- [ ] Running production image/source-SHA parity evidence is unreconciled.
- [ ] Read-only production acceptance evidence for empty collector registries,
  absence of scheduled/startup collection, and side-effect-free reads is
  unreconciled here; released code/config enforce those boundaries.
- [ ] Production Core image digests and the accepted Home Assistant evidence
  identity chain are unavailable in the supplied release evidence.

## Atlas v0.8 implementation status

- [x] V0.8-P0 — Roadmap and release-state reconciliation.
- [x] V0.8-P1 — Effect-aware workflow and approval clarity.
- [x] V0.8-P2 — Unified operational lifecycle read model.
- [x] V0.8-P3 — Mission Control operational history and recovery UX.
- [x] V0.8-P4 — Provider-neutral capability and selector descriptors.
- [x] V0.8-P5 — Deployment and security ergonomics.

P0 through P5 are complete. The immutable `atlas-v0.8-rc1` candidate at
`cf09dfe1eebbd138d37ba7144d91b893f70732fa` has completed required CI,
exact-SHA production deployment, and production soak. The final
`atlas-v0.8.0` release was published at
`f83cd90982d4682ce49e60308e93dc9840984211`.

## Atlas v0.8 RC selection and sign-off

- [x] Record the exact reviewed RC SHA:
  `cf09dfe1eebbd138d37ba7144d91b893f70732fa`.
- [x] Require Quality gates to pass on that exact SHA and record run
  `31856384892`: `atlas-core`, `atlas-agent`, and `mission-control` succeeded.
- [x] Require Container release gate to pass on that exact SHA and record the
  successful run `31856384891`.
- [x] Run `./scripts/operational-capability-parity` and record the exact
  `restart-service/proxmox/qemu` result.
- [x] Confirm lifecycle response redaction and effect-aware approval security
  tests pass on the exact RC SHA.
- [x] Confirm the production registry contains exactly one tuple and no new
  mutation intent or handler exists.
- [x] Review and approve the documented v0.7.0 to v0.8 upgrade and v0.8 to
  v0.7.0 rollback procedures.
- [x] Create the immutable v0.8 RC tag: `atlas-v0.8-rc1`.
- [x] Complete and record the exact-RC production soak.
- [x] Create the final immutable `atlas-v0.8.0` tag at
  `f83cd90982d4682ce49e60308e93dc9840984211`.

## Atlas v0.9 implementation status

- [x] V0.9-P0 — Release-state reconciliation and LXC feasibility closure.
- [x] LXC feasibility investigation — complete / NO-GO.
- [x] V0.9-P1 — Read-only recovery diagnostics.
- [x] V0.9-P2 — Sanitized operational support bundle.
- [x] V0.9-P3 — Release evidence automation.
- [x] V0.9-P4 — Recovery/history operator UX.
- [x] V0.9-P5 — Release acceptance and documentation.

The dependency order is P0 → P1 → P2 → P3 → P4 → P5. The LXC identity gate
closed fail-safe: no authoritative incarnation identity was proven, no
synthetic identity was accepted, and no LXC candidate, selector, translation,
gate, handler, ACL, or mutation is enabled. The revised P1–P5 milestones are
read-only recovery, evidence, UX, and release work.

P0 through P5 implementation and release acceptance are complete. The
immutable RC was selected and passed exact-candidate CI, release-evidence
validation, exact-RC deployment, and restart soak. Only final release
publication remains pending.

## Atlas v0.9 RC selection and sign-off

- [x] Record the exact reviewed RC candidate SHA after the documentation commit.
- [x] Require Quality gates to pass on that exact SHA and record the run ID and
  Core, Agent, and Mission Control conclusions.
- [x] Require Container release gate to pass on that exact SHA and record its
  run ID.
- [x] Run `./scripts/release-evidence` against the exact SHA and annotated RC
  tag; require `atlas-release-evidence-v1` status `ready` without fabricated
  private or CI evidence.
- [x] Run `./scripts/operational-capability-parity` and require exactly
  `restart-service/proxmox/qemu`.
- [x] Confirm recovery diagnostics are deterministic and read-only for healthy,
  pending/recovery, Core-unavailable, immutable-mismatch,
  transition-mismatch, target-replaced, outcome-uncertain, and
  terminal-mismatch states.
- [x] Confirm `atlas-operational-support-bundle-v1` remains bounded,
  deterministic, redacted, explicitly partial/truncated where applicable, and
  local-only with no upload destination.
- [x] Confirm Mission Control recovery/history UX separates network failure
  from operational failure and exposes no retry, run-again, replay,
  reconciliation-write, upload, or share control.
- [x] Confirm the production mutation boundary contains exactly one tuple and
  v0.9 adds no intent or handler.
- [x] Confirm `restart-service/proxmox/lxc` remains unsupported: no synthetic
  identity, candidate, selector, translation, gate, handler, ACL, or mutation
  was added.
- [x] Review the documented v0.8.0 to v0.9 upgrade and v0.9 to v0.8.0
  fail-safe rollback procedure, including in-flight barrier handling.
- [x] Create the immutable annotated `atlas-v0.9-rc1` tag.
- [x] Complete and record exact-RC production deployment and service-restart
  soak without performing a provider mutation merely for soak validation.
- [x] Create the final immutable `atlas-v0.9.0` tag at
  `7a5beac58e1677cd97b9bcc2f160dc30573582aa`; Quality gates run
  `31861408265` and Container release gate run `31861408264` passed.

### Atlas v0.9 RC1 promotion evidence — 2026-08-15

- [x] The immutable annotated tag `atlas-v0.9-rc1` (tag object
  `5ea956e3439f0b5d2fdf088962144d9b37925964`) peels to exact RC SHA
  `bc549ff6ab57d366205c1b9eb0c36fc2f7a61ba3`; HEAD and `origin/main`
  matched that SHA.
- [x] Quality gates run `31860606490` succeeded, and Container release gate
  run `31860606478` succeeded on the exact RC SHA.
- [x] `atlas-release-evidence-v1` reported `summary.status=ready`: hardened
  Compose rendering, Edge-present/Mission-Control-absent host publication,
  capability parity, secret hygiene, annotated-tag peeling, and tracked
  worktree cleanliness passed. The only allowed untracked path was
  `compose.execution-smoke.override.yaml`.
- [x] Production was rebuilt without cache from the exact RC checkout and
  deployed using only `compose.production.yaml`, `compose.https.yaml`, and
  `compose.operator-auth.yaml`. Core and Agent checkout/container checksums
  matched, the running Mission Control image matched the newly built RC image,
  and all production services remained healthy.
- [x] Recovery diagnostics for the accepted workflow were applicable, healthy,
  consistent, transition-valid, request-correlated, and fingerprint-stable,
  with `safe_next_action=none`.
- [x] The acceptance `atlas-operational-support-bundle-v1` sample was bounded,
  canonically digest-verified, untruncated, and sanitized. It contained no raw
  provider identity, environment, commands, logs, files, or upload destination.
- [x] Mission Control operational history, recovery summary, and local-only
  support-evidence preview/download passed. No retry, run-again, reconciliation,
  upload, or repository/operational-boundary bypass control was exposed.
- [x] Sequential Atlas Agent, Atlas Core, Mission Control, and Atlas Edge
  restarts passed without redispatch or provider mutation. The accepted
  workflow remained completed, verified, consistent, and terminal.
- [x] Exactly-once evidence remained unchanged before and after soak: one
  dispatch record, six ledger transitions, one barrier crossing, one provider
  operation, one dispatch result, one verification success, no new operational
  request ID, and VM 110 `qmreboot` count 3. Target fingerprint remained
  `operational-target-fingerprint-v1:1d7fdec6d423cd4936de130860d0171bed424bf695a07e82e22f734d24b6854e`.
- [x] The production mutation boundary remained exactly
  `restart-service/proxmox/qemu`. `restart-service/proxmox/lxc` remains
  unsupported: no authoritative LXC identity, selector requestability,
  translation, execution-gate entry, handler, ACL, or synthetic identity was
  added.
- [x] RC1 is selected, immutable, deployed, soaked, and accepted for final
  promotion. The final `atlas-v0.9.0` release was subsequently published at
  `7a5beac58e1677cd97b9bcc2f160dc30573582aa`.

## Atlas v0.10 implementation status

- [x] V0.10-P0 — Release-state and D9 boundary reconciliation.
- [x] V0.10-P1 — Sanitized proposal contracts and provenance.
- [x] V0.10-P2 — Derivation, compatibility, and staleness.
- [x] V0.10-P3 — Authoritative navigation contract.
- [x] V0.10-P4 — Mission Control proposal UX.
- [x] V0.10-P5 — Boundary integration, validation, and release acceptance.

P0 establishes that Discovery proposals are derived, advisory, and
non-authoritative. They cannot create candidates, action requests, approvals,
or dispatches. Any destination must freshly resolve capability, selector,
target state/fingerprint, and operator authority. V0.10 does not widen
`update-compose-stack` repository execution or the sole production operational
tuple `restart-service/proxmox/qemu`; LXC remains unsupported.

## Atlas v0.10 RC selection and sign-off

- [x] Record the exact reviewed RC candidate SHA.
- [x] Require successful Quality gates on that exact SHA.
- [x] Require successful Container release gate on that exact SHA.
- [x] Require `atlas-release-evidence-v1` status `ready` for the exact SHA/tag.
- [x] Reconfirm operational capability parity is exactly
  `restart-service/proxmox/qemu`.
- [x] Reconfirm proposal reads/navigation create no candidate, planning session,
  approval, action request, dispatch record, or provider operation.
- [x] Reconfirm executable-candidate projection rejects compatible,
  incompatible, stale, expired, hinted, and tampered proposal context.
- [x] Reconfirm stale/tampered proposals are review-only and public/UI proposal
  projections pass redaction checks.
- [x] Reconfirm Mission Control advisory UX performs no automatic selection or
  submission and reloads current destination authority.
- [x] Reconfirm exactly one production mutation tuple and no LXC capability.
- [x] Review v0.9.0-to-v0.10 upgrade, persistence, and rollback guidance.
- [x] Create the immutable v0.10 RC tag.
- [x] Complete exact-RC production deployment and restart soak.
- [x] Create and publish the final immutable `atlas-v0.10.0` tag at
  `b19ded149f65dfb4043a1b80833e5ff64d83e55d`.

### Atlas v0.10 RC1 promotion evidence — 2026-08-15

- [x] Immutable RC tag `atlas-v0.10-rc1` (tag object
  `1c8798472ce46b2aa1fc822c1613a720c62113c4`) peels to exact RC SHA
  `95d98a4d5e0e9767dd6cb5df06c7ffdb693bf162`; HEAD, `origin/main`,
  and the tag matched exactly.
- [x] Quality gates run `31863884438` and Container release gate run
  `31863884456` succeeded on the exact RC SHA.
- [x] `atlas-release-evidence-v1` returned `summary.status=ready`: hardened
  Compose render, capability parity, and secret hygiene passed; security
  findings were empty; the tracked worktree was clean; only the intentional
  untracked `compose.execution-smoke.override.yaml` was allowed.
- [x] Production was rebuilt with `--no-cache` from the exact RC checkout and
  deployed using only `compose.production.yaml`, `compose.https.yaml`, and
  `compose.operator-auth.yaml`. The smoke override was not used.
- [x] Core
  `services/atlas-core/app/services/discovery_proposals.py` and Agent
  `candidate_planning/models.py` checkout/container SHA-256 values matched;
  the running Mission Control image matched the newly built RC1 image; all
  required services remained healthy.
- [x] Live proposal list and known detail returned HTTP 200, unknown detail
  returned controlled HTTP 404, and four deterministic proposal IDs remained
  stable through restart soak. Current production proposals evaluated as
  `current / insufficient_information / compatibility_review` with
  `actionable_navigation=false`.
- [x] Proposal output exposed no authoritative target fingerprint, `vmgenid`,
  raw/provider-native identity, provider action ID, arbitrary route/URL,
  command/environment, or credential/token/cookie/CSRF material.
- [x] Incompatible, insufficient-information, warning/review, stale, expired,
  missing-source, missing-evidence, unsupported-resource, and transport-failure
  states remained inspectable and review-only without prohibited maintenance
  navigation.
- [x] Proposal context selected only a fixed destination. The maintenance
  destination independently reloaded operator session and permission,
  capability descriptors, the server-issued selector, current resources,
  requestability/state, and authoritative fingerprint. Tampered proposal,
  destination, provider, resource, target, and intent hints changed no server
  authority and triggered no submission.
- [x] Mission Control rendered bounded proposal status/reason and compatibility
  review context with an advisory authority warning. It exposed no target
  preselection, automatic submission, Execute, Run, Restart now, Approve,
  Dispatch, retry, or replay control.
- [x] Non-authority counts remained unchanged: candidates `6 → 6`, planning
  sessions `34 → 34`, approvals `55 → 55`, operational action requests
  `1 → 1`, dispatch records `1 → 1`, transitions `6 → 6`, barrier crossings
  `1 → 1`, provider operations `1 → 1`, dispatch results `1 → 1`, and
  verification successes `1 → 1`. No automatic POST occurred.
- [x] Existing request
  `operational-action-f20b14392a0a75dcfb41ec83d230845a6b0a610a29c7d142e5842c7fd827aa4b`
  remained the only operational request. Its workflow remained completed and
  terminal, the Core ledger remained verified, and verification remained
  succeeded.
- [x] VM 110 remained running; `qmreboot` count stayed `3 → 3`; authoritative
  fingerprint remained
  `operational-target-fingerprint-v1:1d7fdec6d423cd4936de130860d0171bed424bf695a07e82e22f734d24b6854e`.
- [x] Sequential Atlas Core, Mission Control, Atlas Agent, and Atlas Edge
  restarts passed. Proposal IDs/evaluations stayed stable and no redispatch or
  provider mutation occurred.
- [x] Mission Control had no host publication, Atlas Edge was the sole browser
  ingress, and production capability remained exactly one tuple:
  `restart-service/proxmox/qemu`. No LXC tuple, new intent, handler, ACL
  expansion, or proposal-derived execution authority was introduced.
- [x] RC1 is selected, immutable, exactly deployed, soaked, and accepted for
  final promotion. The immutable `atlas-v0.10.0` release was published at
  `b19ded149f65dfb4043a1b80833e5ff64d83e55d`.

## Atlas v0.11 P0 architecture sign-off

- [x] Record final `atlas-v0.10.0` release identity.
- [x] Define the Provider Management Framework — Identity-Bound Runtime Intent
  theme and P0 through P5 dependency order.
- [x] Separate provider intent, legacy/generic provider actions, operational
  dispatch, and repository execution authority.
- [x] Limit the initial provider-intent direction to Proxmox QEMU monitoring
  intent and require provider-authoritative incarnation identity binding.
- [x] Preserve QEMU VMID-reuse protection, the LXC identity NO-GO, and the
  advisory/non-authoritative Discovery proposal boundary.
- [x] Record the complete v0.11 non-goal set without changing runtime code,
  provider state, configuration, permissions, gates, handlers, ACLs, or
  production execution.

## Atlas v0.11 P2b recovery and compatibility acceptance

The accepted implementation chain is bounded by the backup-v3 contract
(`47b6ef0`), v3 creation (`f33f70c`), transactional engine (`c4d8650`),
production recovery integration (`a8390c2`), legacy-partial guard (`cef5226`),
and compatibility/lineage guidance (`b5390ba`).

- [x] Backup v3 defines an exact, complete generation for the declared managed
  Atlas Core durable-state boundary; it is not a whole-system backup and does
  not include `atlas-agent-state`.
- [x] `operational_dispatch.db` is required and validated as safety-authoritative
  no-replay state, and restored ledger evidence retains no-replay behavior.
- [x] `operator_intents.db` is required, validated, and preserved as durable
  operator authority.
- [x] `operator_sessions.db` is excluded and invalidated on v3 restore; raw
  snapshot rollback guidance also requires session invalidation while stopped.
- [x] V3 manifests bind the explicit Provider Intent generation: inactive
  backups require `provider_intents.db` absent, while activated backups require
  the validated authority store and exact legacy-import receipt. No public
  write authority is claimed.
- [x] Backup directories and artifacts enforce private `0700`/`0600`
  permissions, including secret-bearing provider connection state.
- [x] Transactional v3 restore preserves set-wide managed-state coherence,
  exact rollback on handled failure, and durable recovery evidence on
  interruption.
- [x] Restore crash recovery and the Core startup interlock fail closed while
  unresolved transaction evidence remains.
- [x] The accepted disposable recovery gate covered audit-present and
  approved-absent branches, session invalidation, Provider Intent
  pre-activation cleanup, YAML/config/secret restoration, operational-ledger
  and operator-intent preservation, unmanaged sentinel preservation, handled
  rollback, and interrupted-restore recovery without a real provider mutation.
  It explicitly guarded and did not target the production `atlas_atlas-data`
  volume.
- [x] Format v1/v2 verification compatibility remains historical
  `legacy_partial`; only v3 is complete for the declared Core boundary.
- [x] V1/v2 restore refuses any populated managed Core path or managed SQLite
  sidecar, including operational, operator-intent, session, audit, and Provider
  Intent state.
- [x] V1/v2 restore onto managed-empty state requires `--confirm` plus explicit
  `--allow-legacy-partial-new-lineage` acknowledgement and creates only a new
  partial lineage.
- [x] Safe v0.11-to-v0.10 downgrade requires paired pre-upgrade complete Core
  and Agent snapshots plus retained operational no-replay evidence; a v2 export
  is supplemental only.
- [x] Restoring v3 and then starting v0.10 is explicitly prohibited.
- [x] Re-upgrade must either resume the preserved v0.11 Core/Agent lineage or
  continue the rolled-back v0.10 lineage into a new v3 recovery point; the two
  histories are mutually exclusive and are not automatically merged.
- [x] V0.11-P2b-4 — Legacy-partial guard, recovery compatibility guidance, and
  release-acceptance closure.
- [x] V0.11-P2b-5 — `atlas-core-recovery-evidence-v1` derives bounded,
  redacted readiness from the disposable recovery, legacy compatibility,
  startup/no-replay, cleanup, and exact execution-parity checks; an artifact is
  accepted only for its exact clean candidate SHA and must be supplied
  explicitly to release evidence.
- [x] V0.11-P2b-6 — Deterministic, atomic legacy Proxmox expectation shadow
  import persists only `legacy_unbound` evidence with no resource type,
  incarnation fingerprint, activation, source-of-truth cutover, or runtime
  authority.
- [x] V0.11-P2c-3 — Activated v3 backup, verification, transactional restore,
  startup compatibility, and recovery-evidence-v2 support preserve the exact
  Provider Intent store generation and reject mixed activation lineages. The
  disposable gate covers both activation branches.
- [x] V0.11-P2c-4 — Exact candidate
  `8ea7610d9f5ce4a33e09a3a12387ee8a23160a6b` is deployed and production
  Provider Intent read authority is activated with the validated seven-record
  `legacy_unbound` import receipt. Both identity-capable QEMU resources remain
  `needs_review` with no active intent, all 11 LXC resources remain unsupported,
  and retained `policies.yaml` is no longer Proxmox monitoring authority. The
  activated v3 backup manifest is
  `b599b1dbb510bf5b313b53417d8c36282be00f3d157796d3fab6741bf7825ad6`;
  exact-SHA recovery evidence v2 is `ready` with SHA-256
  `45aa69294ef1be4514824bd438e4f1aae2ea28a8d78056b500e3c7b8df873182`.
  The pre-activation rollback bundle remains retained. This historical P2c
  read-authority checkpoint was superseded by the accepted P3 production state
  below.

## Atlas v0.11 P3 Provider Intent mutation acceptance

- [x] V0.11-P3a — Complete.
- [x] V0.11-P3b — Complete.
- [x] V0.11-P3c — Complete.
- [x] V0.11-P3d — Exact-candidate production acceptance complete.
- [x] V0.11-P3 — P3a through P3d complete. No later milestone is started or
  marked complete by this closure.
- [x] Accepted exact candidate:
  `2169fa2683ed336e1eec7e3f4febff26895fa395`.
- [x] Production Provider Intent authority remains activated on schema v2 with
  seven preserved `legacy_unbound` records and exactly two active,
  identity-bound QEMU monitoring intents. No legacy record was automatically
  rebound.
- [x] The operator explicitly selected `running` for QEMU 110 / Frigate and
  QEMU 200 / pbs; neither value was inferred from live state or legacy
  evidence. Both were bound to current provider-authoritative identities and
  confirmed `configured` by server-authoritative read-after-write at record
  version 1.
- [x] Each first binding used the dedicated P3 Provider Intent endpoint with
  `expected_record_version=0`, explicit expectation `running`,
  `acknowledge_monitoring_suppression=false`, and a unique request ID. Exact
  replay returned the original result without duplicate history.
- [x] Only intended operator `kenny` received `provider_intent:update`.
  Existing sessions were invalidated, `kenny` reauthenticated after the
  verifier change, and authenticated provider-management-v3 confirmed mutation
  capability.
- [x] Provider Intent mutation remains an authenticated monitoring-policy
  operation and grants no infrastructure execution authority. No provider
  action, operational request, execution candidate/planning/approval, or
  provider-handler invocation was created, and execution authority did not
  expand.
- [x] `policies.yaml` remains physically retained but non-authoritative for
  Proxmox monitoring. Legacy expectation PUT remains rejected while Provider
  Intent is activated, and the seven legacy records remain review/history
  evidence only.
- [x] Execution parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`.
- [x] The accepted post-mutation activated v3 backup is
  `/opt/atlas-cutover/p3d-2169fa2/post-mutation-backups/atlas-data-20260816T032919Z`
  with manifest SHA-256
  `cf90e15831bdbcf898ddda1892938d914f6bcadcddc4bffdf2ede2b155b9a397`.
- [x] `atlas-core-recovery-evidence-v3` is `ready` at
  `/opt/atlas-cutover/p3d-2169fa2/recovery-evidence/post-p3d-activated-recovery-evidence-v3.json`
  with SHA-256
  `998956ccbb56428c04f0a9ea3be0a2668ddd55f66012a925f4ba3ae4f40e04b0`.
  Disposable recovery preserved schema-v2 Provider Intent state, both active
  intent identities and versions, actor-bound audit/request/idempotency
  evidence, all seven legacy records, the import receipt, session invalidation
  and reauthentication, operational no-replay, and execution isolation.
- [x] The pre-P3 rollback anchor remains retained at
  `/opt/atlas-cutover/p3d-2169fa2/pre-p3-backups/atlas-data-20260816T030050Z`
  with paired Agent snapshot
  `/opt/atlas-cutover/p3d-2169fa2/agent-snapshots/atlas-agent-state-20260816T0301Z.tar`.
- [x] Accepted image identities: Core
  `sha256:9cd0fadf99abb4209679aa6efcb7397bfeb0e41d486a3ddac499ee382d8a9a72`,
  Agent
  `sha256:83242fbe090f45d458f6fe7d9a24c8830cebe55df0e8bea59738696a839f2f98`,
  Execution Worker
  `sha256:24b69749831dfddfdf154b819c5cf3621d494df55887a03a1c19c2cd238d0c46`,
  and Mission Control
  `sha256:feea963cc1dda442c344d626e5a97868004d75c2b6e5f5f94130869adb132605`.

## Atlas v0.11 P4 Mission Control provider experience acceptance

- [x] V0.11-P4a — Canonical provider resource and monitoring presentation,
  commit `432afe9ccf6101f7d14dd93cf90c30db7fb142eb`.
- [x] V0.11-P4b — Provider-page authority-surface separation, commit
  `5babaf105bd1530efc56a9512b093a47e37d17e3`.
- [x] V0.11-P4c — Composed provider-page, accessibility, error-state, keyboard,
  and structural-boundary acceptance complete in this closeout slice.
- [x] V0.11-P4 — P4a through P4c complete.
- [x] Public provider-management-v2 is canonical for public resource identity,
  monitoring expectation, status, reason, and legacy-review context.
  Authenticated provider-management-v3 is only the caller-specific
  mutation-readiness overlay.
- [x] Only supported, live Proxmox QEMU with authoritative identity, activated
  Provider Intent authority, write-ready schema-v2 storage, exact readiness,
  and an authenticated authorized caller exposes monitoring Save controls.
  LXC, missing resources, unavailable identity/authority/store,
  migration-required state, and unauthorized callers remain read-only.
- [x] Observed provider state and monitoring expectation are separately labeled;
  configured match, mismatch, ignored, Needs Review, replacement, missing, and
  unavailable states retain bounded textual semantics.
- [x] Replacement and legacy-review paths require a fresh explicit operator
  choice, use current identity and exact version rules, and never preselect or
  copy historical expectations.
- [x] Proxmox `policies.yaml` guest expectations remain physically retained but
  appear only as non-authoritative compatibility/history evidence; they do not
  replace current Provider Intent or automatically apply to current identities.
- [x] Diagnostics and recommendations remain non-interactive advisory surfaces.
  Compatibility actions retain only the existing provider-action API, and
  operational maintenance remains separate navigation to the authenticated
  request/candidate/planning/approval workflow.
- [x] Composed and structural UI tests prove monitoring does not invoke provider
  actions, operational requests/dispatch, candidates, planning, approval,
  Discovery proposal application, legacy expectation PUT, YAML writers, or
  automatic remediation/execution.
- [x] Execution capability parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`.

## Atlas v0.11 P5c Recovery-evidence-v3 and release acceptance

- [x] V0.11-P5c — Recovery-evidence-v3 schema formalization, exact-SHA release
  validation, idempotency and isolation regression tests, and release
  acceptance documentation complete.
- [x] V0.11-P5 — Advisory policy suggestions and release acceptance complete.
- [x] V0.11 release acceptance complete for the exact evidence-bound
  implementation SHA `f8b2c8a202ca1c7316361e0c6b0ba72ee83eb9e2`.

### Atlas v0.11-P5c implementation

- [x] `atlas-core-recovery-evidence-v3` schema defined with 12 additional v3-specific
  checks beyond v2: idempotency, replacement isolation, suggestion/Discovery/ACE
  isolation, legacy-YAML non-authority, LXC unsupported, schema-v2 preservation,
  active-record preservation, legacy-record preservation, import-receipt
  preservation, and operator-bound audit.
- [x] V3 evidence validation enforces schema/activation pairing: only
  `atlas-core-recovery-evidence-v3+activated` satisfies final exact-SHA release
  acceptance; v1/v2 evidence rejected after v3 gates.
- [x] Provider Intent Store idempotency proven: exact request replay returns
  identical outcome; no duplicate audit records, request receipts, or versions.
- [x] Incarnation rebinding isolation proven: new fingerprint creates new v1
  record; old incarnation retained in history; active coordinates atomically
  switch.
- [x] Isolation boundaries validated: Discovery/ACE/suggestion reads, UI
  rendering, and legacy-YAML authority never create or mutate Provider Intent
  records.
- [x] LXC unsupported validated: record creation fails closed; no active
  coordinate index entry.
- [x] Canonical full Atlas Core suite: 1188/1188 passed; 191 Provider Intent
  tests passed; v3 regression suite 10/10 passed. The two failures reported by
  a repository-root invocation are pre-existing working-directory-sensitive
  tests and pass canonically on both P5c and the clean baseline.
- [x] Python syntax, bash syntax, and code quality checks passed.

### Atlas v0.11-P5c exit criteria

- [x] `atlas-core-recovery-evidence-v3` recognized and enforced in release gate
- [x] Exact-SHA candidate validation with schema/activation pairing in place
- [x] V3 idempotency and replacement-isolation regression tests passing
- [x] Isolation boundaries (Discovery/ACE/suggestion/legacy-YAML) validated
- [x] Full canonical regression suite clean (1188 passed)
- [x] Documentation, CHANGELOG, and ROADMAP updates complete
- [x] Final release acceptance evidence package complete

### Atlas v0.11 final release acceptance evidence

- [x] Candidate images are pinned exactly: Atlas Core
  `sha256:e84fd994b6d83953b2dff72b97f59319dc05749e012914bf5c555b6082843bd1`,
  Atlas Agent
  `sha256:89a3b24c042528af7e6f536ecd74ea77279dfd0a666eb678191895fe255cc908`,
  Execution Worker
  `sha256:f064d56e9aec54bdc968c7a73fb966c106e99cb907084fe359c9b95bcd0cc727`,
  and Mission Control
  `sha256:e1f75f09884b634635734e9a739f85985150a9d5615fe40203a950a5ad9b73e1`.
- [x] Recovery evidence uses schema `atlas-core-recovery-evidence-v3`, status
  `ready`, and 39 ordered checks. Its SHA-256 is
  `589fb0caa12c0a996cd777e79536be6411343645dd71e4f3c20dad2a4be1e536`.
- [x] Final release evidence status is `ready`; its SHA-256 is
  `a894f51f871fb8c5c6dc961d1d5c0efb8d2e56178c99964e44052e321050c989`.
- [x] Remote Quality gates run `31980230307` completed successfully, and
  Container release gate run `31980230301` completed successfully.
- [x] Exact-SHA remote Compose validation passed: base and hardened renders
  passed, Atlas Edge is published, and Mission Control is not directly
  published.
- [x] Production read-only acceptance confirms Provider Intent schema v2,
  seven `legacy_unbound` records, two active identity-bound QEMU intents,
  QEMU 110 and QEMU 200 each `running` at version 1, zero suggestions, zero
  active LXC intents, no in-flight or outcome-unknown operational work, all
  required services healthy, and a clean restore namespace. Provider Intent is
  authoritative; `policies.yaml` is retained but non-authoritative; legacy PUT
  authority is disabled; only the intended operator retains
  `provider_intent:update`.
- [x] Production Provider Intent Store checksum is
  `285940362727efd38814d6e899d40638e0f5c8e883342aa2b622efcc25356e12`.
- [x] Execution parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`.
- [x] Bundle checksum-manifest SHA-256 is
  `6515cbaa8abe8e4cc800b98549b4aa3a9ef94cd9b705bc8b689840fdfe3c4a64`.

## Atlas v0.12 implementation closure and release acceptance

Implementation closure is evidence-bound to the commit span `d268c7d` through
`5075f1a`. The annotated `atlas-v0.12.0` release tag exists and points to the
documentation-only closure commit `c8d06a5`, which is not the tested
implementation SHA. Some publication evidence was not recorded in this
checklist; unchecked items below remain unavailable/unreconciled.

### Atlas v0.12 P0–P5 implementation

- [x] P0 — D10 architecture, source, trust, freshness, cache, conflict,
  isolation, and release boundaries defined (`d268c7d`).
- [x] P1 — Fixed dynamic-source foundation implemented for the accepted
  `frigate-github-latest-release-v1` adapter (`a00afcd`).
- [x] P2 — Atomic rebuildable cache, freshness evaluation, and bounded refresh
  coordination implemented (`2cc84cd` through `fb64243`).
- [x] P3 — Deterministic merged evidence projection and read API implemented
  (`6a744da` through `581ea50`).
- [x] P4 — Provenance and source-health UX implemented (`ea0cf5b`).
- [x] P5 — Opt-in bounded startup refresh and evidence-isolation boundary
  implemented (`b6e25f3` through `5075f1a`).
- [x] First adapter accepted as fixed, code-owned, unauthenticated,
  allowlisted HTTPS Frigate latest-release evidence with `supplemental` trust
  and `public_https_allowlisted` origin classification.

### Atlas v0.12 implementation exit criteria

- [x] Dynamic and cached facts remain read-only evidence, never authority.
- [x] Curated catalog remains always available and wins conflicts.
- [x] Refresh is opt-in and defaults false; disabled operation adds no egress.
- [x] Cache is bounded, rebuildable, offline-safe, and disposable.
- [x] Operator-managed sources, credentials, additional adapters, D11, and D12
  remain deferred.
- [x] Execution parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`.

### Atlas v0.12 release acceptance and unavailable publication evidence

- [x] Select and record the exact release SHA and create the annotated
  `atlas-v0.12.0` tag. Tag `atlas-v0.12.0` points to the documentation-only
  closure commit `c8d06a5`; the tested implementation SHA remains `5075f1a`.
- [ ] Record successful exact-SHA quality, test, Compose, recovery, and release
  gate runs.
- [ ] Record immutable candidate image digests and source/image parity.
- [ ] Record final release-evidence artifact identity and checksums.
- [ ] Record production deployment and read-only acceptance evidence.

The unchecked publication evidence remains unavailable/unreconciled. No v0.12
gate run, image digest, release artifact, or deployment acceptance is asserted
by this record; the `atlas-v0.12.0` tag exists at `c8d06a5`.

## Atlas v0.13 implementation and release status

Implementation closure is evidence-bound to the commit span `1df238c` through
`64e8341`. V0.13 was subsequently released as the immutable
`atlas-v0.13.0` release.

### Atlas v0.13 P1–P5 implementation

- [x] P1 — Discovery release evaluation implemented: a bounded, deterministic,
  side-effect-free evaluation of the authoritative baseline version against the
  freshest dynamic release evidence, exposed as an additive, optional
  `release_evaluation` property on `discovery-merged-item-v1` (`1df238c`).
- [x] P2 — Observed installed version evidence implemented: a provider-neutral,
  advisory `installed_version` observation on compatibility-context services and
  a strict numeric `X.Y.Z` comparison key (`286521b`).
- [x] P3 — Version-bounds compatibility implemented: deterministic `version`
  compatibility checks comparing an observed installed version against a
  required relationship's curated `minimum_version`/`maximum_version` bounds
  (`4fe0c23`).
- [x] P4 — Mission Control upgrade intelligence implemented: an advisory
  release-evaluation notice on the Discovery evidence panel presenting the
  bounded status, baseline, and latest candidate (`7d77bf7`).
- [x] P5 — Release isolation/readiness validation implemented: isolation tests
  proving the release-evaluation module has no I/O, network, cache, or
  application-module coupling beyond its two reviewed Discovery consumers in
  `discovery/compatibility.py` and `discovery/dynamic_projection.py` (`64e8341`).

### Atlas v0.13 implementation exit criteria

- [x] The release evaluation is read-only, derived, and additive/optional in
  `discovery-merged-item-v1`; legacy item schemas are unchanged.
- [x] It exposes exactly the eight bounded statuses
  `no_baseline`, `no_dynamic_evidence`, `insufficient_information`,
  `stale_evidence`, `conflicted`, `up_to_date`, `update_available`, and
  `baseline_ahead`, with `baseline.source` exactly `curated` or `item_version`.
- [x] A conflict always resolves to `conflicted` with `latest_candidate` `null`
  and takes precedence over `no_baseline`.
- [x] Only strict numeric `X.Y.Z` versions are comparable; a missing or
  non-strict baseline or candidate yields `insufficient_information` and never
  a positive status.
- [x] The curated catalog remains authoritative; dynamic and observed facts
  remain evidence, not authority, and never override curated data.
- [x] The Mission Control upgrade notice exposes no Apply, Execute, update,
  remediate, or other mutation control.
- [x] Release evaluation, version-bounds compatibility, and upgrade
  presentation add no execution, approval, provider-intent, or remediation
  authority.
- [x] Execution parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`; LXC remains unsupported.
- [x] The rebuildable Discovery cache remains excluded from backup v3.

### Atlas v0.8 RC1 promotion evidence — 2026-08-15

- [x] Production was rebuilt with no-cache images from the exact RC1 checkout.
- [x] Core and Agent source/image checksum parity passed, and Mission Control
  running-image parity matched the RC1 build.
- [x] The three-file deployment used `compose.production.yaml`,
  `compose.https.yaml`, and `compose.operator-auth.yaml`; Atlas Edge was the
  sole HTTPS browser ingress and Mission Control had no host-published port.
- [x] Agent, Core, Mission Control, and Atlas Edge sequential restarts passed;
  all required services remained healthy.
- [x] The completed operational workflow remained terminal and verified with
  consistent lifecycle correlation. Historical approvals remained
  non-actionable, no operational commit approval appeared, and history and
  lifecycle views remained read-only with no retry or run-again control.
- [x] Durable exactly-once evidence remained one dispatch record, six
  transitions, one dispatching/barrier transition, one provider operation, one
  dispatch result, and one verification success. VM 110 `qmreboot` count
  remained `3`; no new operational request ID appeared and the authoritative
  target fingerprint remained unchanged.
- [x] Production remained closed to exactly
  `restart-service/proxmox/qemu`; no new mutation intent or handler appeared.
  The selector remained sanitized without `vmgenid` or raw identity material,
  and private credentials and TLS material remained untracked.

## Atlas v0.8 exact-RC deployment and security checks

- [x] Render base production Compose and confirm Mission Control publishes only
  the default loopback HTTP binding.
- [x] Render the HTTPS plus operator-auth deployment and confirm Atlas Edge is
  the only host-published browser ingress while internal Mission Control routing
  remains healthy.
- [x] Confirm unauthenticated HTTPS receives the Edge authentication challenge
  and authenticated HTTPS reaches the SPA, Core API, and Agent API.
- [x] Confirm expired/unavailable sessions clear authenticated UI state;
  permission failures remain distinct; missing CSRF rotation fails closed; and
  reauthentication returns to the intended safe page.
- [x] Run `./scripts/operational-capability-parity` and require exact parity
  across Agent planning, translation and execution, plus Core execution,
  registry, and descriptor projection.
- [x] Confirm lifecycle response-model redaction tests reject credentials,
  authorization headers, cookies, CSRF, bearer tokens, raw identity,
  provider-native payloads, commands, environment data, arbitrary exceptions,
  and worker/sandbox internals.
- [x] Confirm operational history and lifecycle views remain read-only and
  expose no retry or run-again control, including ambiguous outcomes.
- [x] Confirm the production registry contains exactly one tuple:
  `restart-service / proxmox / qemu`.

## Automated gates

Generate bounded read-only RC/final provenance evidence with:

```bash
./scripts/release-evidence \
  --expected-base atlas-v0.8.0 \
  --candidate-tag atlas-v0.9-rc1 \
  --expected-sha <reviewed-commit-sha> \
  --require-main \
  --require-tag \
  --json
```

Require exit `0` and retain the JSON with the release review. Exit `1` means a
required check failed, exit `2` means required evidence is incomplete, and exit
`3` means the invocation is invalid. A green run proves only the bounded facts
reported by `atlas-release-evidence-v1`; it does not prove production soak,
container-gate completion, or human approval to create a tag. Those steps
remain explicit checklist items.

- [x] Atlas Core installs from `requirements-dev.txt`.
- [x] Atlas Core test suite passes.
- [x] Mission Control installs reproducibly with `npm ci`.
- [x] Mission Control tests, lint, and production build pass.
- [x] Production Compose configuration validates without resolving
  credential values.
- [x] Both production images build from digest-pinned bases.
- [x] Isolated containers become healthy and run as non-root users with
  read-only root filesystems, dropped capabilities, and privilege
  escalation disabled.
- [x] Mission Control, the API proxy, security headers, and SPA deep links
  pass live HTTP smoke checks.
- [x] Container-gate cleanup leaves no temporary Docker resources.
- [x] Python dependency audit reports no known vulnerabilities.
- [x] Repository scan contains no committed production credentials.

The application quality gates run in `.github/workflows/quality-gates.yml`.
The production container gate runs the same
`scripts/container-release-gate` command locally and in GitHub Actions.
Third-party actions are pinned to exact commits.

## Release artifacts

- [x] MIT license is present.
- [x] README, changelog, roadmap, architecture, deployment, and dependency
  security documentation are populated.
- [x] `.dockerignore` excludes credentials, local databases, virtual
  environments, dependencies, builds, and logs.
- [x] Tracked editor backup files are removed.
- [x] The public release identifier is consistently `Foundry`.

## Dependency security

The prior React Router RSC action CSRF exception is resolved by
`react-router-dom@7.18.2`. The final dependency review reports zero npm
vulnerabilities and no known vulnerabilities in the Core or Agent Python
requirements. The dated resolution and transitive remediation record are in
`docs/DEPENDENCY_SECURITY.md`.

## Operator approval

Complete these items immediately before tagging:

- [x] Rotate and verify any credentials exposed during pre-release
  validation.
- [x] Review deployment-specific inventory, policy, and TLS settings.
- [x] Confirm the target branch contains only intended release commits.
- [x] Run `./scripts/container-release-gate` on the release commit.
- [x] Confirm required GitHub checks pass.
- [x] Create an annotated Foundry release tag and publish release notes.

Foundry `v1.0.0` was published on 2026-07-25 from commit `b32b21d`.
Production validation reported no critical issues. The release notes record
the operator-accepted warning for unavailable or unknown Home Assistant
entities.

## Atlas v0.6 release gates

### RC1 verification artifacts

- [x] Record the exact commit checked for atlas-v0.6-rc1 packaging.
- [x] Record commands used and pass/fail status for:
  - `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-core`
  - `cd services/atlas-core && PATH=/opt/atlas/.venv/bin:$PATH python -m pytest -q`
  - `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-agent`
  - `PATH=/opt/atlas/.venv/bin:$PATH PYTHONPATH=services/atlas-agent python -m pytest -q services/atlas-agent/tests`
  - `cd services/mission-control && npm run lint`
  - `cd services/mission-control && npm test -- --run`
  - `cd services/mission-control && npm run build`
  - `./scripts/container-release-gate`

Validated on 2026-08-13 at commit
`70997b398727471d261a297e41831f5901b83a18`. Commands ran from
`/opt/atlas` unless a different working directory is shown:

| Command | Working directory | Exit | Result |
| --- | --- | ---: | --- |
| `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-core` | `/opt/atlas` | 0 | All changed-file checks passed. |
| `PATH=/opt/atlas/.venv/bin:$PATH python -m pytest -q` | `/opt/atlas/services/atlas-core` | 0 | 692 passed, 1 dependency deprecation warning. |
| `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-agent` | `/opt/atlas` | 0 | All changed-file checks passed. |
| `PATH=/opt/atlas/.venv/bin:$PATH PYTHONPATH=services/atlas-agent python -m pytest -q services/atlas-agent/tests` | `/opt/atlas` | 0 | 816 passed, 1 dependency deprecation warning. |
| `npm run lint` | `/opt/atlas/services/mission-control` | 0 | 0 errors, 1 React hook dependency warning. |
| `npm test -- --run` | `/opt/atlas/services/mission-control` | 0 | 28 files and 190 tests passed. |
| `npm run build` | `/opt/atlas/services/mission-control` | 0 | Production build passed with a chunk-size warning. |
| `./scripts/container-release-gate` | `/opt/atlas` | 0 | Compose rendering, production images, isolated hardened runtime, HTTP/HTTPS, data recovery, and Rest Server recovery passed. |

The literal Python commands were also attempted without the repository virtual
environment on this validation host. Both exited `127` because the host has no
global `python` executable. The successful commands above make the required
repository-local tool context explicit; CI supplies the equivalent Python tool
context through `actions/setup-python` and dependency installation.

### RC1 candidate execution boundary

- [x] Supported execution intent is limited to `update-compose-stack`.
- [x] Structured Compose mutation evidence is required before implementation
  approval.
- [x] Legacy planning sessions without mutation evidence are non-actionable
  and require successor planning or replanning.
- [x] Approval binding, persistence/recovery, stale/fingerprint rejection, and
  successor concurrency/idempotent reuse are validated.
- [x] Codex authentication and runtime provisioning are validated.
- [x] Codex-backed repository mutation is production-ready through the exact
  approval-gated candidate path.
- [x] A reviewed narrow seccomp/AppArmor policy or isolated execution runtime
  passes disposable workspace-write, outside-workspace denial, authenticated
  end-to-end execution, verification, review, and commit-boundary tests while
  preserving uid `10001`, `CapDrop=ALL` where applicable,
  `no-new-privileges`, and read-only rootfs.

### RC1 production execution smoke validation

Validated on commit `c333937e61343aed714a475395b41077bad86e28` using the final
production-like smoke workflow `candidate-workflow-6da0da7b4da397219e6f507ebd5439959584559529eb02a9598cdbd6a93aa866` and planning session
`candidate-plan-158f8db4f0c204de90f857ce2911cbf219dd900ae21e2b2f1a16037982baf200`.
The evidence bundle is retained at `/root/atlas-rc1-smoke-evidence/final-c333937/`.

- [x] Candidate intake, planning, candidate plan, workflow shell, shell
  approval, exact implementation approval, isolated worker execution, exact
  verification approval, deterministic RC1 verification, baseline-aware review,
  and the exact commit approval boundary were traversed successfully.
- [x] Worker execution succeeded with the worker attestation showing runtime
  uid `10001`, read-only rootfs, `no-new-privileges`, zero effective
  capabilities, and `runsc-squid` sandbox profile.
- [x] Repository HEAD remained frozen at
  `c333937e61343aed714a475395b41077bad86e28` throughout the successful
  lineage.
- [x] Exactly one approved tracked file changed:
  `services/atlas-agent/tests/test_execution_engine.py`.
- [x] The exact verification plan was persisted before approval. The gated
  RC1 zero-command verification passed without a fake or dummy command, and
  preserved repository HEAD and the validated changed-files digest.
- [x] Baseline-aware review excluded the pre-existing untracked
  `compose.execution-smoke.override.yaml`, passed with zero findings, and
  produced an exact commit approval request for branch `feature/atlas-agent`,
  the validated HEAD, and the one reviewed file.
- [x] The validation-only commit was intentionally not approved or performed.
  The marker was restored afterward and the tracked working tree is clean.
- [x] The smoke remediation set is covered by regression validation: worker
  journal exactly-once recovery, candidate audit approval-boundary projection,
  gated RC1 verification intent, baseline-aware verification, exact
  verification approval binding, candidate verification resume dispatch,
  approval-repository storage identity, AtlasCoreClient event-loop ownership,
  deterministic zero-check verification, and baseline-aware candidate review
  and commit validation.

The untracked `compose.execution-smoke.override.yaml` remains outside workflow
provenance. Recommendation: retain it as a maintained operator smoke harness
until the evidence and operator procedure are no longer needed, then remove it
through a separate reviewed cleanup decision.

## Atlas v0.7 P1.3 release-candidate readiness

### Operational capability and security boundary

- [x] Production capability is closed to `restart-service / proxmox / qemu`.
- [x] Core-owned operator sessions require authenticated HTTPS, one exact
  trusted origin, CSRF validation, and `operational_intent:create`.
- [x] Edge Basic authentication remains defense-in-depth and is not accepted as
  Core operator identity.
- [x] Agent-to-Core authentication is separate from browser authentication.
- [x] Authoritative QEMU identity and fingerprint revalidation bind planning,
  approval, dispatch, and verification.
- [x] Exact `OPERATIONAL_ACTION` approval binds the immutable action request ID,
  digest, target, provider action, verification policy, and expiry.
- [x] Core persists the dispatch barrier before provider mutation and never
  replays a crossed or ambiguous mutation boundary.
- [x] UPID-backed verification and verifier-only recovery are read-only.

### Production acceptance — 2026-08-14

- [x] Approved target: `vorex469 / VM 110 / Frigate`.
- [x] The normal operator-intent, planning, preparation-approval, exact-action
  approval, Agent dispatch, Core handler, and verification path completed.
- [x] Exactly one new `qmreboot`, one dispatching transition, one barrier
  crossing, one provider-operation capture, and one dispatch result occurred.
- [x] The production ledger reached `verified`; Agent projected the workflow as
  `completed`.
- [x] Final VM and QMP states were running and the authoritative fingerprint was
  unchanged.
- [x] No replay, sandbox path, non-production ledger, direct provider mutation,
  commit, tag, or release action occurred.

### Deployment sign-off required before an RC

- [x] Re-run and record the full Core, Agent, Mission Control, worker, Compose,
  container, dependency, and credential-hygiene gates on the final RC commit.
- [x] Push the reviewed documentation commit and require both GitHub workflows
  to pass on that exact SHA.
- [x] Document the supported
  [v0.6.0 to v0.7 upgrade and rollback](DEPLOYMENT.md#atlas-v060-to-v07-upgrade-and-rollback),
  including schema-v3 downgrade handling and in-flight dispatch preservation.
- [x] Review those v0.7 upgrade and rollback instructions and record
  release-lead sign-off.
- [x] Create an immutable RC tag only after the exact pushed SHA is green.
- [x] The final immutable `atlas-v0.7.0` tag was published at
  `8dbc43de73dda300b50c121f19324cb5174df2a9` after the documentation provenance
  fix and required CI passed on that exact final SHA.

### Final RC1 provenance and production soak — 2026-08-14

Release candidate `atlas-v0.7-rc1` resolves to
`5b1321091af0fc191844cdf71e9e0d919e4ea415`.

- [x] Quality gates run `31850208419` passed on the exact RC SHA: `atlas-core`,
  `atlas-agent`, and `mission-control` all succeeded.
- [x] Container release gate run `31850208435` passed on the exact RC SHA.
- [x] Dependency Graph run `31850211284` passed on the exact RC SHA.
- [x] Production was rebuilt from the exact RC1 checkout with no-cache images
  and deployed using only `compose.production.yaml`, `compose.https.yaml`, and
  `compose.operator-auth.yaml`. The untracked
  `compose.execution-smoke.override.yaml` was not used.
- [x] Running Core and Agent source checksums matched the RC1 checkout, and the
  running Mission Control image identity matched the exact RC1 build.
- [x] Sequential restarts of Atlas Agent, Atlas Core, Mission Control, and Atlas
  Edge passed; all production services were healthy afterward.
- [x] The completed operational workflow remained terminal, and the production
  ledger remained unchanged with exactly one historical barrier crossing, one
  historical provider operation, one historical dispatch result, and no
  replay.
- [x] VM 110's `qmreboot` count remained `3`, and its authoritative target
  fingerprint remained unchanged throughout the redeploy and soak.
- [x] Operator-auth private files remained untracked, and the trusted origin
  remained exactly `https://atlas.internal`.
- [x] Agent and Core execution gates remained exactly `restart-service`; the
  production registry remained exactly one tuple:
  `restart-service / proxmox / qemu`.

### Post-hardening RC1 execution validation

Validated on commit `0bddaf6ee46fbef94a2a1eb9f20cfcb1db0ca2be` using a fresh
isolated production-like stack, planning session
`candidate-plan-fa0a537f0715ad4f607287801dc6345e8b3f87ead146f0abb611a962ba6bd75e`,
and workflow
`candidate-workflow-783edad93fa08cf30c039b92fa94db0098b7431e170a37ee57c864adef28417d`.

- [x] Authenticated Agent-to-worker execution traversed the segmented relay.
- [x] Worker execution succeeded with uid `10001`, read-only rootfs,
  `no-new-privileges`, zero effective capabilities, and the
  `runsc-squid+atlas-workspace` sandbox profile.
- [x] Exactly `services/atlas-agent/tests/test_execution_engine.py` changed,
  with patch digest
  `sha256:8a97f55e972fadfe5d2e0a3d49456b38a057be61794da862ee4ad00c36e2455f`.
- [x] Exact zero-check verification passed, review approved with zero findings,
  and the machine-readable audit chain validated without a failure code.
- [x] The workflow stopped at `awaiting_commit_approval`; commit approval
  `approval-commit-candidate-workflow-783edad93fa08cf30c039b92fa94db0098b7431e170a37ee57c864adef28417d`
  remains pending and no validation-only commit was created.
- [x] The validation marker was restored and the isolated stack, volumes, and
  locally built smoke images were removed. The retained smoke override was not
  modified.

### RC1 Python lint baseline

The blocking RC1 Ruff gate checks Python files changed after commit
`0216b7bfe7f3b160a762269802aa34244ae70a72`, including untracked Python files,
using the pinned Ruff version in each service's development requirements. Core
checks `services/atlas-core/app`; Core has no separate `tests/` directory. Agent
checks both `services/atlas-agent/app` and `services/atlas-agent/tests`. Changed
production and test files must pass: no new Ruff violation may be introduced by
RC1 changes. Existing documented debt does not block RC1 by itself and remains
tracked for later cleanup rather than being fixed as release scope.

A fresh repository-wide informational scan with the validated toolchain on
2026-08-13 reports exactly 90 Core findings and 20 Agent findings. The Agent
count supersedes the earlier 18-finding observation; do not use the older
expected count of 22 unless it is independently reproduced.

The commands above show the repository-local virtual environment used for local
release validation. CI installs the same development requirements into the
Python environment supplied by `actions/setup-python`, so its equivalent
commands intentionally use `python` without the local `.venv` path prefix.

### Manual release sign-off

- [x] Release lead confirms changelog entry names the intended tag and scope.
- [x] Rollback path and restore procedures are reviewed and approved for this RC.
- [x] Operator confirms the upgrade and post-upgrade smoke verification
  procedure was reviewed.
- [x] Release blocker list is empty for the following:
  - no auto-approve, no auto-execute,
  - no push, tag, release publication, remote deploy, and no rollback automation.
- [x] Operator sign-off and date are recorded in release notes or issue tracker:
  - Sign-off name: Kenny Horner
  - Sign-off date: 2026-08-13
  - Release candidate commit: `0c7fde2c233799453948a81fd42b53717524f4c1`

- [x] Changelog, version, tag name, upgrade notes, and manual rollback notes are
  reviewed.
- [x] Use an immutable RC tag that does not overwrite existing release tags.
  `atlas-v0.6-rc1.9` was published at
  `6d85df5b112b4bde28ec31fc60cce88560c9dbfc` on 2026-08-13 and remains the
  immutable validated RC baseline.

### Atlas v0.6.0 final release

Authorized final tag candidate: `atlas-v0.6.0`.

- [x] Record the exact final integration commit SHA:
  `2d4a1b1929316589cdf6ea96993442b430826f10` on `main`.
- [x] Run and record the complete final technical validation. The local
  validation matrix and both required CI workflows are green.

The final local validation matrix was recorded on 2026-08-13 at
`d4abb0016f95aab3bee7ef7ce7820fb3fd941388`. Commands ran from `/opt/atlas`
unless a different working directory is shown:

| Command | Working directory | Exit | Result |
| --- | --- | ---: | --- |
| `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-core` | `/opt/atlas` | 0 | Baseline-aware Core Ruff passed. |
| `PATH=/opt/atlas/.venv/bin:$PATH python -m pytest -q` | `/opt/atlas/services/atlas-core` | 0 | 692 passed; 1 accepted dependency deprecation warning. |
| `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-agent` | `/opt/atlas` | 0 | Baseline-aware Agent Ruff passed. |
| `PATH=/opt/atlas/.venv/bin:$PATH PYTHONPATH=services/atlas-agent python -m pytest -q services/atlas-agent/tests` | `/opt/atlas` | 0 | 816 passed; 1 accepted dependency deprecation warning. |
| `npm ci` | `/opt/atlas/services/mission-control` | 0 | Clean install passed; 284 packages installed. |
| `npm audit --package-lock-only --audit-level=high` | `/opt/atlas/services/mission-control` | 0 | Zero vulnerabilities. |
| `npm run lint` | `/opt/atlas/services/mission-control` | 0 | 0 errors; 1 accepted hook warning. |
| `npm test -- --run` | `/opt/atlas/services/mission-control` | 0 | 28 files and 190 tests passed. |
| `npm run build` | `/opt/atlas/services/mission-control` | 0 | Production build passed with the accepted 681.92 kB chunk warning. |
| `/opt/atlas/.venv/bin/python -m pip_audit -r services/atlas-core/requirements.txt` | `/opt/atlas` | 0 | No known vulnerabilities. |
| `/opt/atlas/.venv/bin/python -m pip_audit -r services/atlas-core/requirements-dev.txt` | `/opt/atlas` | 0 | No known vulnerabilities. |
| `/opt/atlas/.venv/bin/python -m pip_audit -r services/atlas-agent/requirements.txt` | `/opt/atlas` | 0 | No known vulnerabilities. |
| `/opt/atlas/.venv/bin/python -m pip_audit -r services/atlas-agent/requirements-dev.txt` | `/opt/atlas` | 0 | No known vulnerabilities. |
| `docker compose --env-file /dev/null -f compose.production.yaml config --no-interpolate --quiet` | `/opt/atlas` | 0 | Production Compose render passed. |
| `docker compose --env-file /dev/null -f compose.production.yaml -f compose.https.yaml config --no-interpolate --quiet` | `/opt/atlas` | 0 | Production plus HTTPS Compose render passed. |
| `./scripts/data-recovery-gate` | `/opt/atlas` | 0 | Tamper rejection, backup, retention, restore, and persistence passed. |
| `./scripts/container-release-gate` | `/opt/atlas` | 0 | Images, isolated runtime, worker hardening, Codex sandbox, HTTP/HTTPS, recovery, and Rest Server gates passed. |
| `git grep -nF '# Atlas RC1 validation smoke marker.' -- .` | `/opt/atlas` | 1 | Expected: validation marker absent from tracked files. |
| `git diff --check` | `/opt/atlas` | 0 | Passed. |

The isolated container gate verified the worker runtime hardening, Codex
`atlas-workspace` write proof, and outside-workspace mutation denial. The
published RC baseline remains immutable: `atlas-v0.6-rc1.9` resolves to
`6d85df5b112b4bde28ec31fc60cce88560c9dbfc`. The local operator harness
`compose.execution-smoke.override.yaml` remained intentionally untracked and
outside release provenance.

- [x] Confirm required CI checks passed on exact validated integration commit
  `2d4a1b1929316589cdf6ea96993442b430826f10`:
  - Quality gates: SUCCESS, GitHub Actions run `31753221630`.
  - Container release gate: SUCCESS, GitHub Actions run `31753221621`.
  - Both required workflows passed on that exact SHA. Together with the local
    matrix above, the complete final technical validation is green.
- [x] Re-review dependency and accepted-advisory status for the final release.
  npm reports zero vulnerabilities, all four Python requirement audits report
  no known vulnerabilities, and no accepted security advisory remains.
- [x] Confirm the final tracked tree contains only intended release files and
  that local-only smoke artifacts remain outside release provenance.
- [x] Record final operator/release-lead sign-off name and date:
  - Sign-off name: Kenny Horner
  - Sign-off date: 2026-08-13
- [x] Confirm `atlas-v0.6.0` was unused before final tag preparation on
  2026-08-13. It must still be reconfirmed immediately before tag creation.
- [x] The immutable annotated `atlas-v0.6.0` tag was published at
  `03c1e03099b0f638dc674235312a3b3e70768c2f` after the required CI passed on
  that final documentation SHA.

### Core

- [x] `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-core`
- [x] `cd services/atlas-core && PATH=/opt/atlas/.venv/bin:$PATH python -m pytest -q`
- [x] Execution candidate, planning-intake, and route-contract tests pass.
- [x] API/OpenAPI contract regression is current.

### Atlas Agent

- [x] `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-agent`
- [x] `PATH=/opt/atlas/.venv/bin:$PATH PYTHONPATH=services/atlas-agent python -m pytest -q services/atlas-agent/tests`
- [x] End-to-end candidate workflow test passes.
- [x] Audit-chain validator tests pass.
- [x] Restart-recovery matrix tests pass.
- [x] Concurrency and idempotency tests pass.
- [x] Commit-path security tests pass.
- [x] Roadmap workflow regression tests pass.

### Mission Control

- [x] `cd services/mission-control && npm run lint`
- [x] `cd services/mission-control && npm test -- --run`
- [x] `cd services/mission-control && npm run build`
- [x] UI does not imply unsupported Phase 3 execution controls.

### Security and release operation

- [x] Approval-boundary review confirms exact immutable implementation, verification, and commit approvals.
- [x] No automatic approval, automatic execution, push, tag, release, remote deploy, or rollback path is enabled.
- [x] No secrets, logs, `jcode/`, local state, dependency folders, virtual environments, or generated builds are committed.
- [x] State migration and restart-recovery tests pass.
- [x] Docker or Compose smoke validation passes when deployment packaging is in scope.
- [x] `git diff --check` passes.
- [x] `git status --short` is clean except explicitly local-only ignored directories before tagging.
- [x] Review docs for RC tag/sequence selection before creating the next release tag.
