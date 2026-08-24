# Atlas Agent

Atlas Agent is Atlas's approval-gated orchestration service. In released v0.14 it coordinates repository candidate planning, implementation, verification, deterministic review, and local commit, and it provides the Agent-facing transport boundary for hardened operational dispatch. It does not own Atlas Core state, provider state, operator authentication, deployment policy, CI, package management, or arbitrary infrastructure execution.

See [Agent architecture](ARCHITECTURE.md) for component boundaries and [Atlas architecture](../../ARCHITECTURE.md) for the system authority model.

## Released responsibilities

For repository candidates, Agent owns immutable context snapshots, deterministic plans, workflow shells, exact approval requests, controlled implementation, verification evidence, deterministic review, commit evidence, local workflow persistence, and audit-chain validation. The only released repository execution intent is:

```text
update-compose-stack
```

For hardened operations, Core owns operator authorization, durable lifecycle state, target revalidation, and dispatch. Agent independently validates and transports only the released tuple:

```text
restart-service / proxmox / qemu
```

This operational path is separate from repository candidate execution and from legacy provider actions. Provider Intent is Core-owned monitoring-policy authority only and is not an Agent execution capability. Backup/restore is operator maintenance tooling, not an Agent intent.

Agent accepts no arbitrary command, intent, provider, or resource type. It does not automatically approve, remediate, update, deploy, roll back, push, tag, or publish releases.

## Repository workflow

```text
candidate intake and planning
→ immutable implementation request
→ exact implementation approval
→ implementation
→ immutable verification request
→ exact verification approval
→ verification and deterministic review
→ immutable commit request
→ exact commit approval
→ local Git commit
```

Each side-effect stage is claimed atomically. Approval is bound to immutable request evidence; commit approval includes expected branch and HEAD, exact reviewed paths, content/status fingerprint, and commit message. Repository drift or mismatched approval blocks the workflow.

Workflow resume is stage-aware and idempotent. Completed stages do not replay, commit executes at most once, and an interrupted implementation, verification, commit, or operational dispatch is recovered conservatively rather than relaunched. Local aggregate snapshots under `ATLAS_AGENT_STATE_DIR` preserve approval-boundary workflow artifacts across restart; they are single-process Agent coordination state, not broader Atlas persistence or cross-host recovery.

## Planning and context

Agent captures Atlas Core health and status once before repository workflow planning and retains the typed snapshot. Intelligence summary data is optional advisory evidence: failures do not discard valid essential context, and intelligence cannot alter commands, arguments, environment, working directory, execution policy, approval state, verification, or commit behavior. Deterministic planning remains authoritative; model assistance does not authorize execution.

Operational planning is descriptive until Core supplies the separately authorized immutable dispatch request. Repository planning and operational planning cannot be converted into one another.

## Production execution backends

Base production sets:

```text
ATLAS_EXECUTION_BACKEND=local
```

The local repository backend is the normal production default. The worker/relay/egress stack is packaged but default-disabled. Using it requires separately gated configuration and runtime validation. When activated, authenticated worker requests pass through the relay to the isolated worker and constrained egress path. Backend selection does not expand the allowed intent or approval boundary.

## Service boundary

Agent exposes health and diagnostics plus versioned endpoints for repository status, approvals, candidate planning, workflows, operational planning/translation, and the authenticated internal operational action boundary. Mission Control proxies the operator-facing Agent API; Core calls the dedicated internal operational boundary. Authoritative validation remains server-side.

The production service is defined by `compose.production.yaml`, uses an internal-only network, a read-only root filesystem, dropped capabilities, narrow state and repository mounts, and no published host port. Follow [Production Deployment](../../docs/DEPLOYMENT.md) rather than treating local development topology as production authority.

## Local development

Use the repository-pinned Python environment and run the Agent tests from this directory. Local development must preserve the exact capability registries and should not enable the worker backend or operational execution merely to exercise planning paths.
