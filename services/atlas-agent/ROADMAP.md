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
