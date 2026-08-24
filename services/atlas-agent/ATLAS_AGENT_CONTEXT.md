# Atlas Agent Context

## Purpose

This document defines the engineering rules that govern Atlas Agent.

All implementations must follow these principles.

---

# Architecture Ownership

Architecture is designed by humans.

AI assists implementation.

AI must not invent new architecture.

If implementation requires architectural changes,
implementation stops until the architecture is approved.

---

# Engineering Workflow

Every change follows the same workflow.

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

No step may be skipped.

---

# Responsibilities

Atlas Agent owns:

- Planning
- Execution
- Verification
- Review
- Reporting
- Local workflow aggregate persistence and restart recovery required for its
  approved workflows
- The exact approved local Git staging and commit boundary for supported
  repository execution

Atlas Agent does not own:

- Authentication
- Authorization
- Broader Atlas/Core durable-state persistence
- External infrastructure or provider persistence
- Deployment
- CI
- Remote source-control authority, including push, tag creation, and release
  publication
- Arbitrary source-control operations
- Package management

---

# Implementation Rules

Implement only the approved scope.

Do not:

- invent abstractions
- redesign existing Atlas services
- rewrite unrelated files
- introduce unnecessary dependencies
- expand scope

Prefer the smallest production-ready implementation.

---

# Repository Rules

Respect existing Atlas conventions.

Follow existing:

- module organization
- dependency injection
- naming
- testing
- formatting

Do not create new project conventions unless explicitly approved.

---

# Testing

Every implementation must include appropriate tests.

Verification should include only the tests affected by the change unless a
full suite is explicitly requested.

Never report success unless the requested verification actually ran.

---

# Review

Review focuses on:

- architectural consistency
- implementation scope
- correctness
- maintainability
- testing

Review recommendations must distinguish facts from opinions.

---

# Human Approval

Humans approve:

- architecture
- roadmap changes
- commits
- merges

AI may recommend.

AI never approves on behalf of a human.

The current implementation pauses independently before implementation
execution, verification commands, and the final deterministic Git commit.
Missing or pending approvals keep the workflow waiting. Rejected, invalid, or
mismatched approvals block the workflow.

Resume is stage-aware and idempotent: implementation does not replay after the
verification pause, verification and review do not replay after the commit
pause, and commit executes at most once. Atomic compare-and-swap transitions
protect each side-effect stage. Execution, verification, review, and commit
artifacts persist in the immutable workflow session between approval pauses.
Commit approval is bound to immutable repository evidence: expected branch,
expected HEAD, exact reviewed changed paths, a content/status fingerprint, and
the commit message. Repository drift before commit blocks the workflow.

---

# Design Philosophy

Atlas Agent is an engineering orchestrator.

It coordinates engineering tools.

It does not replace engineering tools.

The preferred solution is the simplest production-ready solution that
matches the approved architecture.

Future capabilities must extend the existing architecture rather than
replace it.

---

# Current Implementation Status

Atlas v0.14 has two separate Agent-facing work classes:

- Repository candidate execution supports exactly `update-compose-stack` and
  retains deterministic planning, immutable implementation/verification/commit
  requests, independent exact approvals, controlled execution, verification,
  deterministic review, local commit, persisted artifacts, and audit-chain
  validation.
- Hardened operational transport supports exactly
  `restart-service / proxmox / qemu`. Core owns operator authorization,
  lifecycle, target revalidation, dispatch, and recovery; Agent independently
  validates the authenticated immutable request and exact capability before the
  provider operation.

Legacy provider actions are separate from hardened operations. Provider Intent
is monitoring-policy authority only and is not Agent execution. Backup/restore
is operator maintenance tooling, not an Agent intent. No path accepts arbitrary
commands or automatically approves, remediates, updates, deploys, rolls back,
pushes, tags, or publishes releases.

Atlas Core health and status are essential immutable planning context.
Intelligence is optional advisory evidence and cannot alter commands, arguments,
environment, working directory, target, approval, execution policy,
verification, or commit behavior.

Repository workflow state persists as a local, single-process aggregate under
`ATLAS_AGENT_STATE_DIR`. Approval-wait, completed, and blocked states restore
without replay; interrupted side-effect states recover blocked. Core's separate
`operational_dispatch.db` owns durable operational safety and no-replay state.

Base production uses `ATLAS_EXECUTION_BACKEND=local`. The packaged isolated
worker/relay/egress backend is default-disabled and requires separately gated
activation and runtime validation. When activated, authenticated worker
requests pass through the relay; backend selection never expands the allowed
intent registry.

For current system and component boundaries, use
[Atlas architecture](../../ARCHITECTURE.md), [Agent architecture](ARCHITECTURE.md),
and [Agent README](README.md). Roadmaps and historical phase records provide
history, not current release authority.
