# Changelog

This project is under active development. Entries describe significant
operator-visible changes; Git tags remain the source of truth for exact
release boundaries.

## Unreleased

#### v0.35 P0–P4 — Execution Permission Grant Boundary

- Selected Atlas v0.35 **Execution Permission Grant Boundary** and froze the
  documentation-only [v1 planning
  contract](docs/architecture/execution-permission-grant-v1.md).
- Defined one operator-owned append-only permission-evidence artifact binding
  the exact v0.20–v0.33 linkage, v0.34 review/audit fingerprints,
  authenticated operator, exact confirmation text, trusted short expiry, and
  permanent subject/idempotency reservations.
- Froze a dedicated `installation.execution.permission.grant` permission, one
  exact guarded POST, one owned GET, and one Mission Control confirmation and
  readback panel. The grant permits only later execution-admission
  consideration; it does not admit or authorize execution.
- Defined closed grant/status/result/error/audit models, two-state derived
  lifecycle, domain-separated fingerprints, same-owner recomputation,
  confirmation/redaction rules, exact API/UI boundaries, P0–P5 sequencing,
  threats, Home Assistant golden, later enablement, and must-not-change rules.
- P0 changes planning documents only. It adds no models, service, store,
  permission registration, route, UI, persistence, migration, credential or
  network access, Agent call, retry/resend, installation, execution, dispatch,
  worker/workflow/process start, Docker/Podman/shell, mutation, deployment,
  rollback, tag, push, publication, or release action.
- P1 adds strict immutable create, authority, linkage, grant, lifecycle/status,
  idempotency, permanent reservation, audit, redacted-error, and result models;
  deterministic domain-separated fingerprints; and pure owner, permission,
  exact-confirmation, v0.20–v0.34 linkage, 30-second freshness, expiry, and
  Home Assistant blocked-golden validation. It adds no service, API, UI,
  persistence, migration, Agent/runtime call, mutation, or execution authority.
- P2 adds an explicitly constructed Core-local service and bounded append-only
  SQLite store over injected owner-scoped v0.34 evidence. Atomic durable grant,
  audit, and permanent idempotency/review-subject reservations provide
  restart-safe owned create/get/list, exact-duplicate zero-reader readback,
  quotas, corruption checks, derived lifecycle, and redacted failures without
  persisting raw idempotency keys or adding a route, UI, Agent/network call,
  execution, dispatch, retry/resend, workflow/worker, or mutation consumer.
- P3 registers only the owner-scoped candidate collection `GET`/guarded `POST`
  and owned item `GET`, with independent create/read permissions, strict
  body/query/idempotency parsing, origin/CSRF/rate gates, redacted errors, and
  a locked OpenAPI surface. An independent durable database setting is
  validated, while service construction remains injected because no
  production v0.34 evidence reader is authorized. No UI or effect route is
  added.
- P4 adds the Mission Control panel in the v0.34 readiness-review context. Its
  strict client uses only the P3 collection create/list and item get surface;
  its two-step confirmation displays the exact frozen statement and says the
  write creates durable permission evidence only. Readback presents lifecycle,
  30-second inherited freshness/expiry, complete v0.20–v0.34 linkage and
  fingerprints, authenticated ownership, permanent reservation/no-replay,
  audit evidence, redacted failures, fixed-false authority, and the blocked
  Home Assistant golden without polling, sensitive data, effect controls, or
  any mutation outside the single grant-evidence POST.

#### v0.34 P0 — Installation Readiness Review

- Selected Atlas v0.34 **Installation Readiness Review** and froze the
  documentation-only [v1 planning
  contract](docs/architecture/installation-readiness-review-v1.md).
- Defined one authenticated owner-scoped Core GET and one read-only Mission
  Control page over a strict projection of the complete v0.20–v0.33 chain,
  with exact linkage/fingerprints, a closed blocker vocabulary, deterministic
  redacted audit evidence, and only `blocked` or `readiness_gated` outcomes.
- `readiness_gated` always retains `execution_admission_not_defined`; the
  review grants no approval, admission, authorization, installation, dispatch,
  execution, worker/workflow, mutation, deployment, rollback, retry, or replay
  authority.
- P0 changes planning documents only. It adds no models, readers, service,
  route, UI, persistence, credential access, Agent/network call, runtime
  behavior, Home Assistant artifact, migration, tag, push, release, or
  deployment.
- P1 added strict immutable Core linkage, fourteen-item evidence summary,
  readiness, blocker, audit, redacted-error, response/result, and injected
  pure-evaluation models. It enforces exact v0.20–v0.33 identity binding,
  owner/authentication context, freshness/expiry interpretation, deterministic
  domain-separated fingerprints, bounds, fixed-false authority, redaction,
  and the blocked Home Assistant golden, with no service, route, UI, store,
  external I/O, or runtime behavior.
- P2 added the explicitly constructed read-only Core review service over an
  injected owner-scoped local evidence reader and trusted UTC clock. It
  enforces authentication, permission, ownership, exact linkage/fingerprints,
  freshness/blockers, deterministic results, redacted non-disclosing errors,
  and the blocked Home Assistant golden without persistence, reservation,
  credential access, Agent/network calls, retry/replay, or effect authority.
- P3 exposed exactly one authenticated owner-scoped Core GET for the frozen
  readiness review. It accepts only the canonical candidate path, no query or
  body, uses the existing read permission without CSRF mutation semantics,
  returns only closed review/audit or redacted-error bodies, and adds no
  collection, action, mutation, install, execute, dispatch, retry/resend, or
  deployment route.
- P4 added one strictly parsed, credentialed GET client and one read-only
  Mission Control candidate-record readiness page. It presents the two frozen
  states, ordered blockers, complete v0.20–v0.33 summary, linkage/fingerprints,
  freshness, owner context, audit evidence, redacted errors, fixed-false
  authority, and the blocked Home Assistant golden, with no polling, mutation
  call, raw sensitive data, or effect control.
- P5 closed v0.34 with Core and Mission Control release-isolation guards for
  the exact GET-only surface, no-effect service, fixed-false authority,
  exclusive read-only v0.20–v0.33 evidence consumption, sensitive-data and
  effect-control absence, Agent isolation, and blocked/non-artifact Home
  Assistant golden. P1–P5 are complete with no migration, tag, push, release,
  deployment, or runtime authority expansion.

#### v0.33 P0–P5 — End-to-End Inert Delivery Receipt

- Selected Atlas v0.33 **End-to-End Inert Delivery Receipt** and froze the
  documentation-only [v1 planning
  contract](docs/architecture/end-to-end-inert-delivery-receipt-v1.md).
- Defined the exact internal Core request, closed Agent-result verification,
  append-only Core receipt, complete v0.20–v0.32 linkage, deterministic
  fingerprints, inherited 30-second freshness, lifecycle, ownership,
  permanent no-replay/ambiguity, redaction, and audit evidence.
- Froze reuse of the exact v0.32 envelope/result and single Agent POST, exact
  v0.31 HTTPS/principal/credential-reference boundary, independent default-off
  gates, no public Core API or Mission Control surface, P0–P5 scope, threats,
  goldens, later enablement, blockers, and must-not-change contracts.
- P0 changes planning documents only. It adds no models, service, store,
  transport, credential read, network call, route, UI, retry, installation,
  Docker/Podman/shell/process work, worker/workflow/dispatch, mutation,
  deployment, rollback, Home Assistant artifact, tag, push, or release action.
- P1 added strict immutable Core request, receipt-copy, verification, receipt,
  linkage, lifecycle/status, audit, redacted-error, idempotency, fingerprint,
  freshness, bounds, and fixed-false authority models.
- P2 added the explicitly constructed Core verification service and bounded
  append-only owner-scoped receipt store with permanent reservation-first
  no-replay, exact duplicate reads, quotas, restart readback, and fail-closed
  corruption handling. It added no route, transport, or production consumer.
- P3 added the independently default-off one-shot internal composition through
  injected v0.31 transport, credential, and prior-receipt dependencies. It
  sends only the inert v0.32 envelope, preserves terminal ambiguity and zero
  retry, and adds no public Core route or production registration.
- P4 keeps Mission Control absent as frozen. Structural tests lock out every
  v0.33 client, type, hook, component, page, route, navigation, read/mutation,
  verification/polling, retry/resend/send/admit/effect control, sensitive
  rendering, and Home Assistant exception. No API bridge or runtime behavior
  is added.
- P5 closes release isolation with explicit internal-only composition, exact
  duplicate zero-I/O behavior, append-only durable and secret-free evidence,
  fixed-false authority, and zero installation, workflow, worker, dispatch,
  provider/repository/in-guest mutation, deployment, rollback, or replay-
  bypass consumer. Core live send remains one-shot; Agent intake remains
  admission-only; public Core and Mission Control surfaces remain absent; Home
  Assistant remains blocked without a deployment artifact. P5 adds tests and
  release documentation only.
- P5 validation passed both Ruff gates, all 3107 Core tests, all 1045 Agent
  tests, all 555 Mission Control tests, lint, production build, and
  `git diff --check`. The existing frontend hook and chunk-size warnings
  remained non-errors.

#### v0.32 P0–P5 — Agent Live Intake Admission

- Selected Atlas v0.32 **Agent Live Intake Admission** and froze the
  documentation-only [v1 planning
  contract](docs/architecture/agent-live-intake-admission-v1.md).
- Defined the exact inert outer envelope, Agent admission/acknowledgement/
  result/record schemas, complete v0.20–v0.31 causal linkage, deterministic
  fingerprints, inherited 30-second freshness, same-owner validation,
  permanent no-replay, lifecycle, redaction, and audit evidence.
- Froze one default-off production Agent POST, fixed-Core-principal
  authentication through an injected mode-0400 credential reference, strict
  HTTPS/body/response bounds, exact internal OpenAPI, and no Mission Control or
  public Core surface.
- Froze P0–P5 scope, threats, goldens, exact evidence-only authority, later
  enablement, remaining blockers, and must-not-change contracts. V0.31's
  reserved attempt is admission input; Agent admission/result/acknowledgement
  are causally upstream of the v0.31 Core receipt and cannot require it.
- V0.32 P0 changes planning documents only. It adds no runtime registration,
  service, store, route, credential read, Agent call, retry, installation,
  Docker/Podman/shell/process work, worker/workflow/dispatch, mutation,
  deployment, rollback, Home Assistant artifact, tag, push, or release action.
- P1 added strict immutable Agent-local envelope, v0.20–v0.31 linkage,
  authentication, admission, acknowledgement, result, receipt/record, audit,
  error, idempotency, lifecycle, fingerprint, freshness, bounds, and
  fixed-false authority models.
- P2 added an explicitly constructed default-off admission service and bounded
  append-only owner-scoped store with permanent reservation-first no-replay,
  exact replay, restart readback, quotas, and fail-closed corruption handling.
- P3 added the sole independently default-off production Agent POST with exact
  HTTPS/source/path/method, mode-0400 credential reference, bounded streaming,
  strict parsing, closed responses, and exact internal OpenAPI. It adds no
  effect route or execution authority.
- P4 keeps Mission Control absent as frozen. Structural tests lock out every
  v0.32 client, hook, component, page, route, navigation, read/mutation call,
  admit/retry/resend/send-again or effect control, sensitive rendering, and
  Home Assistant exception. No Core bridge or runtime behavior is added.
- P5 closes the boundary with exact default-off single-route registration,
  concurrent one-envelope no-replay, append-only restart-safe evidence,
  secret-free persistence/log/error locks, fixed-false effect authority, zero
  installation/workflow/worker/dispatch/mutation/deployment consumers, Core
  one-shot/no-retry preservation, absent Mission Control, capability parity,
  and Home Assistant blocking. P5 adds tests and release documentation only.
- P5 validation passed both Ruff gates, 61 focused Core isolation tests, 5
  focused Agent closure tests, all 3072 Core tests, all 1045 Agent tests, and
  550 Mission Control tests plus lint/build. The existing frontend hook and
  chunk-size warnings remained non-errors.

#### v0.31 P0–P5 — Live Delivery Send Boundary

- Selected Atlas v0.31 **Live Delivery Send Boundary** and froze the
  documentation-only [v1 planning
  contract](docs/architecture/live-delivery-send-boundary-v1.md).
- Defined the exact one-shot operator request, unchanged v0.27 wire request,
  Agent result/admission/acknowledgement, complete v0.20–v0.30 linkage,
  fingerprints, append-only attempt/receipt lifecycle, inherited 30-second
  freshness, permanent reservation/no-replay, ownership, redaction, audit,
  transport authentication and bounded credential-reference contract.
- Froze independent default-off Core send and Agent route registration, exact
  three-route Core and one-route Agent surfaces, Mission Control confirmation,
  P0–P5 scope, threats, goldens, authority, later enablement, remaining
  blockers, and must-not-change contracts.
- V0.31 P0 changes planning documents only. It adds no send, route, credential
  read, transport, Agent call, installation, Docker/Podman/shell/process work,
  worker/workflow/dispatch, mutation, deployment, rollback, retry daemon,
  Home Assistant artifact, tag, push, publication, or release action.
- P1 added closed immutable live-send request, attempt, receipt, lifecycle,
  audit, redacted-error, transport-envelope, linkage, fingerprint, freshness,
  endpoint, credential-reference, idempotency, ambiguity, and fixed-false
  authority models.
- P2 added the explicitly constructed default-off Core reservation service and
  append-only owner-scoped durable store with permanent no-replay, restart
  readback, quotas, bounds, and fail-closed corruption handling.
- P3 added the injected one-shot Core HTTPS/credential boundary, permanent
  reservation before I/O, bounded closed Agent response validation, terminal
  ambiguity, and append-only receipt/result/acknowledgement/audit evidence. It
  adds no install, execution, worker, workflow, deployment, or mutation power.
- P4 keeps Mission Control absent because P3 exposes no guarded Core live-send
  API or UI-facing read model. Structural tests lock out every v0.31 client,
  type, page, route, navigation, mutation, retry/resend/send-again control,
  secret or raw transport rendering, prohibited authority label, and Home
  Assistant exception. No API bridge or runtime behavior is added.
- P5 closes the release boundary with explicit/default-off/one-shot locks,
  permanent no-replay and ambiguity handling, secret-free durable evidence,
  fixed-false effect authority, zero workflow/worker/dispatch/provider/
  repository/in-guest/install/deploy/rollback consumers, dormant test-only
  Agent intake, absent Mission Control surface, capability parity, and Home
  Assistant blocking. P5 adds tests and release documentation only.
- P5 validation passed both Ruff gates, 60 focused Core isolation tests, 10
  focused Agent intake-closure tests, all 3071 Core tests, all 1020 Agent
  tests, and 545 Mission Control tests plus lint/build. The existing frontend
  hook and chunk-size warnings remained non-errors.

#### v0.30 P0–P5 — Operator-Controlled Delivery Enablement

- Selected Atlas v0.30 **Operator-Controlled Delivery Enablement** and froze
  the documentation-only [v1 planning
  contract](docs/architecture/operator-controlled-delivery-enablement-v1.md).
- Defined exact closed create/linkage/record/result/status/error/audit schemas,
  fixed operator-confirmation wording, owner/authz rules, inherited v0.29
  freshness/expiry, permanent idempotency/no-replay, redaction, default-off
  API/UI boundaries, P0–P5 scope, threats, goldens, and must-not-change rules.
- V0.30 P0 changes planning documents only. Delivery activation, Agent calls,
  transport/credential loading, dispatch, worker/workflow/runtime/process work,
  installation, provider/repository/in-guest mutation, deployment, rollback,
  enablement consumption, and Home Assistant artifacts remain prohibited.
- P1 added closed immutable models, canonical domain-separated fingerprints,
  fixed confirmation and authority fields, lifecycle derivation, and pure
  same-owner v0.20–v0.29 linkage validation.
- P2 added the explicitly constructed evidence service and bounded append-only
  owner-scoped store with permanent atomic reservations, exact retry/no-replay,
  quotas, restart durability, and fail-closed corruption handling.
- P3 added only guarded create/list/item-read Core routes with dedicated
  permissions, mutation protections, strict parsing/bounds, ownership
  isolation, sanitized errors, and exact OpenAPI/method limits.
- P4 added strict Mission Control parsing and evidence-only creation/review of
  lifecycle, expiry, linkage, fingerprints, audit, and fixed-false authority.
- P5 locks concurrency and permanent no-replay, zero downstream consumers,
  exact Core and Mission Control surfaces, capability parity, and Home
  Assistant's blocked state. P5 adds tests and release documentation only.

#### v0.29 P0–P5 — Controlled Delivery Activation Preflight

- Selected Atlas v0.29 **Controlled Delivery Activation Preflight** and froze
  the documentation-only [v1 planning
  contract](docs/architecture/delivery-activation-preflight-v1.md).
- Defined exact closed request, result, linkage, decision, reason, lifecycle,
  fingerprint, ownership/authz, freshness/expiry, idempotency/no-replay,
  redaction/audit, default-disabled API/UI, and P0–P5 contracts binding the
  complete same-owner v0.20–v0.28 evidence chain.
- V0.29 P0 adds no runtime behavior. Delivery activation, Agent requests,
  transport/route registration, credential/secret loading, worker/workflow/
  dispatch/runtime/process execution, provider/repository/guest mutation,
  installation, deployment, rollback, and Home Assistant artifacts remain
  prohibited.
- P1 added closed immutable models, canonical fingerprints, pure lifecycle and
  complete injected same-owner v0.20–v0.28 linkage validation.
- P2 added the explicitly constructed evaluator and bounded append-only,
  owner-scoped durable evidence store with permanent atomic reservations,
  exact retry/no-replay, quotas, and fail-closed readback.
- P3 added only authenticated, authorized create/list/item-read Core routes
  with mutation protections, strict parsing/bounds, redaction, ownership
  isolation, and default-absent production service construction.
- P4 added strict Mission Control API parsing and temporary, non-authorizing
  preflight status/linkage/audit review plus an evidence-only confirmation; it
  adds no activation, delivery, execution, installation, or deployment control.
- P5 locks zero downstream consumers across Core and Agent, exact OpenAPI and
  UI/mutation surfaces, append-only/no-replay posture, capability parity, and
  Home Assistant's blocked state. P5 adds tests and release documentation only.

#### v0.28 P0–P5 — Dormant Core-to-Agent Delivery Wiring

- Froze and completed the Dormant Core-to-Agent Delivery Wiring v1 contract:
  closed immutable Core configuration, request/preparation, response-
  validation, audit, idempotency, result, and redacted-error models bind the
  exact same-owner v0.20–v0.27 evidence chain and server-owned Core time.
- Added the explicitly constructed fixed-disabled no-send client and bounded
  append-only preparation store. It may prepare one immutable `not_sent`
  request, perform owned readback, and validate one directly injected closed
  Agent result; it has no send, transport, credential-loading, execution,
  mutation, worker, workflow, deployment, or rollback capability.
- Locked endpoint and authentication-reference shape validation without file
  reads, credential material, Authorization rendering, DNS, sockets, TLS,
  HTTP, network libraries, Agent invocation, or production construction.
- Production Core and Agent app/container/settings/API paths have no v0.28
  client, factory, store, route, credential, consumer, listener, workflow,
  worker, provider/repository/guest mutation, candidate execution, or replay
  bypass. The v0.27 Agent intake route remains dormant and test-only.
- Mission Control has no v0.28 type, client, mutation, route, navigation,
  control, evidence rendering, or prohibited action label. Home Assistant
  remains blocked, non-installable, non-executable, and has no deployment
  artifact.
- P5 validation passed both Core and Agent Ruff gates, 92 focused Core
  isolation/dormant-wiring tests, 1,016 Agent tests, 522 Mission Control tests,
  Mission Control lint/build, and `git diff --check`. P5 adds tests and release
  documentation only; it performs no migration, tag, push, release, or deployment.

#### v0.27 P0–P5 — Real Agent Intake Boundary

- Froze and completed the Real Agent Intake Boundary v1 contract: immutable
  closed request, admission, acknowledgement, result, audit, validation, and
  redacted-error models bind the exact same-owner v0.20–v0.26 evidence chain,
  operator identity, and server-owned Agent intake time.
- Added the explicitly constructed, default-disabled evidence service and
  bounded append-only store with exact idempotency, one-envelope no-replay,
  quotas, restart durability, owned reads, and fail-closed corruption and
  ambiguous-reservation behavior.
- Added one dormant test-only `POST /api/v1/internal/installation-intake`
  factory. Production Agent app/container/settings paths do not register it,
  and production Core has no delivery, transport, listener, worker, workflow,
  execution, mutation, deployment, rollback, or replay-bypass consumer.
- Locked authentication, authorization, HTTPS, JSON/header/body bounds,
  duplicate-key and unknown-field rejection, linkage/freshness, redaction,
  fixed-false authority, and absence of install/run/execute/deploy/dispatch/
  deliver/start-workflow/runtime sibling surfaces.
- Mission Control has no v0.27 type, client, mutation, route, navigation,
  control, evidence rendering, or prohibited action label. Home Assistant
  remains blocked, non-installable, non-executable, and has no deployment
  artifact.
- P5 validation passed both Ruff gates, 41 focused Core release-isolation
  tests, 1,016 Agent tests, 517 Mission Control tests, Mission Control lint and
  production build, and `git diff --check`. Lint retained one pre-existing
  exhaustive-deps warning and the build retained its existing chunk-size
  advisory; neither was an error. P5 adds tests and release documentation only.

#### v0.26 P0–P5 — Simulated Core-to-Agent Handoff Delivery

- Selected Atlas v0.26 **Simulated Core-to-Agent Handoff Delivery** and froze
  the documentation-only [v1 planning
  contract](docs/architecture/simulated-handoff-delivery-v1.md).
- Defined exact closed Core simulated-delivery, immutable attempt-evidence,
  and Agent simulated-acknowledgement schemas binding the same-owner v0.20
  candidate, v0.21 intent, v0.22 validation evidence, v0.23 request, v0.24
  envelope, and v0.25 intake record by exact IDs and fingerprints.
- Froze freshness and lifecycle, one-delivery/one-intake/one-acknowledgement
  idempotency and no-replay, ambiguous-copy reconciliation, operator ownership,
  request identities, redaction/audit evidence, default-disabled no-surface
  posture, authority limits, P0–P5 scope, and must-not-change contracts.
- V0.26 P0 changes planning documentation only. It adds no runtime behavior,
  route, command, UI, store, transport, Docker/Podman/container-runtime call,
  shell/process execution, provider/repository/in-guest mutation, workflow,
  worker execution, installation, deployment, rollback, Home Assistant
  artifact, migration, tag, push, publication, or release.
- The release may later simulate delivery only through an explicitly
  constructed in-process coordinator and preserve non-authorizing evidence.
  Live authenticated transport, receipt/admission, atomic consumption,
  execution authority, runtime work, and all target mutation remain blocked.
- Completed the closed models, canonical fingerprints, lifecycle derivation,
  bounded Core attempt/acknowledgement-copy stores, explicit coordinator,
  Agent acknowledgement adapter, exact v0.25 intake reuse, restart durability,
  quotas, ownership, exact retry/no-replay, reconciliation, redaction, and
  offline synthetic goldens.
- P4 keeps Mission Control absent because the frozen contract defines no
  production UI-facing route or read model. Structural tests lock out every
  v0.26 client, mutation, page, route, navigation, control, evidence rendering,
  and prohibited install/run/execute/deploy/dispatch/deliver/send-to-Agent/
  start-workflow/rollback label.
- P5 closes production isolation across Core and Agent. V0.26 evidence is not
  consumed by HTTP/OpenAPI, commands, app/container registration, settings,
  network transport, workers, workflows, candidate execution, provider/
  repository/in-guest mutation, deployment, rollback, or replay bypass. All
  authority remains fixed false and readback remains direct, owned, in-process
  store access.
- Home Assistant remains blocked, non-installable, and non-executable with no
  deployment artifact. P5 adds no runtime behavior, authority, migration, tag,
  push, release, or deployment.
- P5 validation passed both Ruff gates, 43 focused Core isolation/closure
  tests, 983 Agent tests, 513 Mission Control tests, Mission Control lint/build,
  and `git diff --check`. Lint retained one pre-existing exhaustive-deps
  warning and the build retained its existing chunk-size advisory; neither was
  an error.

#### v0.25 P0–P5 — Agent Intake Simulation

- Selected Atlas v0.25 **Agent Intake Simulation** and froze the
  documentation-only [v1 planning
  contract](docs/architecture/agent-intake-simulation-v1.md).
- Defined the exact closed simulated-intake input and immutable Agent evidence
  record binding every required v0.20–v0.24 identity and fingerprint under one
  authenticated operator and one distinct simulation request identity.
- Froze the `simulated`/terminal `expired` lifecycle, 30-second maximum local
  freshness window, one-simulation-per-envelope idempotency/no-replay rules,
  redaction/audit evidence, default-disabled posture, and P0–P5 plan.
- V0.25 P0 changes planning documentation only. No Agent/Core route, command,
  UI, transport, runtime call, store, worker, workflow, Docker/Podman/shell/
  process execution, provider/repository/guest mutation, installation,
  deployment, rollback, Home Assistant artifact, migration, tag, push,
  publication, or release is added.
- The release may later validate only explicitly injected bytes and preserve
  simulation evidence; authentic delivery, live admission, atomic consumption,
  execution approval, runtime behavior, and every external mutation remain
  blocked.
- Completed the closed immutable models, pure injected validation, bounded
  append-only simulation evidence store, atomic idempotency/no-replay
  reservations, restart durability, quotas, owned readback, and sanitized
  failures.
- P3 locks simulation intake to explicit in-process construction only. Agent
  OpenAPI, commands, application container, settings, Core clients, workers,
  workflows, providers, repositories, and runtime adapters expose or consume
  no v0.25 surface; only the isolated evidence store may mutate its configured
  store path.
- P4 locks Mission Control to no v0.25 presentation because the frozen
  contract exposes no UI-facing read model. Structural Mission Control and
  cross-service tests prove there is no v0.25 API client, route, navigation,
  mutation call, install/intake/delivery control, execution-suggesting label,
  simulation evidence rendering, or sensitive intake detail. Home Assistant
  remains blocked, non-installable, and non-executable with no deployment
  artifact.
- P4 validation passed 509 Mission Control tests, Mission Control lint/build,
  the Agent Ruff gate, 968 Agent tests, and `git diff --check`; lint reported
  one pre-existing exhaustive-deps warning and no errors.
- P5 closes the release with release-wide isolation, regression, authority,
  no-replay, owned-readback, capability-parity, and Home Assistant blocked-
  golden tests. Production Core and Agent paths cannot consume v0.25 records;
  Agent HTTP/OpenAPI, CLI/shell, container/settings registration, worker,
  workflow, runtime, provider/repository/guest mutation, candidate execution,
  deployment, rollback, and replay-bypass surfaces remain absent.
- Mission Control remains free of v0.25 API clients, mutations, routes,
  navigation, controls, prohibited action labels, and evidence rendering.
  `install-container` remains unsupported and default-disabled, and Home
  Assistant remains blocked with no deployment artifact. P5 adds no runtime
  behavior, authority, migration, tag, push, release, or deployment.
- P5 validation passed both Core and Agent Ruff gates, 35 focused Core
  release-isolation tests, 969 Agent tests, 509 Mission Control tests, Mission
  Control lint/build, and `git diff --check`. Lint retained one pre-existing
  exhaustive-deps warning and the build retained its existing chunk-size
  advisory; neither reported an error.

#### v0.24 P0–P5 — Installation Dispatch Handoff

- Selected Atlas v0.24 **Installation Dispatch Handoff** and froze the
  documentation-only [v1 planning
  contract](docs/architecture/installation-dispatch-handoff-v1.md).
- Defined an immutable, operator-owned, non-delivered Core envelope binding
  the exact v0.20 candidate, v0.21 approval, v0.22 validation evidence, and
  v0.23 execution-request identities and fingerprints.
- Froze the exact closed envelope and contract-only Agent intake/admission
  shapes, `prepared`/terminal `expired` lifecycle, 60-second maximum lifetime,
  atomic one-envelope-per-request idempotency/no-replay, ownership, redaction,
  audit evidence, default-disabled API/UI, and P0–P5 plan.
- V0.24 P0 grants only local validation and future preparation of evidence:
  no live Agent intake or Core-to-Agent invocation, worker dispatch,
  Docker/Podman/shell/process execution, provider/repository/guest mutation,
  workflow, install, deployment, rollback, or Home Assistant artifact.
- Completed the closed models and pure validation, bounded append-only store,
  authenticated default-disabled preparation-only create/list/item-read API,
  and Mission Control immutable evidence-preservation and review surface.
- Added P5 structural locks proving no Core or Agent invocation/HTTP consumer,
  dispatch delivery, worker, workflow, provider/repository/in-guest mutation,
  candidate execution, deployment, rollback, or replay bypass consumes a
  v0.24 handoff record.
- Locked Core to the intended guarded create/list/get lifecycle surface and
  Mission Control to two reads plus the one explicit record-only create, with
  no prohibited authority controls, navigation, labels, or mutation calls.
- Reconfirmed both five-field authority sets remain fixed false, the feature
  and service remain default-disabled and non-delivering/non-executing, and
  Home Assistant remains blocked with no deployment artifact.
- Trusted transport, fresh execution approval, live admission, atomic consume/
  no-redelivery, execution-time proof, runtime/recovery/audit, deployment, and
  rollback remain blocked.

#### v0.23 P0–P5 — Installation Execution Request Boundary

- Selected Atlas v0.23 **Installation Execution Request Boundary** and froze
  the documentation-only
  [v1 planning contract](docs/architecture/installation-execution-request-v1.md).
- Defined a closed, immutable, operator-owned Core record binding the exact
  v0.20 candidate, v0.21 approval intent, and complete fresh v0.22 request,
  validation, and audit-evidence fingerprints. Its derived states are only
  `recorded` and terminal `expired`; every authority field is false.
- Froze strict same-owner linkage, freshness/expiry, atomic multi-identity
  reservation, exact-replay behavior, no-replay ambiguity rules, append-only
  ownership, redaction, audit evidence, default-disabled API/UI boundaries,
  P0–P5 scope, must-not-change contracts, and golden cases.
- V0.23 P0 adds no runtime behavior, Core route, store, UI, Agent/worker call,
  Core-to-Agent dispatch, process/shell/Docker/Podman execution, provider/
  repository/guest mutation, workflow, installation, deployment, rollback,
  Home Assistant artifact, migration, tag, push, publication, or release.
- Completed the closed models and validation, bounded append-only store,
  authenticated default-disabled record-only create/list/item-read API, and
  Mission Control explicit evidence submission and immutable review surface.
- Added P5 structural locks proving no Core or Agent invocation, dispatch,
  worker, workflow, provider/repository/in-guest mutation, deployment,
  rollback, candidate execution, or replay-bypass path consumes a v0.23
  record. Core exposes only guarded create/list/get, and Mission Control has no
  prohibited authority control, navigation, label, or mutation outside the
  explicit record-creation call.
- Reconfirmed all five authority fields are fixed false, the feature and
  service remain default-disabled and non-executing, and Home Assistant stays
  blocked, non-installable, and non-executable with no deployment artifact.
- P5 validation passed both requested Ruff gates, 233 focused Core tests, 948
  Agent tests, 499 Mission Control tests, Mission Control lint/build, and
  `git diff --check`. P5 added tests and release documentation only; no
  migration, tag, push, publication, deployment, or release action occurred.

#### v0.22 P0–P5 — Agent Install-Container Contract

- Selected Atlas v0.22 **Agent Install-Container Contract** and froze the
  documentation-only
  [v1 planning contract](docs/architecture/agent-install-container-contract-v1.md).
- Defined the exact validation-only request/result schemas, existing-QEMU
  subject, mandatory v0.20 candidate and v0.21 approval fingerprints,
  digest-pinned single-container artifact, rootless runtime boundary,
  filesystem/network/resource limits, idempotency, no-replay, sanitized
  errors, audit evidence, threat model, and P0–P5 scope.
- `install-container` remains unsupported and default-disabled. No Core route,
  Core-to-Agent dispatch, worker, install, provider/repository/guest mutation,
  runtime invocation, Home Assistant deployment, tag, push, release, or
  deployment is added.
- Added isolated strict immutable Agent request, validation, audit-evidence,
  and redacted-error models with the complete v0.20/v0.21 proof identity,
  fixed runtime/filesystem/network/resource bounds, canonical JSON parsing,
  and deterministic domain-separated fingerprints. Every authority field is
  fixed false and no model has a production consumer.
- Added the pure proof/linkage validator and an explicitly composed local-only
  dry-run service that returns only closed validation evidence or sanitized
  redacted errors. It has no HTTP route, application-container registration,
  persistence, Core client, runtime, network, filesystem, or execution adapter.
- Added a closed, static `install-container` capability diagnostic to the
  existing Agent information response and a read-only Mission Control
  presentation of its unsupported, default-disabled posture, fixed runtime,
  filesystem, and network bounds, and blocked Home Assistant golden. With no
  production validation-result read model, the UI shows an explicit empty
  state and adds no Core bridge, result fetch, control, navigation, or mutation.
- Added presentation-only coverage for closed validation status, proof and
  evidence fingerprints, artifact references, audit evidence, and redacted
  errors. Validation is explicitly not installation, execution approval,
  dispatch, deployment, rollback, replay, or mutation permission.
- Added P5 structural locks proving no Core, dispatch, worker, workflow,
  provider/repository/in-guest mutation, deployment, rollback, candidate
  execution, or no-replay path consumes a v0.22 validation record. Agent keeps
  only its static diagnostic and isolated pure validator, with no runtime or
  command route; Mission Control adds no prohibited control, navigation, or
  mutation call. Home Assistant remains blocked and non-installable.
- P5 validation passed the requested Core and Agent Ruff gates, focused Core
  release-isolation tests, the full Agent suite, Mission Control tests/lint/
  build, and `git diff --check`. No runtime behavior, migration, tag, push,
  publication, deployment, or release action was added or performed.

#### v0.21 P0–P5 — Installation Approval Intent

- Completed the closed contract, isolated bounded append-only store,
  authenticated create/list/item-read API, and explicit Mission Control
  confirmation and immutable evidence review for one exact owned active v0.20
  non-executable candidate identity.
- Added P5 structural locks proving no Core or Agent authority/mutation path
  recognizes approval intents; OpenAPI exposes only the intended three-route
  surface; and Mission Control performs only append, list, and get calls with
  no prohibited control or navigation.
- Reconfirmed approval intents are immutable operator-scoped evidence only,
  Home Assistant remains non-approvable and non-executable, Agent
  `install-container` remains unsupported, and backup v3 remains closed.
- Approval intent remains evidence only: it is not execution authorization and
  has no consumer, state transition, revocation, workflow, dispatch, Agent,
  worker, provider, repository, guest, deployment, rollback, or replay path.
- P5 validation passed Core and Agent Ruff, 38 focused Core tests, 912 Agent
  tests, 485 Mission Control tests, Mission Control lint/build, and
  `git diff --check`. No migration, tag, push, publication, deployment, or
  release action was performed.

#### v0.20 P0–P5 — Installation Candidate Record Lifecycle

- Completed the closed immutable envelope, bounded operator-scoped durable
  store, authenticated preserve/list/get/delete API, and Mission Control
  lifecycle review. `active` means only unexpired source facts; every stored
  authority field remains false.
- Added P5 isolation locks proving no v0.20 envelope is consumed by Core or
  Agent approval, execution, dispatch, worker, workflow, provider, repository,
  in-guest, deployment, rollback, or replay paths. OpenAPI exposes only the
  intended lifecycle routes, and Mission Control is limited to preserve,
  review, and delete.
- Home Assistant remains v0.19 `not_admitted` and cannot be preserved. Backup
  v3 remains closed and excludes the independent advisory database; explicit
  operator maintenance is required.
- Added no runtime authority, migration, backup widening, Agent
  `install-container`, tag, push, publication, deployment, or release action.

#### v0.19 P0–P5 — Installation Candidate Admission

- Completed the pure fail-closed admission evaluator, bounded ephemeral
  candidate record, authenticated GET-only Core projection, and read-only
  Mission Control review. The sole positive result remains
  `admitted_but_non_executable` with every authority field false.
- Added P5 isolation locks across v0.16–v0.19 and every Core/Agent production
  consumer, plus OpenAPI and Mission Control source locks against candidate
  creation, approval, workflow, dispatch, execution, worker, provider,
  repository, or in-guest mutation consumption.
- Home Assistant remains `not_admitted`: `compose/home-assistant.yaml` is absent
  and Atlas Agent does not support `install-container`.
- Added no runtime authority, migration, backup widening, tag, push,
  publication, deployment, or release action.

#### v0.18 P0–P5 — Installation Capability Assessment

- Completed the bounded Proxmox/QEMU provider-fact adapter, deterministic
  comparison, authenticated GET-only Core assessment, and read-only Mission
  Control review. Even the strongest assessment remains non-authorizing.
- Added P5 isolation locks proving the v0.16 InstallationPlan and v0.17
  selection/admission contracts remain non-authorizing and no v0.18 record is
  consumed by candidate, approval, workflow, dispatch, Agent, worker,
  provider, repository, or in-guest mutation paths.
- Froze OpenAPI to the sole v0.18 route
  `GET /api/v1/installation/capability-assessments/{item_id}/{selection_id}`;
  Mission Control exposes no prohibited control, navigation, or mutation call.
- Home Assistant remains blocked by absent `compose/home-assistant.yaml`, and
  Atlas Agent continues to reject unsupported `install-container`; no runtime
  authority, migration, backup widening, tag, push, or release was added.

#### v0.17 P0–P5 — Prospective Installation Destination Assessment

- Completed authenticated enumeration and immutable, operator-scoped selection
  of one exact server-observed Proxmox QEMU existing-guest incarnation, with
  exact re-resolution, 24-hour expiry, terminal cancellation/staleness, bounded
  concurrency, and sanitized durable tombstones.
- Added one five-minute, non-durable `install-container-assessment` interest and
  a deterministic non-authorizing Core assessment. The exact routes are
  `GET /api/v1/installation/destinations`, `POST /api/v1/installation/destination-selections`,
  `GET` and `DELETE /api/v1/installation/destination-selections/{selection_id}`,
  and `POST /api/v1/installation/admission-assessments`.
- Added the Mission Control prospective-destination selection and assessment
  review surface. Its copy explicitly denies install/planning authority and it
  exposes no candidate, workflow, Agent, approval, or dispatch control.
- Locked the Home Assistant golden as blocked: the absent
  `compose/home-assistant.yaml` keeps InstallationPlan status
  `missing_deployment_artifact` and fingerprint
  `34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a`,
  followed by destination-capability-unknown and Agent-unsupported reasons.
- Preserved `candidate_created=false`, `planning_allowed=false`, `candidate=null`;
  Agent still does not support `install-container`; no provider, repository,
  workflow, approval, operational action, dispatch, worker, or execution
  authority was added.

#### v0.17-P1 conformance correction

- Recorded an explicit P0 normative amendment for exact `resource_id`
  participation in immutable selection identity, non-retrograde terminal
  timestamps, and the closed restricted-JCS fingerprint subset. The historical
  P0 commit remains unchanged and the amendment grants no new authority.

#### v0.17-P0 — Prospective Installation Destination Assessment architecture

- Froze the documentation-only, decision-complete
  [v1 contract](docs/architecture/prospective-installation-destination-v1.md)
  for an operator-scoped, immutable, expiring selection of one exact observed
  Proxmox QEMU guest incarnation and an ephemeral non-authorizing admission
  assessment.
- Froze exact identity/re-resolution, movement invalidation, lifecycle,
  idempotency, deterministic fingerprints, reason precedence, guarded future
  API, Mission Control terminology, storage/restore, dependency isolation, and
  P0–P5 acceptance boundaries.
- Home Assistant remains `missing_deployment_artifact` at
  `34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a`;
  candidate projection remains false/false/null. No runtime, route, store, UI,
  test, migration, persistence implementation, Agent, candidate, workflow,
  provider, worker, execution, commit, tag, or push change is included.

#### v0.16.0 — Grounded Installation Planning release closure

- Completed P0 through P5 for deterministic, immutable, provenance-linked,
  ephemeral `InstallationPlan v1` reads answering what would be required to
  install an item at the current item-scoped boundary.
- Preserved deterministic JCS/NFC SHA-256 fingerprints, evidence provenance,
  freshness, compatibility, prerequisites, blockers, risks, missing facts, and
  required operator confirmations. The fixed-clock Home Assistant golden
  remains `missing_deployment_artifact` at
  `34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a`.
- Released only the bounded server-owned read path at
  `GET /api/v1/discovery/items/{item_id}/installation-plan` and a complete
  read-only Mission Control review. Neither surface has an install, execute,
  approve, deploy, dispatch, candidate-creation, or confirmation-acceptance
  control.
- Completed the pure fail-closed projection toward existing
  `ExecutionCandidate` admission. It preserves the complete plan and exact
  fingerprint but creates no candidate because v1 has no approved target
  identity and Atlas Agent has no supported installation intent.
- P5 validation passed focused Core Ruff and pytest gates, 156 directly
  affected Core candidate/route tests, the full 911-test Atlas Agent suite,
  Mission Control's 54-file/440-test suite, lint, build, and exact operational
  capability parity. Broad Core validation was exercised through the practical
  managed-sandbox boundary; restricted ownership/thread behavior was not
  treated as a production defect.
- V0.16 adds no Docker/subprocess/network mutation, worker or queue execution,
  operational dispatch, automatic approval, Provider Intent/workflow mutation,
  hidden persistence, synthesized approved target, or synthesized installation
  intent. Atlas v0.16 does not install Home Assistant; that authority remains a
  future-release contract.

#### v0.16-P3/P4 — Read-only review and fail-closed candidate projection

- Completed the bounded InstallationPlan GET API and read-only Mission Control
  review without action controls.
- Added a deterministic, non-persistent projection toward the existing
  `ExecutionCandidate` admission boundary. It preserves the complete plan and
  exact fingerprint but creates no candidate because InstallationPlan v1 has no
  approved target and Atlas Agent has no supported installation intent.
- The projection creates no session, workflow, approval, queue item, dispatch,
  replay identity, Provider Intent mutation, or execution authority. Home
  Assistant remains `missing_deployment_artifact` at fingerprint
  `34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a`.
- Closure validation passed Ruff; 16 projection tests; 343 InstallationPlan
  tests; 90 discovery/parity regressions; 78 execution-candidate
  model/projection/eligibility tests; 31 execution-candidate service tests; 60
  Core route/operator-intent tests; and 434 Atlas Agent
  candidate-planning/approval/workflow tests. P0 through P4 are complete; P5 is
  next.

#### v0.16-P1/P2 — InstallationPlan contract and evaluator

- Implemented and accepted the deterministic, immutable InstallationPlan
  contract, assembler, and evaluator while preserving the frozen P0 relations.
  Coverage closes evidence precedence and freshness, provenance, compatibility,
  prerequisite and image projection, status precedence, hostile inputs,
  isolation, and authority boundaries.
- Accepted the Home Assistant golden fingerprint
  `34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a` and
  fixed duplicate risks produced from multiple qualifying evidence records.
- Historical P1/P2 acceptance validated 254 InstallationPlan tests and 90
  required discovery/parity regressions (344 combined). At that historical
  milestone, P3 was next and P4–P5 remained future work.
- InstallationPlan grants no execution, mutation, approval, dispatch,
  persistence-writer, workflow-mutation, Provider Intent mutation,
  acquisition, queue, worker, or network authority.

#### v0.16-P0 — InstallationPlan contract and threat model

- Completed documentation-only P0 and froze the normative
  [InstallationPlan v1 contract](docs/architecture/installation-plan-v1.md):
  exact closed schema, six statuses, blocker vocabulary and total precedence;
  JCS/NFC SHA-256 fingerprint; provenance, freshness and conflict rules;
  item-scoped-only target decision; failure/threat models; legacy/dependency
  isolation; and the complete P1–P5 validation matrix.
- Closed the final P0 contract gaps with a bounded raw-evidence adapter model,
  exhaustive evidence-decision relation, valid-only nullable evidence values,
  closed catalog and compatibility decision/provenance inputs, and a fully
  typed fingerprint schema with total sorting and domain-separated identities.
- Froze evidence classification and internal identity emission precedence,
  curated release-claim projection, bounded compatibility evidence IDs,
  canonical primitives and overflow-safe age range, exhaustive image and
  prerequisite projection, and typed assumption/confirmation production; no
  unreachable target-ambiguity runtime state remains.
- Amended P0 to freeze the exact domain-separated `Fingerprint.value`
  derivation, every prerequisite description template, and every confirmation
  prompt template; all remain deterministic, presentation-only where
  applicable, and non-authorizing.
- Amended P0's closed risk vocabulary to the two deterministic, reachable
  producers `evidence_approaching_expiry` and `compatibility_warning`; removed
  the speculative `artifact_content_change` and target-dependent
  `environment_variance` runtime values and froze severity, subject,
  confirmation, ordering, and fingerprint behavior for every remaining risk.
- P0 adds no plan implementation, API, UI, test, runtime configuration,
  persistence, approval, target, mutation, execution, or authority.

#### v0.16 planning selected — Grounded Installation Planning

- Selected P0 → P5 planning for deterministic, immutable,
  provenance-linked, ephemeral informational `InstallationPlan` read models.
  This records the historical selection-time state: P0 was then complete as
  documentation/architecture and P1–P5 were pending.
- Froze `plan_ready_for_review`, `insufficient_information`, `incompatible`,
  `conflicted`, `stale_evidence`, and `missing_deployment_artifact` as the exact
  closed v1 status vocabulary and froze the total blocker mapping.
- Froze precedence so conflict cannot resolve to
  readiness, successful image grounding cannot override a missing required
  deployment artifact, and absent optional context cannot erase known
  incompatibility; the normative contract contains the complete table.
- Required the Home Assistant case to fail closed as
  `missing_deployment_artifact` because its exact binding target,
  `compose/home-assistant.yaml`, is absent. Image grounding is not deployment
  readiness, and no substitute artifact or mutable image may be inferred.
- Kept plans read-only and non-persistent and the new operator path GET-only;
  P0 subsequently selected item-scoped-only v1 with no target selector.
- Isolated legacy caller-document `POST /analysis/deployments` and
  `POST /api/v1/analysis/deployments` from v0.16; neither will be expanded,
  reused, or converted into an InstallationPlan path.
- Added no code, test, CI, runtime/Compose, authority, candidate, intent,
  approval, workflow, dispatch, repository, worker, command, credential, or
  release-publication change.

## atlas-v0.15.0 — Atlas v0.15.0 (2026-08-25)

#### v0.15-P0–P5 — Grounded image identity and provenance operator surface

Atlas v0.15 has the theme **Deployment Image Grounding Operator Surface**.
P0 through P5 and production acceptance are complete. Atlas v0.15.0 is
released as the immutable `atlas-v0.15.0` tag at
`850480ce6c5f86a5bf4a783e33f7e08a7f29a2ab`.

- The milestone dependency order is P0 → P1 → P2 → P3 → P4 → P5.
- The selected surface is read-only and informational: it presents the
  released v0.14 image grounding and provenance to the operator and derives
  no new authority from presentation.
- Initial evidence breadth is the accepted Home Assistant `2026.8.3`
  registry-attested proof only.
- Non-goals: no generic collectors, no startup, scheduled, or request-time
  collection, no execution authority, no automatic remediation, and no
  Discovery-to-dispatch coupling.
- Capability parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`; LXC remains unsupported.
- P1 implemented a deterministic, fail-closed, binding-driven local read-only
  model
  reusing existing Compose observation, accepted evidence, and
  `ground_deployment_image`, with provenance preserved and no acquisition,
  persistence, mutation, or execution.
- P2 implemented the additive, bounded, redacted GET-only Core projection at
  `GET /api/v1/discovery/items/{item_id}/image-grounding`. It has no mutation
  sibling, Agent dependency,
  provider mutation, persistence, or proposal/candidate/workflow creation;
  OpenAPI and route-isolation tests are required.
- P3 implemented an advisory Mission Control status/provenance surface
  that distinguishes `REGISTRY_ATTESTED` from `CURATED`, displays fail-closed
  states, and offers no action or workflow conversion.
- P4 completed the authoritative security/isolation/authority validation matrix,
  including proof of absence of startup,
  scheduled, and request-time acquisition. A GET consumes only already-accepted
  local evidence and reviewed local readers and cannot trigger GHCR access,
  registry acquisition, Sigstore verification, collector execution, or
  evidence refresh. P4 also proves mutation/execution separation, redaction,
  source conflict handling, and all unchanged authority, approval, no-replay,
  worker, and maintenance contracts.
- P5 completed focused/full component validation, capability parity,
  exact-SHA CI/container gates, read-only production acceptance,
  collector-inactivity verification, documentation reconciliation, rollback
  guidance, and release closure.

The reviewed Home Assistant reference is release `2026.8.3`, image
`ghcr.io/home-assistant/home-assistant`, digest
`sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe`,
source class `REGISTRY_ATTESTED`. Registry-attested evidence is informational;
it is not deployment approval, authorization, install readiness, or execution
authority.

## atlas-v0.14.0 — Atlas v0.14.0 (2026-08-24)

Atlas v0.14.0 is released as the immutable `atlas-v0.14.0` tag at
`4d2526e1b022c5c36eaced65bf5b71703da5d2d7`. RC1 at `4abace1` exposed a
Mission Control asynchronous test race; the test-only fix produced the final
release commit, also selected by RC2. Quality gates and the container release
gate succeeded on that exact final commit.

#### Added

- `DeploymentBinding` connects a curated catalog item to one exact repository
  Compose file and service without granting access to arbitrary source
  configuration.
- Image grounding composes an exact repository Compose-image observation with
  accepted image-release evidence. The resulting grounding and evidence
  provenance projection are read-only and informational.
- The image-release evidence loader accepts reviewed, immutable evidence rows;
  reviewed promotion preserves the `REGISTRY_ATTESTED` source class rather than
  converting registry proof into `CURATED` knowledge.
- Repository Compose-image observation reads the bound image from the reviewed
  repository boundary without adding a route, collector activation, or
  execution path.
- The trusted collector boundary supports bounded GHCR acquisition and offline
  Sigstore verification for one reviewed fixed proof case: Home Assistant
  `2026.8.3`. Its Sigstore trust root is repository-owned and hash-pinned.
- The accepted Home Assistant proof integrates as `REGISTRY_ATTESTED` evidence,
  then participates in read-only grounding composition and provenance
  projection.

#### Security and authority boundary

`acquisition != verification != accepted evidence != grounding != operational authority`

- Acquisition is bounded retrieval, verification is offline cryptographic
  evaluation, accepted evidence is immutable knowledge, and grounding is an
  informational composition. None grants operational authority.
- The collector remains inactive in production. Production collector
  registries remain empty, and there is no scheduled or startup collection.
- V0.14 adds no update, pull, restart, or deploy authority. It does not change
  the existing operational or repository execution boundaries.
- `REGISTRY_ATTESTED` and `CURATED` remain distinct trust classes. Accepted
  registry evidence is never silently promoted to curated authority.

## atlas-v0.13.0 — Atlas v0.13.0 (2026-08-21)

Atlas v0.13 has the theme **Compatibility/Upgrade Intelligence**. It turns the
already-released v0.12 dynamic Discovery facts into bounded, read-only upgrade
intelligence: a deterministic release evaluation for each merged item, observed
installed-version evidence, version-bounds compatibility checks, and Mission
Control upgrade presentation. The immutable `atlas-v0.13.0` release is
published; implementation completed at `64e8341` before its release closure.

#### Added

- P1 discovery release evaluation: a bounded, deterministic, side-effect-free
  evaluation of the authoritative baseline version against the freshest dynamic
  release evidence for each `discovery-merged-item-v1` projection, exposed as an
  additive, optional `release_evaluation` property.
- P2 observed installed version evidence: a provider-neutral, advisory
  `installed_version` observation on compatibility context services and a strict
  numeric `X.Y.Z` comparison key, so a missing or malformed version is unknown
  and never yields a positive assertion.
- P3 version-bounds compatibility: deterministic `version` compatibility checks
  comparing an observed installed version against the curated
  `minimum_version`/`maximum_version` bounds of a required relationship,
  fail-closed to `insufficient_information` when a version is not strict
  numeric `X.Y.Z`.
- P4 Mission Control upgrade intelligence: an advisory release-evaluation
  notice on the Discovery evidence panel presenting the bounded status,
  baseline, and latest candidate with no Apply, Execute, update, or remediate
  control.
- P5 release isolation/readiness validation: isolation tests proving the
  release-evaluation module has no I/O, network, cache, or application-module
  coupling beyond its two reviewed Discovery consumers.

#### Security and authority boundary

- The release evaluation is read-only upgrade intelligence. It is derived, not
  persisted; it adds no Provider Intent, policy, proposal, approval, provider
  action, or execution authority.
- The curated catalog remains authoritative. The baseline is the curated
  release version when present (`baseline.source=curated`), otherwise the item
  version (`baseline.source=item_version`). Dynamic and observed facts remain
  evidence, not authority, and never override curated data.
- Discovery remains `GET`-only and read-only. `release_evaluation` is additive
  and optional in `discovery-merged-item-v1`; legacy item schemas are
  unchanged.
- Capability parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`. LXC remains unsupported. The rebuildable
  Discovery cache remains excluded from backup v3.

## atlas-v0.12.0 — Atlas v0.12.0 (2026-08-19)

Implementation is complete at `5075f1a`. The annotated `atlas-v0.12.0` release
tag points to the documentation-only closure commit `c8d06a5`, which is not
the tested implementation SHA.

#### Added

- P1 fixed, code-owned `frigate-github-latest-release-v1` source foundation
  with bounded unauthenticated allowlisted HTTPS retrieval.
- P2 atomic rebuildable cache, freshness and offline evaluation, source health,
  conflict handling, and bounded refresh coordination.
- P3 deterministic merged Discovery evidence read API in which curated claims
  remain authoritative and dynamic/cached facts remain supplemental evidence.
- P4 Mission Control provenance, freshness, conflict, and source-health
  presentation with curated-only fallback.
- P5 opt-in, default-off bounded startup refresh via
  `ATLAS_ENABLE_DISCOVERY_DYNAMIC_REFRESH`, with isolation tests preserving the
  evidence-not-authority boundary.

#### Security and authority boundary

- Dynamic Discovery adds no Provider Intent, policy, proposal, approval, or
  execution authority. Capability parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`.

## atlas-v0.11.0 — Atlas v0.11.0 (2026-08-17)

The annotated `atlas-v0.11.0` release tag points to the exact evidence-bound
implementation SHA `f8b2c8a202ca1c7316361e0c6b0ba72ee83eb9e2`. The later
documentation-only release-acceptance closure remains commit
`375db0a883bd100de21d2deabaa118be48c1e057` and is not the tested binary or
recovery-evidence SHA.

#### Added

- `atlas-core-recovery-evidence-v3` schema with 12 additional v3-specific checks
  beyond v2, binding exact-SHA mutation-state proof to identity-bound Provider
  Intent incarnation boundaries.
- V3 evidence validation enforces that only exact-SHA evidence with schema/activation
  pairing (v3+activated) satisfies final release acceptance for identity-bound
  provider-intent mutation.
- V3 regression test suite covering Provider Intent idempotency, replacement
  isolation, Discovery/ACE/suggestion isolation, and legacy-YAML non-authority.
- Recovery gate v3 verification branch with seeded fixture demonstrating active
  identity-bound records, legacy evidence preservation, mutation receipt,
  and audit operator-binding.
- Identity-bound Provider Intent authority for supported Proxmox QEMU resources,
  with schema-v2 durable mutation, audit, and idempotency records.
- Authenticated explicit mutation and a coherent Mission Control authority
  presentation separating observed state, monitoring intent, diagnostics,
  provider actions, and operational maintenance.
- Advisory suggestions that require explicit Review and Save; suggestions never
  apply automatically or cause remediation.
- Backup/recovery-v3 preservation of active identity-bound intent, legacy
  records, import receipts, mutation evidence, and audit evidence.

#### Validation

- Provider Intent Store mutation idempotency: exact request replay returns
  identical outcome without duplicate audit records.
- Incarnation rebinding: new fingerprint creates new v1 record; old incarnation
  retained in history but superseded in active coordinates.
- Isolation boundaries: Discovery/ACE/suggestion reads, UI rendering, and
  legacy-YAML authority never create or mutate Provider Intent records.
- LXC unsupported: record creation fails closed; no active coordinate entry.
- LXC remains unsupported for identity-bound Provider Intent. V0.11 adds no
  automatic remediation and no execution expansion; capability parity remains
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`.
- Canonical Atlas Core regression suite: 1188/1188 passed. The separately
  reported 1184/1186 root invocation was traced to two pre-existing
  working-directory-sensitive tests that pass from the canonical Core
  directory on both the P5c tree and clean baseline.

#### Exit criteria

- [x] `atlas-core-recovery-evidence-v3` recognized and enforced
- [x] Exact-SHA candidate validation with schema/activation pairing
- [x] V3 idempotency and replacement-isolation proven
- [x] Isolation boundaries validated
- [x] Full regression suite clean
- [x] Documentation and release evidence package complete

## atlas-v0.10.0 — Atlas v0.10.0 (2026-08-15)

Atlas v0.10 implements a sanitized, stale-aware Discovery-to-Operator Proposal
Handoff without expanding execution authority.

### Added

- Immutable, extra-forbid proposal, provenance, compatibility, destination,
  target-hint, identity, expiry, and source-state contracts.
- Read-only derivation and evaluation with bounded process-local observation of
  stale or expired proposals and no durable proposal persistence.
- Bounded GET-only proposal list/detail APIs with sanitized, closed navigation.
- Mission Control proposal cards, review-only stale/incompatible presentation,
  compatibility navigation, and separate advisory maintenance context.

### Security boundary

- Proposal existence or navigation cannot create a candidate, planning session,
  approval, action request, dispatch record, or provider operation.
- Maintenance selection reloads current operator permission, production
  capability descriptors, selector resources, state, requestability, and target
  fingerprint. Proposal hints are presentation-only.
- Production mutation remains exactly `restart-service/proxmox/qemu`; LXC and
  all other mutation tuples remain unsupported. The immutable
  `atlas-v0.10.0` release was published at
  `b19ded149f65dfb4043a1b80833e5ff64d83e55d`.

### RC1 validation

- `atlas-v0.10-rc1` (tag object
  `1c8798472ce46b2aa1fc822c1613a720c62113c4`) peels to
  `95d98a4d5e0e9767dd6cb5df06c7ffdb693bf162`. Quality gates run
  `31863884438` and Container release gate run `31863884456` succeeded, and
  `atlas-release-evidence-v1` reported `ready`.
- Production was rebuilt without cache from the exact RC checkout using only
  the production, HTTPS, and operator-auth Compose files. Core and Agent source
  checksums and the Mission Control image matched the RC build; all required
  services remained healthy.
- Live proposal list/detail reads returned four deterministic, sanitized
  proposals, known detail returned 200, unknown detail returned controlled 404,
  and IDs remained stable through Core, Mission Control, Agent, and Edge
  restarts.
- Proposal reads and navigation changed no candidate, planning, approval,
  action-request, dispatch, barrier, provider-operation, result, verification,
  or VM reboot count. Review-only, stale, expired, missing-source/evidence,
  unsupported, transport-failure, and tampered states remained fail-closed.
- Mission Control remained advisory with no target preselection, automatic
  submission, execution, approval, dispatch, retry, or replay control. Atlas
  Edge remained the sole browser ingress.

## atlas-v0.9.0 — Atlas v0.9.0 (2026-08-15)

Atlas v0.9 completed Operational Recovery and Evidence Automation. The final
release was published at
`7a5beac58e1677cd97b9bcc2f160dc30573582aa`, promoting the immutable
`atlas-v0.9-rc1` candidate at
`bc549ff6ab57d366205c1b9eb0c36fc2f7a61ba3` passed required CI,
`atlas-release-evidence-v1`, exact-SHA no-cache production deployment, and
sequential restart soak. Final Quality gates run `31861408265` and Container
release gate run `31861408264` passed.

### Added

- Added a deterministic read-only recovery diagnostic covering lifecycle
  consistency, Core availability, immutable correlation, transition validity,
  target replacement, outcome uncertainty, and controlled safe-next-action
  guidance.
- Added bounded, allow-listed `atlas-operational-support-bundle-v1` evidence
  with deterministic integrity/correlation digests and explicit truncation.
- Added check-only `atlas-release-evidence-v1` automation with fail-closed
  worktree, exact-SHA/tag, CI, Compose, capability, image, and secret-hygiene
  evidence.
- Added Mission Control recovery summaries, bounded enriched operational
  history, controlled filters, and local-only support-evidence preview/download.

### Safety boundary

A read-only feasibility audit rejected `restart-service / proxmox / lxc`
because no provider-authoritative, configuration-independent incarnation
identifier was available. Atlas did not synthesize identity from mutable or
reusable fields, and added no LXC candidate, selector, translation, gate,
handler, ACL, or mutation. The operational production boundary remains exactly
`restart-service / proxmox / qemu`; v0.9 adds no mutation intent or handler.

## atlas-v0.8.0 — Atlas v0.8.0 (2026-08-15)

Atlas v0.8.0 was published at
`f83cd90982d4682ce49e60308e93dc9840984211`, promoting the immutable
`atlas-v0.8-rc1` candidate at
`cf09dfe1eebbd138d37ba7144d91b893f70732fa` after required CI, exact-SHA
production deployment, and sequential service-restart soak validation.

### Added

- Added effect-aware approval presentation with explicit actionable,
  historical, superseded, and expired states and effect-specific approval
  boundaries.
- Added a unified sanitized operational lifecycle read model correlating
  provenance, planning, approvals, dispatch-barrier evidence, provider
  operation capture, verification, recovery, and terminal outcome.
- Added read-only Mission Control operational history and recovery guidance
  with no mutation retry or run-again controls.
- Added provider-neutral, read-only capability and resource-selector
  descriptors projected from existing closed capability sources.

### Changed

- Hardened HTTPS deployments so Atlas Edge is the only host-published browser
  ingress while Mission Control remains reachable on the internal Compose
  network.
- Improved expired-session, reauthentication, permission, CSRF-rotation, and
  Core-unavailable operator UX without adding automatic mutation retry.
- Added release assertions for Agent/Core/translation/registry/descriptor
  parity and lifecycle-response redaction.

The production mutation boundary remains exactly
`restart-service / proxmox / qemu`; v0.8 adds no intent or provider mutation
handler.

### RC1 validation

- Rebuilt no-cache production images from the exact RC1 checkout and proved
  Core, Agent, and Mission Control source/image parity.
- Validated the three-file production deployment, Edge-only HTTPS ingress,
  absence of a Mission Control host port, and exact operational capability
  parity for `restart-service/proxmox/qemu`.
- Restarted Agent, Core, Mission Control, and Atlas Edge sequentially; all
  services remained healthy and the accepted operational workflow remained
  terminal, verified, and lifecycle-consistent.
- Confirmed stale and historical approvals remained non-actionable, no commit
  approval appeared for the operational workflow, and lifecycle/history views
  exposed no retry or run-again control.
- Confirmed exactly-once evidence remained unchanged: one dispatch record, six
  transitions, one dispatching/barrier transition, one provider operation, one
  dispatch result, one verification success, and VM 110 `qmreboot` count `3`,
  with no new request ID and no target-fingerprint change.

## atlas-v0.7.0 — Atlas v0.7.0 (2026-08-14)

Atlas v0.7.0 was published at
`8dbc43de73dda300b50c121f19324cb5174df2a9`, promoting the immutable
`atlas-v0.7-rc1` candidate at
`5b1321091af0fc191844cdf71e9e0d919e4ea415`.

### Added

- Added the approval-gated `restart-service / proxmox / qemu` operational
  workflow, including authoritative QEMU identity, deterministic candidate
  planning, immutable action requests, exact approvals, authenticated
  Agent-to-Core dispatch, a durable exactly-once barrier, provider UPID
  capture, bounded verification, and verifier-only recovery.
- Added Core-owned operator authentication with Argon2id verifier provisioning,
  secure sessions, exact HTTPS trusted-origin enforcement, CSRF protection,
  rate limits, security audit records, and the closed
  `operational_intent:create` permission.
- Added durable operator-intent candidates and a sanitized authoritative
  resource selector. Mission Control now provides operator login and bounded
  maintenance-request pages without exposing provider commands, action IDs,
  native identities, or arbitrary parameters.
- Added one-shot sandbox and verifier-only recovery harnesses used to validate
  the operational contracts without enabling a generic execution path.

### Changed

- Provider health and intelligence collection are bounded concurrently so one
  slow provider cannot serially multiply the dashboard startup timeout.
- Production Compose supports the explicit operator-auth overlay and separate
  Agent-to-Core dispatch credential while retaining existing container
  hardening.

### Validated

- On 2026-08-14, the normal production workflow performed exactly one approved
  graceful restart of Proxmox QEMU VM 110 (`Frigate`). The workflow completed,
  the durable ledger reached `verified`, the same authoritative fingerprint was
  observed afterward, and barrier, provider-operation, and dispatch-result
  counts were each exactly one with no replay.

## atlas-v0.6.0 — Atlas v0.6.0 (2026-08-13)

Atlas v0.6.0 promotes the validated `atlas-v0.6-rc1.9` baseline and was
published as the immutable `atlas-v0.6.0` release at
`03c1e03099b0f638dc674235312a3b3e70768c2f`.

### Added

- Hardened Codex `workspace-write` execution with an immutable named permission
  profile, runsc isolation, a segmented Agent-to-worker relay, peer-bound bearer
  authentication, and production-gate proofs for disposable workspace writes,
  outside-workspace denial, and direct worker-control-plane denial.

- Configurable loopback or LAN HTTP binding and an optional authenticated
  HTTPS ingress overlay.
- Online, integrity-checked backups and guarded restores for persistent
  action history and provider telemetry.
- Optional daily systemd backups with persistent scheduling, strict
  verification, and minimum-count retention safeguards.

### Security

- Updated React Router to 7.18.2 and refreshed the lockfile's compatible
  `brace-expansion`, `nanoid`, and `postcss` transitive releases, resolving the
  final dependency audit findings without a major-version migration or package
  override.

### Validated RC baseline

`atlas-v0.6-rc1.9` was published on 2026-08-13 at
`6d85df5b112b4bde28ec31fc60cce88560c9dbfc` as the validated release-candidate
baseline for v0.6.0.

### Implemented in v0.6.0

- Discovery Center compatibility engine, evidence flow, and catalog integration now
  drive execution-candidate projection with compatibility context available to
  planning and runtime decisions.
- Mission Control Discovery views and execution workflow shell now include
  discovery compatibility details and candidate workflow status across planning,
  implementation, verification, review, and commit checkpoints.
- Provider resources and connection management are now persisted in runtime state,
  including runtime policy and provider-connection stores plus connection secrets.
- Approval-gated execution is implemented across implementation, verification,
  review, and commit stages with immutable approval records.
- Candidate workflow planning and execution state is durable and restart-safe, with
  persisted transition artifacts and deterministic recovery behavior.
- Concurrent resume and workflow state transitions are hardened to prevent
  duplicated effective execution boundaries.
- Runtime verification context is preserved in redacted metadata for restart-safe
  continuation and strict validation.
- Deterministic and hardening coverage added for timing-sensitive candidate paths,
  restart/recovery matrix behaviors, audit-chain validation, concurrency, and
  contract regression.
- Validation coverage required for this RC includes ruff, test, lint, build, and
  container-release-gate verification.
- Core operational scope remains explicit to `update-compose-stack`.
- Structured Compose mutation evidence is required before implementation
  approval. It is carried through planning, workflow metadata, immutable
  implementation requests, and deterministic plan fingerprints.
- Planning, exact approval binding, persistence/recovery, stale evidence
  rejection, and successor concurrency/idempotent reuse were validated in the
  RC1 production smoke-test boundary.
- The final production-like RC1 execution smoke validation passed through the
  awaiting-commit-approval boundary on commit
  `c333937e61343aed714a475395b41077bad86e28`. It verified isolated worker
  execution, exact implementation and verification approvals, deterministic
  zero-command RC1 verification, baseline-aware review, and an exact commit
  approval request without performing the validation-only commit.
- The smoke hardening set now covers worker journal exactly-once recovery,
  approval-boundary audit projection, gated RC1 intent verification,
  baseline-aware verification and review, exact verification-plan approval
  binding, candidate resume dispatch, approval-repository storage identity,
  AtlasCoreClient event-loop ownership, deterministic zero-check evidence, and
  baseline-aware commit validation.
- Codex authentication, CLI installation, ephemeral runtime provisioning, and
  repository mutation are production-ready through the exact approval-gated
  candidate path. A named `workspace-write` permission profile runs inside a
  runsc-isolated worker with an authenticated, network-segmented control plane.
  Runtime proofs cover disposable workspace writes, outside-workspace denial,
  and direct worker-control-plane denial. Broad unconfined profiles,
  `CAP_SYS_ADMIN`, root execution, and `danger-full-access` remain explicitly
  rejected.

### Deferred to v0.7+

- `restart-service` execution intent.
- `backup` and `restore` execution intents.
- `install-provider` and `update-image` execution intents.
- Push, tag, release publication, remote deployment, and rollback automation.
- Candidate UI execution affordances in Mission Control beyond current shell,
  audit, and status workflows.

### Completed v0.6.0 milestone

**Codex Execution Sandbox Hardening** provides an isolated runsc execution
runtime, disposable `workspace-write` and outside-workspace denial proofs,
preserved non-root uid `10001`, zero effective capabilities,
`no-new-privileges`, and read-only rootfs hardening. Authenticated end-to-end
execution was validated through verification, review, and the pending commit
approval boundary without creating the validation-only commit.

### Inherited technical debt

- Atlas Core has an existing repository-wide backlog of 90 Ruff violations.
- Atlas Agent has an existing repository-wide backlog of 20 Ruff violations.
  v0.6.0 blocks new violations in changed production and test files while leaving
  both services' inherited cleanup outside release scope.
- Mission Control currently emits a large JavaScript chunk warning during build.
- Some Atlas Core source-boundary tests assume Atlas Core working-directory layout.

## v1.0.0 — Foundry (2026-07-25)

### Added

- Specialized OPNsense, Frigate, Obsidian, Qdrant, and n8n providers.
- Provider-backed ACE findings with bounded concurrent collection.
- Persistent provider-intelligence telemetry, filtering, export, trends,
  and retention administration.
- Live provider policies, performance thresholds, structured validation
  diagnostics, and Mission Control policy views.
- Persistent action history with filtering, pagination, detail views,
  sanitized export, and confirmed retention maintenance.
- Reproducible development dependency manifests and runtime requirements.
- Hardened production containers for Atlas Core and Mission Control with
  health checks, an API proxy, and persistent telemetry storage.
- Isolated container release gate with runtime hardening assertions,
  HTTP smoke checks, automatic cleanup, and GitHub Actions coverage.
- Pinned Core and Mission Control quality gates, a release checklist, and
  the project MIT license.

### Changed

- Atlas Core integration tests now use a thread-free in-process ASGI
  harness.
- Mission Control exposes provider telemetry, trends, policy status, and
  operational retention controls.
- Removed a stale tracked test backup from release source archives.

## Historical development tags

- `v0.7.0-foundry` — deployment planning, risk engine, and Forge workflow.
- `foundry-0.4.0` — Mission Control provider architecture.
- `v0.3.0-alpha2` — reusable knowledge-engine assessment rules.
- `v0.3.0-alpha1` — Atlas Intelligence Engine and summary API.
- `v0.2.0` — typed ACE policy engine.

### Architecture

- Completed Phase 3 candidate workflow from Discovery compatibility evidence through local Git commit.
- Added deterministic end-to-end candidate workflow coverage, audit-chain validation, recovery matrix coverage, concurrency hardening, commit-path security hardening, strict request validation, and route-contract regression coverage.
- Documented v0.6 boundaries: only `update-compose-stack` is supported; Atlas does not push, tag, release, deploy remotely, auto-approve, auto-execute, or roll back changes.

### Security

- Candidate commits are constrained to exact reviewed files and reject unsafe paths such as `.git/`, `jcode/`, `logs/`, absolute paths, parent traversal, duplicates, empty paths, symlink escape, and unrelated changed files.
- Caller-controlled Phase 3 request bodies use strict validation so input cannot broaden command, path, approval, verification, evidence, or commit scope.
