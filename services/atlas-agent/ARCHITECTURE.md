# Atlas Agent Architecture

## Purpose and ownership

Atlas Agent orchestrates bounded work; it does not own repository truth, Atlas Core control-plane state, provider state, operator sessions, or infrastructure authority. Core data enters through typed APIs and immutable request contracts. Agent never reads Core databases directly.

Released v0.14 contains two deliberately separate paths:

```text
repository candidate                         hardened operation
Core candidate -> Agent planning/workflow    Core lifecycle/dispatch -> Agent boundary
              -> approved repository tool                         -> validated transport
              -> verification/review/commit                       -> provider operation
```

Legacy provider actions are a third, provider-owned surface and do not use the hardened operational tuple. Provider Intent changes monitoring policy only and is not provider execution.

## Repository candidate execution

The repository registry contains exactly `update-compose-stack`. Candidate intake is revalidated, then captured with repository and optional Core context as immutable planning evidence. The workflow produces immutable implementation, verification, and commit requests with independent exact approvals.

The controlled local execution engine validates repository root, command capability, arguments, environment, and working directory. Implementation, verification, deterministic review, and local commit preserve separate artifacts. Commit additionally binds expected branch and HEAD, exact reviewed changed paths, status/content fingerprint, and message; drift blocks execution.

No repository workflow pushes, tags, publishes a release, deploys remotely, rolls back, or accepts an arbitrary command.

## Operational dispatch transport

The operational registry contains exactly `restart-service / proxmox / qemu`. Core owns operator-session permission checks, durable operational planning and approval lifecycle, target fingerprint revalidation, dispatch state, verification, recovery projection, and support evidence. Agent independently validates the immutable request, provider/resource tuple, expiry, digest, and authenticated Core boundary before translating it to the single reviewed provider action.

The transport is no-replay. Requests and outcomes use stable identity; a completed request is not relaunched, and an interrupted or uncertain side effect remains conservative for reconciliation. This path is not a generic Agent candidate, provider-action proxy, shell, or backup/restore mechanism.

## Planning, review, and approval stages

Repository planning produces executable workflow inputs only for the repository registry. Operational planning produces a descriptive plan and action request only for the operational registry; it cannot become repository execution. Each mutation proceeds only after its owning authority creates an exact immutable approval/request contract.

Agent never approves on behalf of an operator. Missing, rejected, expired, drifted, mismatched, or already-consumed evidence blocks the relevant transition. Resume uses atomic compare-and-swap state transitions, does not repeat completed stages, and never treats a persisted `executing` state as permission to retry.

## Persistence and recovery

Repository workflow and approval artifacts persist as a local single-process aggregate snapshot under `ATLAS_AGENT_STATE_DIR`. Approval-wait, completed, and blocked states restore without replay. Interrupted side-effect stages recover blocked. This store is Agent coordination state, not a distributed database or Atlas Core authority.

Core separately owns `operational_dispatch.db` for durable operational safety and audit. Agent does not use its repository snapshot as a substitute for Core's dispatch ledger.

## Context and model assistance

Before repository planning, Agent retrieves typed Core health/status once and may add bounded advisory intelligence. The immutable snapshot is reused on resume. Advisory or model-produced evidence cannot change commands, arguments, environment, target, approval, execution policy, verification, or commit behavior. Deterministic planning and reviewed registries remain authoritative.

## Optional isolated worker backend

`ATLAS_EXECUTION_BACKEND=local` is the base-production default. The packaged worker backend is default-disabled and requires separately gated configuration and runtime validation.

When explicitly activated, Agent sends authenticated worker requests through the relay. The worker authenticates at its boundary, accepts only the isolated relay peer, executes in a disposable constrained workspace, persists a one-way/no-replay ledger, and reaches allowlisted egress only through the proxy. The relay transports requests; it is not alone the authentication authority.

Changing backend does not change the repository intent registry or add operational/provider capabilities. Interrupted worker execution becomes `unknown_outcome` and is not automatically relaunched.

## Production dependency flow

```text
Mission Control -> Agent operator API -> repository workflow -> local backend (default)
                                                      \-> optional gated relay/worker

Atlas Core -> authenticated internal Agent operational boundary -> exact operational adapter
```

All public and internal callers are treated as untrusted until the applicable authentication, capability, identity, digest, expiry, and state checks succeed. There is no automatic approval, remediation, update, deployment, rollback, or release publication.
