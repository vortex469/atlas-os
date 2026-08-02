# Atlas Agent Decisions

## Overview

This document records key architectural decisions made for Atlas Agent.

## Core Principles

### Orchestration, Not Ownership

Atlas Agent orchestrates engineering workflows but does not own the underlying
tools or systems. It coordinates with other services rather than replacing them.

### Atlas Core is Authoritative

Atlas Core remains the authoritative source of Atlas system state.
All information accessed by Atlas Agent comes through supported Atlas Core APIs.

### API-Only Atlas State Access

Atlas Agent accesses Atlas state only through supported APIs.
Direct database access is not permitted.

### Engines Consume Normalized Typed Context

Each engine receives a normalized, typed context from the Context Engine.
Engines do not call Atlas Core independently.

### Write Operations and External Commands Require Approval

All write operations and external command execution require human approval
before proceeding. Implementation execution, verification commands, and the
final deterministic Git commit each have independent approval boundaries. This
ensures that no changes are made without proper oversight.

### Model Providers and Tool Executors Are Replaceable

The underlying model providers and tool executors remain replaceable.
This allows for flexibility in implementation while maintaining the overall architecture.

### Atlas Intelligence Is Advisory Enrichment

Atlas intelligence is retrieved only through the supported read-only Atlas Core
intelligence summary API. It supplies bounded evidence for planning and is not
an autonomous instruction source.

Recognized intelligence connection, timeout, response, and payload failures
preserve otherwise valid Atlas Core health and status context. The failure is
logged and represented in `AgentContext` with a stable code and predefined
message.

Intelligence content cannot modify executable commands, arguments,
environment, working directories, execution policy, approval state,
verification commands, commit approval evidence, or deterministic commit
behavior.

### Approval Boundary Resume Semantics

The production workflow is:

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

Workflow resume is stage-aware and idempotent. Implementation does not replay
after the verification approval pause, verification and review do not replay
after the commit approval pause, and commit executes at most once. Atomic
compare-and-swap transitions protect each side-effect stage. Execution,
verification, review, and commit artifacts persist in the immutable workflow
session between approval pauses.

Commit approval is bound to immutable repository evidence including expected
branch, expected HEAD, exact reviewed changed paths, a content/status
fingerprint, and commit message. Repository drift before commit blocks the
workflow. Missing or pending approvals keep the workflow waiting. Rejected,
invalid, or mismatched approvals block the workflow.

Workflow and approval state is persisted as a local file-backed aggregate
snapshot under `ATLAS_AGENT_STATE_DIR`. Approval-boundary workflows survive
process restart. Interrupted `EXECUTING`, `VERIFYING`, and `COMMITTING`
side-effect stages recover as blocked rather than being replayed.

This persistence is local and single-process. It does not provide a distributed
store, database, multi-process coordination, or cross-host recovery. Redacted
verification environment values require matching current environment values
after restart, and corrupt or unsupported snapshots block startup.

### Production Service Deployment Boundary

Atlas Agent owns its service-specific production deployment artifacts, not the
broader Atlas platform deployment strategy.

The dedicated production image is built by `deploy/docker/atlas-agent.Dockerfile`
from Python 3.12 slim. The runtime contains Python, Uvicorn through the service
runtime dependencies, Atlas Agent, and Git. Project-specific workflow tools such
as Codex, Ruff, pytest, Node/npm, Docker, and repository-specific verification
toolchains are intentionally not bundled and must be provided by the operator
when a workflow requires them.

Production Compose uses two repository path concepts. `ATLAS_REPOSITORY_HOST_PATH`
is a Compose-only operator-selected host path. Atlas Agent receives
`ATLAS_AGENT_REPOSITORY_ROOT=/workspace/repository`, and Compose mounts the host
path at `/workspace/repository`. The application therefore remains independent
of the host filesystem layout. Local workflow and approval snapshots are stored
on the `atlas-agent-state` volume.

Atlas Agent is exposed only inside the production Docker network on port 8090.
Mission Control proxies `/agent-api/` to Atlas Agent and strips that prefix.
HTTPS traffic continues through `atlas-edge` to Mission Control and then to
Atlas Agent. Production health checks use `/health`, and the release gate covers
image build, production and HTTPS Compose validation, health, hardening, mount
checks, absence of published Atlas Agent host ports, the writable
`atlas-agent-state` volume, and `/agent-api` HTTP and HTTPS smoke tests.

## v0.6 Phase 3 decisions

- Candidate workflows start from Atlas Core execution candidates and planning-intake revalidation. Agent never reads Core databases directly.
- The only supported candidate execution intent is `update-compose-stack`.
- Implementation requests, verification plans, and commit requests are immutable and persisted before approval.
- Implementation, verification, and commit each require separate exact approval.
- Workflow resume is state-driven and idempotent. Interrupted side-effect states recover blocked instead of replaying.
- Candidate audit validation uses machine-readable identifiers and fingerprints and does not parse rationale, titles, descriptions, or recommendation prose.
- Candidate commit is local only and limited to exact reviewed repository-relative files. Atlas Agent does not push, tag, release, deploy remotely, auto-approve, auto-execute, or roll back changes.
