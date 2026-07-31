# Atlas Agent Decisions

## Overview

This document records key architectural decisions made for Atlas Agent.

## Core Principles

### Orchestration, Not Ownership

Atlas Agent orchestrates engineering workflows but does not own the underlying
tools or systems. It coordinates with other services rather than replacing them.

### Atlas Core is Authoritative

Atlas Core remains the authoritative source of Atlas system state.
All information accessed by Atlas Agent comes through supported Atlas Core APIs.

### API-Only Atlas State Access

Atlas Agent accesses Atlas state only through supported APIs.
Direct database access is not permitted.

### Engines Consume Normalized Typed Context

Each engine receives a normalized, typed context from the Context Engine.
Engines do not call Atlas Core independently.

### Write Operations and External Commands Require Approval

All write operations and external command execution require human approval
before proceeding. Implementation execution, verification commands, and the
final deterministic Git commit each have independent approval boundaries. This
ensures that no changes are made without proper oversight.

### Model Providers and Tool Executors Are Replaceable

The underlying model providers and tool executors remain replaceable.
This allows for flexibility in implementation while maintaining the overall architecture.

### Atlas Intelligence Is Advisory Enrichment

Atlas intelligence is retrieved only through the supported read-only Atlas Core
intelligence summary API. It supplies bounded evidence for planning and is not
an autonomous instruction source.

Recognized intelligence connection, timeout, response, and payload failures
preserve otherwise valid Atlas Core health and status context. The failure is
logged and represented in `AgentContext` with a stable code and predefined
message.

Intelligence content cannot modify executable commands, arguments,
environment, working directories, execution policy, approval state,
verification commands, commit approval evidence, or deterministic commit
behavior.

### Approval Boundary Resume Semantics

The production workflow is:

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

Workflow resume is stage-aware and idempotent. Implementation does not replay
after the verification approval pause, verification and review do not replay
after the commit approval pause, and commit executes at most once. Atomic
compare-and-swap transitions protect each side-effect stage. Execution,
verification, review, and commit artifacts persist in the immutable workflow
session between approval pauses.

Commit approval is bound to immutable repository evidence including expected
branch, expected HEAD, exact reviewed changed paths, a content/status
fingerprint, and commit message. Repository drift before commit blocks the
workflow. Missing or pending approvals keep the workflow waiting. Rejected,
invalid, or mismatched approvals block the workflow.

Approval and workflow repositories remain in memory, so process-restart recovery
is not implemented.
