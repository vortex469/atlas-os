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

Atlas Core context is retrieved once before workflow planning and retained as
an immutable workflow snapshot for planning, verification, and review. Resume
reuses that snapshot and does not contact Atlas Core again. Context retrieval
is read-only, has no retries, and is optional by default. Set
`ATLAS_CORE_REQUIRED=true` to block new workflows when context is unavailable.

Health and status are essential Atlas Core context. The typed Atlas Core client
also requests `/api/v1/intelligence/summary` as advisory enrichment. A
recognized intelligence connection, timeout, response, or payload failure is
recorded in the context without discarding valid health and status data.
Intelligence evidence may add bounded planning risks, but it never changes
execution commands, arguments, environment, working directories, approval
state, execution policy, verification commands, or commit behavior.

---

# Relationship to Mission Control

Mission Control remains the primary user interface.

Mission Control currently displays Atlas Agent repository, sprint,
verification, and review state. Its Atlas Agent data hook also loads pending
approvals, and an approval card can submit decisions through the Atlas Agent
approval API. The current status panel does not yet mount that approval card.

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

Awaiting implementation approval
    ↓

Implementation execution
    ↓

Awaiting verification approval
    ↓

Verification
    ↓

Review
    ↓

Awaiting commit approval
    ↓

Commit

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

Every engineering change must pass through this workflow.

---

# Human Approval

Human approval is a required engineering gate.

The approval workflow includes:
- Pause at defined tool execution points
- Resume after human approval
- Mission Control visibility of approval status

Atlas Agent may recommend changes.

Atlas Agent may verify changes.

Atlas Agent may review changes.

Implementation execution, verification commands, and the final deterministic
Git commit each have independent approval boundaries. Missing or pending
approvals keep the workflow waiting. Rejected, invalid, or mismatched approvals
block the workflow.

Resume is stage-aware and idempotent. Implementation does not replay after the
verification approval pause, verification and review do not replay after the
commit approval pause, and commit executes at most once. Atomic compare-and-swap
state transitions protect each side-effect stage. Execution, verification,
review, and commit artifacts persist in the immutable workflow session between
approval pauses.

Commit approval is bound to immutable repository evidence: expected branch,
expected HEAD, exact reviewed changed paths, a content/status fingerprint, and
the commit message. Repository drift before commit blocks the workflow.

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

# Architecture

For detailed architecture documentation, see [ARCHITECTURE.md](./ARCHITECTURE.md).

---

# Current Implementation Status

For checkpoint details, see [ROADMAP.md](./ROADMAP.md).

- A0–A7 are complete.
- A8 is partially complete. Its first production slice consumes bounded Atlas
  intelligence summary evidence through Atlas Core.
- A9 is complete.
- A10 is partially complete.
- A11 is functionally complete.
- A12 is complete for its currently defined approval-boundary scope.
- A13 is partially complete.
- A14 is complete for its currently listed status scope; it overlaps the
  earlier A7 Mission Control checkpoint. Pending approval data and decision UI
  exist, but the decision card is not mounted in the current status panel.
- A15 is partially complete.

---

# HTTP Endpoints

Atlas Agent exposes these operational and workflow endpoints:

```text
GET /health
GET /diagnostics
GET /api/v1/agent/info
GET /api/v1/agent/repository
GET /api/v1/agent/sprint
GET /api/v1/agent/verification
GET /api/v1/agent/review
POST /api/v1/agent/approval/request
GET /api/v1/agent/approval/pending
GET /api/v1/agent/approval/{request_id}
POST /api/v1/agent/approval/{request_id}/decision
POST /api/v1/agent/workflows
POST /api/v1/agent/workflows/{workflow_id}/resume
```

`GET /api/v1/agent/info` returns the configured application name,
runtime environment, repository root, development version marker, and
the workflow and verification states supported by the service.

Starting a workflow performs deterministic planning and returns an approval
request without executing the implementation. Resume is stage-aware: each
approved side-effect stage is atomically claimed once, artifacts are retained in
the immutable workflow session, and later resumes continue from the current
approval boundary rather than replaying completed stages. Workflow and approval
state is persisted as a local file-backed aggregate snapshot under
`ATLAS_AGENT_STATE_DIR`. Approval-boundary workflows survive process restart,
while interrupted `EXECUTING`, `VERIFYING`, and `COMMITTING` side-effect stages
recover as blocked rather than being replayed.

The local snapshot is single-process file-backed persistence for Atlas Agent's
own workflow coordination state. It is not broader Atlas platform persistence,
and it does not provide a distributed store, database, multi-process
coordination, or cross-host recovery. Redacted verification environment values
must match current environment values after restart before verification can
continue. Corrupt or unsupported snapshots block startup.

---

# Local Model Assistance

Atlas Agent has a replaceable model-provider interface, an Ollama provider, a
model service, and optional model-assisted planning analysis. Deterministic
planning remains the source of the implementation plan. Model-assisted review,
model selection, and autonomous model-driven execution are not implemented.
