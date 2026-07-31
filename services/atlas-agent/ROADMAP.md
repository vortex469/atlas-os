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

Configuration validation, diagnostics, structured failures, and broad automated
tests are implemented. Documentation synchronization is A10.1. Recorded
performance validation and remaining operational-readiness evidence are still
unfinished.

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

Status: partially complete

Goal

Enable tool execution that requires human approval.

Capabilities

- Git, Ruff, pytest, npm, and Docker execution
- explicit safety boundaries and approvals

Implementation execution through the current Codex tool policy is
approval-gated. Verification commands and the final deterministic Git commit do
not yet have independent approval boundaries. The broader Ruff, pytest, npm,
Git, and Docker approval matrix remains unfinished.

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
controlled implementation, verification, review, and deterministic commit
handling. Granular approval boundaries for verification commands and the final
commit remain unfinished.

---

## Next Implementation Checkpoint

A10.1 synchronizes documentation only. After it, both a further bounded A8
knowledge increment and A12 granular approval work remain valid next steps.
The existing roadmap does not define a sub-checkpoint ordering between those
unfinished tracks, so the next implementation checkpoint is pending human
selection.
