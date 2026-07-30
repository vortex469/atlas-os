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
- Future LLM Orchestrator
- Future tool-execution layer
- Mission Control as the future user interface

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

## Future Development

Future capabilities will include:

- LLM orchestration
- Tool execution
- Mission Control integration

## Context Model

Atlas Agent uses a conceptual typed AgentContext to represent system state.
The AgentContext contains:
- repository context
- Atlas system context:
  - services
  - providers
  - infrastructure relationships
  - Orion recommendations
  - Mission Control status
- runtime context
- workflow context
- user request

Engines consume normalized context and do not call Atlas Core independently.

Atlas Core context is captured exactly once before workflow planning. The
immutable snapshot is stored with the workflow session and is passed to
planning, verification, and review. Resuming a workflow reuses the stored
snapshot and never retrieves fresh Atlas Core context. When Atlas Core is
optional, retrieval failures preserve repository-only workflows; required mode
blocks before planning. An asynchronous application-composition layer retrieves
the context and then invokes the synchronous Workflow Engine. The read-only
integration does not poll or retry.

## Dependency Flow

The dependency flow is:

Mission Control
  -> Atlas Agent API
  -> Context Engine / Workflow Engine / future LLM Orchestrator
  -> Atlas Core Client
  -> Atlas Core APIs

This ensures Atlas Core remains the authoritative source of system state,
while Atlas Agent provides a consistent orchestration layer for engineering workflows.

## Design Principles

- Engines receive normalized context from the Context Engine
- Engines do not gather Atlas Core data independently
- Model providers and tool executors remain replaceable behind interfaces
- Writes and external command execution require explicit approval
