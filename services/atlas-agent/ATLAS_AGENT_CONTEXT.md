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

Implementation
↓

Verification
↓

Review
↓

Human Approval
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

Atlas Agent does not own:

- Authentication
- Authorization
- Persistence
- Deployment
- CI
- Source control
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

The current implementation pauses before implementation execution and resumes
only after a matching approval. Verification commands and the final
deterministic Git commit do not yet have independent approval boundaries.

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

- A0–A7 are complete.
- A8 is partially complete with bounded advisory Atlas intelligence summary
  integration.
- A9 is complete.
- A10 is partially complete; A10.1 synchronizes documentation.
- A11 is functionally complete.
- A12 and A13 are partially complete.
- A14 is complete for its listed Mission Control status scope and overlaps A7;
  pending approval data is loaded, but its decision card is not mounted in the
  current status panel.
- A15 is partially complete.

Atlas Core health and status are essential context. Intelligence is optional
advisory enrichment: recognized intelligence failures preserve valid health
and status data and are represented deterministically in `AgentContext`.
Intelligence content is evidence only and cannot alter execution or approval
inputs.

After A10.1, the roadmap leaves the ordering between the next bounded A8
increment and A12 granular approval work to human selection.
