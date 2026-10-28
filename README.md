# Atlas OS

Atlas OS is a local-first infrastructure control plane that turns provider,
inventory, policy, Discovery, installation, and execution-boundary evidence
into operator-facing explanations, recommendations, and tightly bounded
approved actions.

Atlas is intentionally conservative: evidence precedes mutation, each authority
surface is separate, and later authority remains fail-closed and default-off
unless a released contract explicitly activates it.

## Current repository state

The selected development scope through **Atlas v1.0.0** is complete: bounded,
explicitly approved repository editing, separate verification and local commit,
durable result lookup/recovery, and fail-closed worker isolation and transport.
See the [roadmap](ROADMAP.md), [v1.0.0 release scope](docs/releases/atlas-v1.0.0.md)
and [release checklist](docs/RELEASE_CHECKLIST.md).

The latest verified annotated tag is
**[`atlas-v1.0.0`](https://github.com/vortex469/atlas-os/tree/atlas-v1.0.0)**,
pushed after [PR #38](https://github.com/vortex469/atlas-os/pull/38) merged to
`main` at exact commit `e41d6017d19d0e86321dede3d3a36ea3c1c8df4b`.
Both exact-commit workflows passed:
[Quality gates](https://github.com/vortex469/atlas-os/actions/runs/40228623388)
and [Container release gate](https://github.com/vortex469/atlas-os/actions/runs/40228623378).
The existing pre-tag release-evidence check exited 0 with `summary.status=ready`;
the annotated tag's commit identity was verified on GitHub.

The **v1.0.0 GitHub release page has not been published**. GitHub's Releases
sidebar therefore still lists
[`atlas-v0.65.0`](https://github.com/vortex469/atlas-os/releases/tag/atlas-v0.65.0)
as the latest published release. A pushed tag and a published release page are
separate records; neither deploys Atlas.

This release scope does not authorize deployment or runtime activation. The
nested patch-helper limitation, seven installation blockers and deferred
successor control-plane activation remain explicit. Production running-image
parity and production operator acceptance require separate evaluation.

## What Atlas does today

Atlas Core collects and normalizes infrastructure state, evaluates policy,
serves typed APIs, owns durable control-plane state, and guards operator
sessions, Provider Intent, Discovery, installation evidence, and operational
lifecycle state.

Mission Control is the browser operator surface. It presents provider health,
policy findings, recommendations, Discovery evidence, installation planning and
candidate evidence, approval and execution-admission records, queue and worker
evidence, and review surfaces. Its installation workflow panels are evidence and
review surfaces; authoritative validation remains server-side.

Maintenance proposals use their own plan and exact-action review screens. The
operator can review the target, expected disruption, expiry, and verification
rules before a separate exact-action approval and run step. Approval controls
require the server's current actionable approval presentation. Phone and desktop
browser tests simulate this journey without contacting a provider or enabling
execution; these checks do not establish production acceptance.
Maintenance history displays lifecycle and recovery details only when their
workflow identifiers match the request listed on the card.
Maintenance audits show their read-only operational lifecycle rather than
repository implementation, review, and commit stages.
Proposal searches display only the latest requested results. Previous cards are
hidden during loading and after a failed search, so stale proposals are not
presented as current results.
Preparation screens use four plain steps: Proposal, Planning, Plan, and Workflow.
This indicator shows the current screen; it does not report approval or execution
status. The workflow displays its server-reported stages separately.
Workflow preparation uses plain-language next steps, with technical request
details available in an optional disclosure beside any preparation error.
Keyboard users can use “Skip to page content” to bypass the repeated header and
navigation without changing the current URL.
Forge clears previous analysis when the name or Compose document changes and
ignores responses for older inputs. Analysis errors are announced in the editor;
an analysis result does not execute a deployment.
Forge's summary shows the highest risk reported by its analyzer or planner and
keeps unknown durations distinct from zero. Planner approval flags describe the
proposal; workflow authorization remains separate.
Maintenance selection is locked while a request is submitted. Refreshing clears
the previous selection and result, and the returned proposal must match the
requested resource and action before planning is offered.
Dashboard attention keeps decisions, blockages and their reasons visible, with
workflow stage metadata and health interpretation guidance available on demand.

Atlas Agent owns approval-gated repository workflow orchestration, verification,
review, and local commit boundaries. The released repository execution intent
remains exactly `update-compose-stack`.

The packaged execution-worker stack provides an optional isolated backend for
Agent repository execution. Base production uses the local Agent backend; worker,
relay, egress-proxy, and auth-staging infrastructure are packaged but
separately gated. The worker path does not expand the allowed repository intent
or absorb Provider Intent, provider actions, operational dispatch,
backup/restore, deployment, rollback, or release-publication authority.

Implemented side-effect surfaces remain deliberately separate:

- legacy provider actions exposed by individual providers;
- Provider Intent mutation, limited to identity-bound Proxmox QEMU
  `monitoring-policy`;
- hardened operational dispatch, exactly `restart-service / proxmox / qemu`;
- repository candidate execution, exactly `update-compose-stack`.

The v0.20-v0.49 installation chain records evidence for planning, prospective
destination review, capability assessment, candidate admission and preservation,
operator approval statements, validation-only Agent install-container
contracts, execution requests, dispatch handoffs, simulated and inert delivery,
readiness, permission, execution admission, runner binding plans, worker
admission stubs, queue reservations, worker intake admission, live enqueue
admission, one-shot live enqueue, queue observation, controlled dequeue
admission, one-shot controlled dequeue, dequeue worker binding, worker-binding
activation preflight, worker-binding activation evidence, and controlled worker
queue claim admission evidence.

## What Atlas deliberately does not do

Atlas does not automatically remediate, approve, update, deploy, roll back,
publish releases, or install arbitrary applications.

Discovery remains GET-only/read-only and grants no operational authority. Image
grounding is informational; the generic image collector remains inactive in
production unless a future released contract changes that.

The installation pipeline through v0.49 is not installation execution. The
strongest v0.49 installation state is
`controlled_worker_queue_claim_admission_recorded`: evidence that one exact
active same-owner v0.48 worker-binding activation evidence record may be
considered by a later, separately released controlled queue claim/lease/
acknowledgement boundary.

V0.49 does not define queue claim, queue lease, queue acknowledgement, worker
activation runtime, worker store contact, worker runtime contact, worker-start
admission, worker start, Agent invocation, execution authorization, execution
start, installation, deployment, rollback, publication, or an effect consumer.
Home Assistant remains blocked where the repository lacks a supported
deployment artifact and execution authority.

## Architecture overview

```text
operator browser
  -> Mission Control
       -> Atlas Core
            -> providers / runtime state / durable evidence stores
            -> guarded operational dispatch
       -> Atlas Agent
            -> local repository execution backend (default)
            -> optional, separately gated isolated backend:
                 authenticated worker requests through relay
                      -> runsc-isolated execution worker
                           -> allowlisted egress proxy

one-shot stagers:
  atlas-agent-auth-stager
  atlas-execution-auth-stager
  atlas-core-agent-auth-stager
```

`compose.production.yaml` defines the hardened base production package. HTTPS
ingress, Core-owned operator authentication, and Provider Intent activation are
enabled by overlays. Development can run Core and Mission Control directly, but
that two-process setup is not the production topology.

The guarded installation authority chain is Core-owned and stage-specific. Each
stage binds exact same-owner evidence from the prior stage, records bounded and
redacted evidence, uses dedicated operator permissions where exposed by API, and
keeps downstream authority false until a later released boundary explicitly
defines it.

For the freshest normative details, start with:

- [Roadmap](ROADMAP.md)
- [Release checklist and evidence](docs/RELEASE_CHECKLIST.md)
- [Controlled Worker Queue Claim Admission v1](docs/architecture/controlled-worker-queue-claim-admission-v1.md)
- [Worker Binding Activation Evidence v1](docs/architecture/worker-binding-activation-evidence-v1.md)
- [One-Shot Dequeue Worker Binding v1](docs/architecture/one-shot-dequeue-worker-binding-v1.md)
- [InstallationPlan v1](docs/architecture/installation-plan-v1.md)
- [Execution worker README](services/atlas-execution-worker/README.md)

## Installation pipeline summary

Atlas can assemble read-only installation plans and operator review evidence,
then preserve exact non-executable candidate records and approval statements.
Later stages progressively record validation, request, handoff, delivery,
readiness, permission, execution-admission, runner, worker, queue, dequeue,
binding, activation, and queue-claim-admission evidence.

Those records are useful because they make the authority chain inspectable and
auditable before any future runtime authority is considered. They are not
commands, payloads, credentials, deployment recipes, rollback plans, or hidden
approval to run work.

## Production services

`compose.production.yaml` defines nine base services: `atlas-core`,
`atlas-agent`, `atlas-agent-auth-stager`, `atlas-execution-worker`,
`atlas-execution-worker-relay`, `atlas-execution-auth-stager`,
`atlas-core-agent-auth-stager`, `atlas-egress-proxy`, and `mission-control`.
Overlays add HTTPS/`atlas-edge`, Core-owned operator authentication, and
Provider Intent activation.

## Local development

Local development runs components directly and is not the production topology.
Atlas Core requires Python 3.12; Mission Control requires a supported Node.js
and npm toolchain. Open two terminals from the repository root and leave each
server running in its own terminal.

Terminal 1 — Atlas Core:

```bash
cd services/atlas-core
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8643
```

Terminal 2 — Mission Control:

```bash
cd services/mission-control
npm ci
npm run dev
```

For access from another device on the same trusted LAN, start Vite with:

```bash
npm run dev -- --host 0.0.0.0 --port 5173 --strictPort
```

Open the Network URL printed by Vite or `http://<Atlas-machine-LAN-IP>:5173`;
on Linux, `hostname -I` lists the machine's addresses. Allow inbound TCP port
5173 through the host firewall if needed. Vite proxies API requests to Core at
`127.0.0.1:8643` and Agent at `127.0.0.1:8090`, so start the backend needed by
the screen you want to inspect on the Atlas machine. See the [Mission Control
development guide](services/mission-control/README.md#development) for proxy
and trusted-LAN details. The hardened execution path has its own development
and test workflows.

## Production deployment

Production uses the hardened Compose package and persistent named volumes.
Agent defaults to its local repository execution backend. The package also
includes default-disabled worker, relay, egress-proxy, and related auth-staging
infrastructure for an isolated backend that requires explicit, separately gated
activation. Follow [Production Deployment](docs/DEPLOYMENT.md); do not infer
production layout from the two-process development example.

## Security / authority model

Core owns API contracts, operator sessions, Provider Intent, operational
dispatch, Discovery state, and the installation evidence chain. Agent owns
repository workflow orchestration and independently enforces execution
capabilities. The execution worker is an optional isolated backend, not a new
authority surface.

Backup/restore is operator maintenance tooling, never an Agent execution
intent. Credentials remain outside tracked configuration. Side effects require
the authority specific to their surface, and new authority must fail closed, be
explicitly activated, and be independently enforceable at each trust boundary.

## Release history links

- [Changelog](CHANGELOG.md)
- [Release checklist and evidence](docs/RELEASE_CHECKLIST.md)
- [Deployment and historical upgrade notes](docs/DEPLOYMENT.md)
