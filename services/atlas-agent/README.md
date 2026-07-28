# Atlas Agent

## Mission

Atlas Agent is the engineering orchestration service for Atlas.

Its purpose is to coordinate software engineering workflows by combining
planning, implementation, verification, review, and human approval into a
single repeatable process.

Atlas Agent does **not** replace Git, Codex, pytest, Ruff, Docker, or other
engineering tools. It orchestrates them.

---

# Responsibilities

Atlas Agent owns five engineering responsibilities.

## Planning

Generate implementation plans from approved roadmap checkpoints and
architectural guidance.

Planning determines:

- implementation scope
- affected components
- required tests
- implementation risks

Planning never modifies source code.

---

## Execution

Coordinate implementation through approved engineering tools.

Execution is responsible for:

- launching implementation workflows
- monitoring progress
- collecting execution results

Execution does not decide architecture.

---

## Verification

Verify every implementation before review.

Verification may execute:

- pytest
- Ruff
- frontend tests
- builds
- other project-specific validation

Verification reports results without changing source code.

---

## Review

Review completed work against the approved architecture.

Review answers questions such as:

- Does the implementation match the approved design?
- Is the change larger than necessary?
- Are required tests present?
- Does the implementation follow Atlas conventions?

Review produces recommendations.

Review never commits code.

---

## Reporting

Produce structured engineering reports.

Reports summarize:

- modified files
- test results
- verification status
- review findings
- overall recommendation

---

# Atlas Responsibilities

Atlas Agent owns:

- engineering orchestration
- workflow coordination
- implementation planning
- verification
- review
- engineering reports

Atlas Agent does not own:

- authentication
- authorization
- persistence
- deployment
- cloud infrastructure
- CI systems
- package management
- source control

Those responsibilities remain with their existing Atlas services or external tools.

---

# Relationship to Atlas Core

Atlas Core remains the primary platform for Atlas capabilities.

Atlas Agent consumes architectural context and project information when
required but does not replace Atlas Core functionality.

---

# Relationship to Mission Control

Mission Control remains the primary user interface.

Atlas Agent is expected to expose engineering workflows that Mission Control
may present to the user.

Mission Control is responsible for user interaction.

Atlas Agent is responsible for engineering orchestration.

---

# Relationship to Orion

Orion remains an independent Atlas capability.

Atlas Agent may integrate with Orion where engineering workflows benefit
from Orion functionality.

Atlas Agent does not redefine Orion's responsibilities.

---

# Engineering Workflow

Atlas Agent follows a fixed engineering workflow.

Roadmap
    ↓

Architecture
    ↓

Planning
    ↓

Implementation
    ↓

Verification
    ↓

Review
    ↓

Human Approval
    ↓

Commit

Every engineering change must pass through this workflow.

---

# Human Approval

Human approval is a required engineering gate.

Atlas Agent may recommend changes.

Atlas Agent may verify changes.

Atlas Agent may review changes.

Only a human approves changes for commit.

No implementation is committed automatically.

---

# Design Principles

Atlas Agent follows these principles.

- Architecture is designed by humans.
- AI assists implementation.
- Small changes are preferred.
- Every change is verifiable.
- Every change is reviewable.
- Every change is reversible.
- Human approval precedes every commit.

These principles guide every future Atlas Agent capability.
---

# HTTP Endpoints

Atlas Agent exposes the following read-only operational endpoints:

```text
GET /health
GET /api/v1/agent/info
GET /api/v1/agent/repository
GET /api/v1/agent/sprint
GET /api/v1/agent/verification
GET /api/v1/agent/review
```

`GET /api/v1/agent/info` returns the configured application name,
runtime environment, repository root, development version marker, and
the workflow and verification states supported by the service.
