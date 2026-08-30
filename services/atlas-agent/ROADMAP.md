# Atlas Agent Roadmap

## Released v0.14 state

Atlas Agent is the approval-gated engineering orchestration service. It owns
repository inspection, planning, immutable workflow requests, persistence and
recovery, execution handoff, verification, review, and local commit controls.
The only released repository execution intent is `update-compose-stack`.

In base production Agent uses the local repository execution backend. The
packaged execution worker, relay, egress proxy, and related authentication
staging are disabled by default; the isolated worker backend requires explicit,
separately gated activation. When activated, authenticated worker requests pass
through the relay, with authentication enforced end-to-end by the worker
together with the allowed relay-peer boundary. Execution is never implied by
planning or approval presentation.

Agent also participates in hardened operational dispatch, whose exact released
tuple is `restart-service / proxmox / qemu`. This is separate from repository
candidate execution, legacy provider actions, and Provider Intent. Backup and
restore are operator maintenance tools and are not Agent execution intents.

## Historical A-track

A0-A7 and A9 shipped the documentation/service foundation, repository
inspection, planning, execution, verification, review, Mission Control status,
and workflow automation. Released slices across A8 and A10-A15 supplied Core
intelligence context, production deployment, Core integration, approval-gated
tools, orchestration boundaries, Mission Control integration, and the current
approval-gated development loop; the old roadmap also recorded broader pieces
of those tracks as incomplete.

These A-track checkpoints and the v0.6-v0.10 Agent milestone notes are
historical. An old “next checkpoint” is not current work.

## Enduring constraints

- Planning does not mutate the repository.
- Execution requires the exact supported intent and approval chain.
- When the optional worker backend is activated, worker isolation remains a
  gate independent of repository freshness, immutable evidence, verification,
  review, and commit approval.
- Agent does not automatically approve, deploy, roll back, push, tag, or
  publish a release.
- Discovery evidence and proposals remain advisory/read-only.

## Uncommitted directions

Broader knowledge inputs, additional execution intents, performance evidence,
and distributed orchestration require future explicit planning and authority
review. This document does not name a next checkpoint or invent new Agent work.

## Selected v0.27 planning boundary

Atlas v0.27 selects the **Real Agent Intake Boundary**. Its
normative contract is
[Real Agent Intake Boundary v1](../../docs/architecture/real-agent-intake-boundary-v1.md).
P0 freezes an authenticated, evidence-only intake request, admission result,
seven-release linkage, one-envelope no-replay, and a dormant internal route.

P1–P3 implement isolated models, an explicitly constructed default-disabled
admission service, and one bounded append-only evidence store. P3 deliberately
adds no production route or command surface. P4 adds the isolated,
default-disabled route factory for explicitly constructed offline test apps
only. Production Agent registration, settings, credentials, OpenAPI, Core
delivery, CLI, UI, workflow/worker/runtime coupling, and every target effect
remain prohibited in v0.27. `install-container` remains unsupported and absent
from executable intent/capability registries.

P5 completes release isolation and regression validation. It locks concurrent
single admission, no-replay and fail-closed ambiguity, owned direct readback,
the factory's single test-only POST shape, zero production Agent/Core consumer,
and no Mission Control surface. Home Assistant remains blocked and has no
deployment artifact. P5 adds tests and release documentation only.

## Selected v0.32 planning boundary

Atlas v0.32 selects **Agent Live Intake Admission**. Its normative contract is
[Agent Live Intake Admission v1](../../docs/architecture/agent-live-intake-admission-v1.md).
P0 freezes an inert outer envelope binding the complete same-owner v0.20–v0.30
chain and the v0.31 reserved send attempt, plus closed Agent admission,
acknowledgement, result, record, audit, lifecycle, and redacted-error models.
The Agent outputs are inputs to the downstream v0.31 Core receipt; the receipt
is not an admission prerequisite.

P1–P3 added closed models, a bounded append-only default-off admission
service/store, and the sole guarded production Agent POST. Registration stays
off unless explicitly configured; authentication is for one fixed Core
principal through an injected mode-0400 credential reference, and no secret
value may be modeled, persisted, logged, returned, or documented. P4 keeps
Mission Control absent and adds structural locks against any v0.32 client,
page, navigation, mutation, retry/resend, effect control, sensitive rendering,
or Home Assistant exception. It adds no Core bridge or runtime behavior. P5
completed isolation and release closure with exact default-off route locks,
concurrent permanent no-replay, append-only restart-safe and secret-free
evidence, zero effect consumers, Core one-shot/no-retry preservation,
capability parity, and Home Assistant blocking. Both Ruff gates, all 3072 Core
tests, all 1045 Agent tests, and all 550 Mission Control tests plus lint/build
passed. P5 adds tests and release evidence only.

This boundary durably admits evidence; it does not admit execution. There is no
install, runtime/container/process execution, retry/resend, dispatch, worker,
workflow, provider/repository/in-guest mutation, deployment, rollback, public
Core API, Mission Control surface, or Home Assistant artifact. Existing
executable intent and capability registries remain unchanged.

## Selected v0.33 planning boundary

Atlas v0.33 selects **End-to-End Inert Delivery Receipt**. Its normative
contract is [End-to-End Inert Delivery Receipt
v1](../../docs/architecture/end-to-end-inert-delivery-receipt-v1.md).

Agent behavior remains the exact v0.32 independently default-off guarded POST,
closed envelope/result, append-only admission, fixed Core principal, and
mode-0400 credential-reference verification. V0.33 adds no Agent schema,
action, route, callback, read API, worker/workflow/runtime consumer, retry, or
mutation. Core may explicitly make one one-shot call and verify the returned
admission/acknowledgement into its own receipt; Core does not claim direct
verification of Agent-local storage.

P0 is documentation-only. P1–P3 added Core-only closed verification models,
an append-only default-off receipt service/store, and one injected one-shot
composition. P4 locks Mission Control and public Core API absence. P5 completed
release isolation while preserving the exact one-shot Core send and admission-
only Agent boundary; both Ruff gates, all 3107 Core tests, all 1045 Agent tests,
and all 555 Mission Control tests plus lint/build passed.
Installation, execution, dispatch, worker/workflow start,
provider/repository/in-guest mutation, deployment, rollback, retry/resend, and
Home Assistant artifacts remain blocked.

## Selected v0.34 planning boundary

Atlas v0.34 selects **Installation Readiness Review**. Its normative contract
is [Installation Readiness Review
v1](../../docs/architecture/installation-readiness-review-v1.md).

V0.34 is Core-local read composition and Mission Control presentation only.
It may summarize the frozen exported v0.22, v0.25–v0.27, and v0.32 Agent
evidence already bound into the v0.33 chain, but it adds no Agent schema,
reader, route, call, callback, credential access, registration, or behavior.
Agent-local records not exported by released contracts cannot be inferred.

P0 changed planning documents only. P1 added Core-only closed models and pure
review evaluation without any Agent import or behavior. P2 adds only a
Core-local injected reader composition and does not import or invoke Agent.
P3 exposes only the authenticated Core read-only GET and likewise does not
import, contact, or change Agent. P4 adds only a Mission Control read-only GET
presentation and likewise cannot invoke Agent. P5 release isolation confirms
that v0.34 adds no Agent consumer, route, invocation, or behavior. P0–P5 are
complete. Installation,
execution, dispatch, retry/resend, Agent invocation, worker/workflow/process
start, provider/repository/in-guest mutation, deployment, rollback, and Home
Assistant artifacts remain blocked.

## Selected v0.35 planning boundary

Atlas v0.35 selects **Execution Permission Grant Boundary**. Its normative
contract is [Execution Permission Grant
v1](../../docs/architecture/execution-permission-grant-v1.md).

P0 was documentation-only. P1–P3 add only Core-owned closed models and an
explicitly constructed Core-local append-only service/store. The grant is an
operator permission artifact over the already exported v0.20–v0.34 evidence
chain. It adds no Agent schema, permission, route, reader, callback,
credential, registration, invocation, worker/workflow consumer, runtime
capability, executable intent, or behavior. Agent-local evidence not exported
by released contracts remains inaccessible and cannot be inferred.

The v0.35 grant may later become one prerequisite for a separately specified
execution-admission decision, but it is not that decision and cannot be
consumed by Agent in v0.35. Installation, execution, dispatch, retry/resend,
Agent invocation, worker/workflow/process start, Docker/Podman/shell,
provider/repository/in-guest mutation, deployment, rollback, and Home Assistant
artifacts remain blocked through P0–P5.

## Selected v0.36 planning boundary

Atlas v0.36 selects **Installation Execution Admission Boundary**. Its
normative contract is [Installation Execution Admission
v1](../../docs/architecture/installation-execution-admission-v1.md).

P0 was documentation-only. P1–P4 added Core-owned admission evidence
over the already exported v0.20–v0.35 chain. It adds no Agent model, route,
reader, callback, permission, credential, registration, runner identity,
invocation, executable capability, worker/workflow consumer, or runtime
behavior. Agent-local evidence not exported by released contracts remains
inaccessible and cannot be inferred. P5 confirms through Agent regression and
repository isolation tests that Agent has no v0.36 consumer or Home Assistant
deployment artifact. P0–P5 are complete.

Every successful v0.36 record remains `admission_gated` because runner binding
and the execution-start boundary are undefined. Installation, execution,
dispatch, retry/resend, Agent invocation, worker/workflow/process start,
Docker/Podman/shell, provider/repository/in-guest mutation, deployment,
rollback, and Home Assistant artifacts remain blocked through P0–P5.
