# Atlas Agent Architecture

## Overview

Atlas Agent is the orchestration layer for Atlas AI.

Atlas Agent performs orchestration, not ownership.
It does not own repository, infrastructure, provider, Orion, or Mission Control state.

Atlas Core remains the authoritative source of Atlas system state.
Atlas Agent retrieves Atlas system data only through supported Atlas Core APIs.
Atlas Agent never reads Atlas Core databases or persistence implementations directly.

## Core Components

The following engines compose the Atlas Agent architecture:

- Atlas Agent API
- Repository Inspection
- Context Engine
- Workflow Engine
- Planning Engine
- Verification Engine
- Review Engine
- Atlas Core Client
- Model Provider and Model Service
- Controlled tool-execution layer
- Mission Control integration

## Engine Responsibilities

### Atlas Agent API

The Atlas Agent API provides endpoints for interaction with the orchestration service.

### Repository Inspection

The Repository Inspection engine analyzes Git repository state to provide context about the current codebase.

### Context Engine

The Context Engine receives and normalizes system context from Atlas Core.
It provides a unified view of the Atlas system to other engines.

### Workflow Engine

The Workflow Engine coordinates the overall engineering workflow.

### Planning Engine

The Planning Engine generates implementation plans based on roadmap checkpoints
and architectural guidance.

### Verification Engine

The Verification Engine validates implementation quality.

### Review Engine

The Review Engine ensures implementation matches approved architecture.

### Atlas Core Client

The Atlas Core Client provides typed access to Atlas system state through
supported APIs. It handles configuration, connection validation, and API calls.

### Model Assistance

Atlas Agent provides a replaceable model-provider interface, an Ollama
provider, a model service, and optional model-assisted planning analysis.
Deterministic planning remains authoritative. Model-assisted review, model
selection, and autonomous model-driven execution are future capabilities.

### Controlled Tool Execution

The Execution Engine validates repository and executable boundaries before
running the approved implementation command. The current policy permits Codex
implementation execution. Implementation execution, verification commands, and
the final deterministic Git commit each have independent approval boundaries.

### Mission Control

Mission Control displays repository, sprint, verification, and review state.
Its Agent data hook loads pending approvals, and its approval card can submit
decisions, but that card is not mounted in the current status panel. Commit
approval is additive to the existing approval API surface. Workflow execution
remains an Atlas Agent responsibility, and the approval decision UI remains a
separate usability and integration concern.

## Context Model

Atlas Agent uses a typed, immutable `AgentContext` snapshot. The implemented
context contains Atlas identity and release data, service health, and optional
advisory intelligence findings, assessments, and recommendations. Repository
state remains a separate immutable planning input.

Engines consume normalized context and do not call Atlas Core independently.

Atlas Core context is captured exactly once before workflow planning. The
immutable snapshot is stored with the workflow session and is passed to
planning, verification, and review. Resuming a workflow reuses the stored
snapshot and never retrieves fresh Atlas Core context. Execution, verification,
review, and commit artifacts also persist in the immutable workflow session
between approval pauses. When Atlas Core is optional, retrieval failures preserve
repository-only workflows; required mode blocks before planning. An asynchronous
application-composition layer retrieves the context and then invokes the
synchronous Workflow Engine. The read-only integration does not poll or retry.

Health and status are essential context. Intelligence summary retrieval is
advisory enrichment. Recognized intelligence failures are logged and recorded
with a stable failure code and message while valid health and status context
remains usable. Planning may emit one unavailable-intelligence risk or at most
five ordered, deduplicated intelligence evidence risks. Intelligence content
cannot alter commands, arguments, environment, working directories, approval
state, execution policy, verification commands, or commit behavior.

## Workflow State and Approval Boundaries

The production workflow states are:

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
compare-and-swap transitions protect each side-effect stage.

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

## Dependency Flow

The dependency flow is:

Mission Control
  -> Atlas Agent API
  -> Workflow Orchestrator
  -> Context Engine / Workflow Engine / optional Planning Advisor
  -> Atlas Core Client / Model Service / controlled tools
  -> supported Atlas Core APIs / Ollama / repository-scoped commands

This ensures Atlas Core remains the authoritative source of system state,
while Atlas Agent provides a consistent orchestration layer for engineering workflows.

## Design Principles

- Engines receive normalized context from the Context Engine
- Engines do not gather Atlas Core data independently
- Model providers and tool executors remain replaceable behind interfaces
- Writes and external command execution require explicit approval

The final principle is implemented for the current approval-boundary scope:
implementation execution, verification commands, and the final deterministic
Git commit each require separate approval decisions.

## Future Development

Genuinely unfinished capabilities include broader historical knowledge,
additional bounded Knowledge Engine integration, Docker policy beyond the
current approval-boundary scope, model-assisted review, model selection, and
broader development-loop hardening.
