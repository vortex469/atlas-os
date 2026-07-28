# Atlas Agent Roadmap

## Vision

Atlas Agent is the engineering orchestration service for Atlas.

Its purpose is to provide a repeatable engineering workflow from roadmap
checkpoint to verified implementation while keeping humans in control of
architectural decisions.

---

## A0 — Documentation

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

Goal

Review implementation against Atlas architecture.

Capabilities

- Architecture validation
- Scope validation
- Test coverage review
- Engineering recommendations

---

## A7 — Mission Control Integration

Goal

Expose Atlas Agent workflows through Mission Control.

Capabilities

- Repository status
- Sprint status
- Verification reports
- Review reports

---

## A8 — Knowledge Engine Integration

Goal

Use Atlas knowledge to improve planning.

Capabilities

- Architecture awareness
- Repository knowledge
- Best practices
- Historical context

---

## A9 — Workflow Automation

Goal

Coordinate engineering workflows.

Capabilities

- Sprint execution
- Verification pipeline
- Review pipeline
- Human approval gates

---

## A10 — Production Readiness

Goal

Prepare Atlas Agent for production use.

Deliverables

- Documentation complete
- Tests complete
- Performance validation
- Operational readiness

---

## A11 — Atlas Core Integration

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
- A11.1 Atlas Core Client
- A11.2 Context Aggregation
- A11.3 Planning Integration
- A11.4 Verification and Review Integration

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

---

## A12 — Approval-Gated Tool Execution

Goal

Enable tool execution that requires human approval.

Capabilities

- Git, Ruff, pytest, npm, and Docker execution
- explicit safety boundaries and approvals

---

## A13 — Local Model Orchestration

Goal

Orchestrate local language models for enhanced capabilities.

Capabilities

- local reasoning, planning, review, and model selection
- model implementations remain replaceable

---

## A14 — Mission Control Integration

Goal

Expose Atlas Agent workflows through the Atlas UI.

Capabilities

- repository status
- sprint status
- verification reports
- review reports

---

## A15 — Approval-Gated Development Loops

Goal

Orchestrate inspection, planning, editing, verification, review, and commits with human approval at defined write boundaries.

Capabilities

- orchestrate inspection, planning, editing, verification, review, and commits
- retain human approval at defined write boundaries
