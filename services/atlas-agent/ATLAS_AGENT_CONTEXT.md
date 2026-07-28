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

The current implementation is complete through A10.

A11 — Atlas Core Integration is the next checkpoint.

A12–A15 are the approved long-term direction.
