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