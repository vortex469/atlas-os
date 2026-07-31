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
implementation execution. Verification commands and the final Git commit do
not yet have independent approval boundaries.

### Mission Control

Mission Control displays repository, sprint, verification, and review state.
Its Agent data hook loads pending approvals, and its approval card can submit
decisions, but that card is not mounted in the current status panel. Workflow
execution remains an Atlas Agent responsibility.

## Context Model

Atlas Agent uses a typed, immutable `AgentContext` snapshot. The implemented
context contains Atlas identity and release data, service health, and optional
advisory intelligence findings, assessments, and recommendations. Repository
state remains a separate immutable planning input.

Engines consume normalized context and do not call Atlas Core independently.

Atlas Core context is captured exactly once before workflow planning. The
immutable snapshot is stored with the workflow session and is passed to
planning, verification, and review. Resuming a workflow reuses the stored
snapshot and never retrieves fresh Atlas Core context. When Atlas Core is
optional, retrieval failures preserve repository-only workflows; required mode
blocks before planning. An asynchronous application-composition layer retrieves
the context and then invokes the synchronous Workflow Engine. The read-only
integration does not poll or retry.

Health and status are essential context. Intelligence summary retrieval is
advisory enrichment. Recognized intelligence failures are logged and recorded
with a stable failure code and message while valid health and status context
remains usable. Planning may emit one unavailable-intelligence risk or at most
five ordered, deduplicated intelligence evidence risks. Intelligence content
cannot alter commands, arguments, environment, working directories, approval
state, execution policy, verification commands, or commit behavior.

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

The final principle describes the target architecture. Currently,
implementation execution is approval-gated, while verification commands and
the final commit do not yet have separate approval decisions.

## Future Development

Genuinely unfinished capabilities include broader historical knowledge,
additional bounded Knowledge Engine integration, granular approval boundaries
for verification and commit operations, model-assisted review, and model
selection.
