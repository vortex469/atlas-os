# Atlas Agent Roadmap

## Vision

Atlas Agent is the engineering orchestration service for Atlas.

Its purpose is to provide a repeatable engineering workflow from roadmap
checkpoint to verified implementation while keeping humans in control of
architectural decisions.

---

## A0 — Documentation

Status: complete

Goal

Establish the architecture and guiding principles.

Deliverables

- README.md
- ROADMAP.md
- ATLAS_AGENT_CONTEXT.md

Acceptance Criteria

- Documentation reviewed
- Architecture approved
- No application code

---

## A1 — Service Skeleton

Status: complete

Goal

Create the Atlas Agent service foundation.

Deliverables

- FastAPI application
- Dependency injection
- Configuration
- Logging
- Health endpoint
- Tests

Acceptance Criteria

- Service starts
- Tests pass
- Ruff passes

---

## A2 — Repository Inspection

Status: complete

Goal

Allow Atlas Agent to inspect a Git repository.

Capabilities

- Current branch
- HEAD commit
- Git status
- Modified files
- Untracked files

Acceptance Criteria

Repository status returned through a repository interface.

---

## A3 — Planning Engine

Status: complete

Goal

Convert roadmap checkpoints into implementation plans.

Capabilities

- Scope analysis
- File estimation
- Risk assessment
- Test planning

Planning never edits code.

---

## A4 — Execution Engine

Status: complete for the currently approved Codex execution scope

Goal

Execute approved implementation plans.

Capabilities

- Launch Codex
- Track progress
- Capture output
- Stop on failure

Execution never commits code.

---

## A5 — Verification Engine

Status: complete

Goal

Verify implementation quality.

Capabilities

- Ruff
- Pytest
- npm
- Build validation

Acceptance Criteria

Structured verification report.

---

## A6 — Review Engine

Status: complete

Goal

Review implementation against Atlas architecture.

Capabilities

- Architecture validation
- Scope validation
- Test coverage review
- Engineering recommendations

---

## A7 — Mission Control Integration

Status: complete

Goal

Expose Atlas Agent workflows through Mission Control.

Capabilities

- Repository status
- Sprint status
- Verification reports
- Review reports

This checkpoint supplied the current read-only Atlas Agent status panel.
A14 retains the later roadmap label for the same integration area rather than
representing an unrelated second UI.

---

## A8 — Knowledge Engine Integration

Status: partially complete

Goal

Use Atlas knowledge to improve planning.

Capabilities

- Architecture awareness
- Repository knowledge
- Best practices
- Historical context

Implemented first production slice:

- typed access to Atlas Core's supported intelligence summary API
- normalized findings, assessments, and recommendations in `AgentContext`
- preservation of essential health and status context when advisory
  intelligence is unavailable
- one observable planning risk for unavailable intelligence
- at most five deterministic intelligence-derived planning risks
- strict separation between intelligence evidence and execution inputs

Still unfinished:

- a supported definition and source for broader engineering history
- additional bounded knowledge capabilities beyond the live intelligence
  summary

---

## A9 — Workflow Automation

Status: complete

Goal

Coordinate engineering workflows.

Capabilities

- Sprint execution
- Verification pipeline
- Review pipeline
- Human approval gates

---

## A10 — Production Readiness

Status: partially complete

Goal

Prepare Atlas Agent for production use.

Deliverables

- Documentation complete
- Tests complete
- Performance validation
- Operational readiness

Configuration validation, diagnostics, structured failures, broad automated
tests, and production deployment artifacts are implemented. Atlas Agent now has
a dedicated production Dockerfile, a production Compose service, an
`atlas-agent-state` persistent volume, internal-only service exposure, Mission
Control `/agent-api/` proxying, HTTPS flow through `atlas-edge`, production
health checks, container hardening, and container release-gate coverage.
Recorded release acceptance testing, performance validation, and remaining
operational-readiness evidence are still unfinished.

---

## A11 — Atlas Core Integration

Status: functionally complete

Goal

Allow Atlas Agent to reason about the running Atlas system through supported Atlas Core APIs.

Deliverables

- typed Atlas Core client
- configuration and connection validation
- read-only Atlas system context retrieval
- Context Engine
- normalized AgentContext
- backward-compatible integration with planning, verification, and review
- unit and integration tests
- API and architecture documentation

Suggested implementation sequence:
- A11.1 Atlas Core Client — complete
- A11.2 Context Aggregation — complete
- A11.3 Planning Integration — complete
- A11.4 Verification and Review Integration — complete

Explicitly out of scope:
- direct Atlas Core database or persistence access
- Git write automation
- external command execution
- Docker execution
- autonomous editing
- Mission Control UI changes
- multi-model orchestration

Acceptance Criteria

- Atlas Core remains the authoritative source of Atlas system state
- Atlas Agent retrieves Atlas state only through supported Atlas Core APIs
- failures are bounded and reported clearly
- existing repository-only workflows remain functional
- no breaking API changes
- Ruff passes
- all tests pass

The functional integration is complete. Documentation synchronization is
tracked by A10.1.

---

## A12 — Approval-Gated Tool Execution

Status: complete for the currently defined approval-boundary scope

Goal

Enable tool execution that requires human approval.

Capabilities

- Git, Ruff, pytest, npm, and Docker execution
- explicit safety boundaries and approvals

Implementation execution through the current Codex tool policy, verification
commands, and the final deterministic Git commit now have independent approval
boundaries. The implemented production workflow is:

```text
planned
→ awaiting implementation approval
→ executing
→ awaiting verification approval
→ verifying
→ reviewing
→ awaiting commit approval
→ committing
→ completed
```

Resume is stage-aware and idempotent. Implementation does not replay after the
verification pause, verification and review do not replay after the commit
pause, and commit executes at most once. Atomic compare-and-swap transitions
protect each side-effect stage, and execution, verification, review, and commit
artifacts persist in the immutable workflow session between approval pauses.
Commit approval is bound to immutable repository evidence: expected branch,
expected HEAD, exact reviewed changed paths, a content/status fingerprint, and
the commit message. Repository drift before commit blocks the workflow.
Missing or pending approvals keep the workflow waiting; rejected, invalid, or
mismatched approvals block the workflow.

The broader Docker execution policy remains outside the current implemented
scope.

---

## A13 — Local Model Orchestration

Status: partially complete

Goal

Orchestrate local language models for enhanced capabilities.

Capabilities

- local reasoning, planning, review, and model selection
- model implementations remain replaceable

The replaceable provider interface, Ollama provider, model service, normalized
model responses, and model-assisted planning are implemented. Model-assisted
review, model selection, and autonomous model-driven execution are not.

---

## A14 — Mission Control Integration

Status: complete for the currently listed scope

Goal

Expose Atlas Agent workflows through the Atlas UI.

Capabilities

- repository status
- sprint status
- verification reports
- review reports

The current Mission Control integration displays these reports. It also loads
pending approvals and includes an approval decision card, although that card is
not mounted in the current status panel. This checkpoint overlaps A7 and
records the same product integration area at a later roadmap stage.

---

## A15 — Approval-Gated Development Loops

Status: partially complete

Goal

Orchestrate inspection, planning, editing, verification, review, and commits with human approval at defined write boundaries.

Capabilities

- orchestrate inspection, planning, editing, verification, review, and commits
- retain human approval at defined write boundaries

The current workflow covers inspection, planning, approval pause/resume,
controlled implementation, independently approved verification, deterministic
review, independently approved commit, and deterministic commit handling.
Workflow and approval state is persisted as a local file-backed aggregate
snapshot under `ATLAS_AGENT_STATE_DIR`. Approval-boundary workflows survive
process restart. Interrupted `EXECUTING`, `VERIFYING`, and `COMMITTING`
side-effect stages recover as blocked rather than being replayed.

The implemented persistence is local and single-process. It does not provide a
distributed store, database, multi-process coordination, or cross-host recovery.
Redacted verification environment values require matching current environment
values after restart, and corrupt or unsupported snapshots block startup.

The production deployment path for this service is implemented.
`compose.production.yaml` runs Atlas Agent from the dedicated production image,
mounts the operator-selected `ATLAS_REPOSITORY_HOST_PATH` at
`/workspace/repository`, passes
`ATLAS_AGENT_REPOSITORY_ROOT=/workspace/repository`, persists local workflow
state on `atlas-agent-state`, and keeps the service internal-only behind Mission
Control's `/agent-api/` proxy. HTTPS traffic flows through `atlas-edge` to
Mission Control and then Atlas Agent. The production image includes Python,
Uvicorn, Atlas Agent, and Git only; Codex, Ruff, pytest, Node/npm, Docker, and
other project-specific workflow tools remain operator-provided rather than
bundled.

Broader A15 development-loop hardening remains unfinished.

---

## Next Implementation Checkpoint

A12 granular approval work is complete for its currently defined scope. Based on
the existing roadmap, the remaining unfinished checkpoints include A8 broader
knowledge capabilities, A10 release acceptance and operational-readiness
evidence, A13 model-assisted review/model selection, A15 broader
development-loop hardening, and Docker execution policy work outside the current
A12 scope. The roadmap does not define a sub-checkpoint ordering between those
unfinished tracks, so the next implementation checkpoint is pending human
selection.

## v0.6 and v0.7 completion and future phases

### Completed

- Phase 3 candidate planning and workflow shell creation.
- Immutable candidate implementation requests.
- Exact implementation, verification, and commit approvals.
- Candidate execution, verification evidence, deterministic review, local commit, and completed workflow persistence.
- P3.14A reliability and security hardening, including end-to-end candidate coverage, audit-chain validation, recovery matrix tests, deterministic concurrency tests, commit-path security, strict route validation, API contract coverage, and roadmap regression tests.

### Planned Phase 4

V0.7 completed the first closed Phase 4 slice:
`restart-service / proxmox / qemu`, with typed operational planning, immutable
requests, exact approvals, authenticated Core dispatch, durable exactly-once
barrier, bounded verification, and recovery.

Additional execution intents or provider/resource tuples may be added only
after separate design, public contracts, immutable requests, exact approvals,
recovery behavior, security tests, and end-to-end coverage. `backup`, `restore`,
`install-provider`, and `update-image` remain examples of unsupported future
intents; v0.8 deliberately adds none of them.

Atlas v0.8 P0 through P5 are complete. The immutable `atlas-v0.8-rc1`
candidate at `cf09dfe1eebbd138d37ba7144d91b893f70732fa` passed required CI,
exact-SHA production parity, and sequential service-restart soak validation.
Agent changes are limited to effect-aware approval presentation, sanitized
lifecycle correlation, and read-only capability consistency. Agent planning,
translation, and execution remain closed to the existing
`restart-service / proxmox / qemu` operational tuple. The final
`atlas-v0.8.0` release was published at
`f83cd90982d4682ce49e60308e93dc9840984211`.

## Atlas v0.9 — Safe Operational Tuple Expansion

The contingent second tuple is `restart-service / proxmox / lxc`, but it is not
enabled. Work proceeds in order through P0 release reconciliation, P1 read-only
authoritative LXC identity, P2 multi-tuple capability and permission contracts,
P3 dormant planning and dispatch contracts, P4 handler/verification/recovery
validation, and P5 controlled enablement and acceptance.

P1 is a hard stop: VMID plus node is insufficient, and Atlas must prove stable
same-incarnation fingerprints and replacement, stale, missing, duplicate,
ambiguous, and uncertain identity rejection. The first code slice changes only
read-only, versioned LXC identity and fingerprint contracts and tests. It does
not change planning, translation, Agent or Core execution gates, capability
advertisement, selector requestability, handler registration, ACLs, or provider
state.

P2 must prevent the existing broad `operational_intent:create` permission from
silently authorizing future tuples. Every tuple must also match across Agent
planning, translation, and execution plus Core execution, semantic action,
handler, descriptor, and selector sources; mismatches fail closed without
auto-repair.

### Planned Phase 5

Distributed orchestration, clustering, multi-process locking, and cross-host recovery require a persistence and coordination design beyond the current local single-process Agent state store.
