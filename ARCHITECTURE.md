# Atlas Architecture

Atlas is a local-first, provider-neutral infrastructure control plane. It helps operators understand infrastructure, convert deterministic findings into candidate work, and execute only the narrow changes that receive explicit human approval.

Atlas v0.6 focuses on the Phase 3 candidate workflow. The only supported execution intent is `update-compose-stack`.

Atlas does not push, tag, publish releases, deploy remotely, auto-approve, or auto-execute work.

## Subsystems and responsibilities

### Atlas Core

Atlas Core owns the authoritative system view and public platform API. It collects provider state, exposes Discovery Center catalog and compatibility evidence, lets Orion-owned intelligence produce recommendations, projects execution candidates, and performs planning-intake revalidation.

Atlas Core does not execute candidate work. It does not grant approval for Agent side effects.

### Discovery Center

Discovery Center owns provider-neutral catalog facts and deterministic compatibility evidence. It is read-only and curated-catalog-first. Dynamic discovery, semantic search, and execution are future work.

### Intelligence and execution candidates

Atlas intelligence consumes Discovery compatibility evidence and emits explainable recommendations. Execution candidate projection converts eligible recommendations into structured candidate records with stable identifiers and fingerprints.

### Atlas Agent

Atlas Agent owns local engineering orchestration. It creates candidate planning sessions, deterministic candidate plans, workflow shells, immutable implementation requests, verification plans, audit-chain validation, deterministic review, and local Git commits.

Agent state is local-first and file-backed under `ATLAS_AGENT_STATE_DIR`. Side-effect stages are approval-gated, persisted, restart-aware, and at-most-once.

### Mission Control

Mission Control is the operator UI. It displays Atlas Core, Discovery, and Agent state. It does not currently expose Phase 3 candidate execution controls and must not bypass Core or Agent approval boundaries.

## Ownership boundaries

- Core owns candidate source authority and revalidation.
- Agent owns local workflow orchestration and side-effect gating.
- Mission Control owns presentation and user interaction.
- External tools own their own effects, such as Codex implementation, Docker Compose verification, and Git.
- Operators own approval decisions.

## Trust boundaries

- Caller-controlled API bodies use strict request models and cannot supply commands, paths, evidence, or approval overrides for candidate side effects.
- Candidate execution starts only from Core-projected candidates and stable fingerprints.
- Implementation, verification, and commit approvals bind to exact immutable requests.
- Raw secrets, authorization headers, uncontrolled command output, and broad diffs must not be logged or persisted as public contract data.
- Local Git commit is the final implemented Phase 3 side effect. Push, tag, release, rollback, and remote deployment are outside v0.6 scope.

## Phase 3 pipeline

```mermaid
flowchart TD
    A[Discovery catalog and compatibility evidence] --> B[Atlas intelligence finding]
    B --> C[Execution candidate]
    C --> D[Core planning intake revalidation]
    D --> E[Agent candidate planning session]
    E --> F[Deterministic candidate plan]
    F --> G[Workflow shell]
    G --> H[Immutable implementation request]
    H --> I[Exact implementation approval]
    I --> J[Implementation execution]
    J --> K[Verification plan]
    K --> L[Exact verification approval]
    L --> M[Verification evidence]
    M --> N[Deterministic review]
    N --> O[Exact commit approval]
    O --> P[Local Git commit]
    P --> Q[Completed workflow]
```

## Approval flow

Each side-effect stage has its own approval boundary.

1. Implementation approval authorizes one immutable implementation request with exact command, arguments, working directory, and evidence.
2. Verification approval authorizes one immutable verification plan with exact checks.
3. Commit approval authorizes one immutable commit request with exact branch, HEAD, reviewed files, fingerprint, and message.

Rejected, mismatched, missing, or stale approvals block the workflow. Empty-command approval records cannot authorize execution. Later-generated work cannot inherit an earlier approval.

## Restart behavior

Planning, workflow conversion, implementation translation, execution, verification, review, and commit artifacts are persisted. Approval-wait states restore unchanged. Completed and blocked workflows restore unchanged with their artifacts. Interrupted side-effect states such as executing, verifying, and committing recover as blocked rather than replaying the side effect.

Aggregate snapshots are atomic and versioned. Corrupt, unsupported, or partially written active snapshots fail safely instead of silently resuming unsafe state.

## Audit chain

Candidate workflows preserve machine-readable links across:

- finding identity
- execution candidate ID and fingerprint
- candidate planning session ID
- candidate plan ID and fingerprint
- workflow ID and candidate metadata
- implementation request and approval IDs
- execution result
- verification plan, approval, and evidence IDs
- candidate review result and generic review report
- commit request, approval, result SHA, and committed files

Audit validation uses identifiers and fingerprints, never rationale, titles, descriptions, or recommendation prose.

## Supported and unsupported operations

Supported in v0.6:

- `update-compose-stack` candidate workflows that end in a local Git commit.

Not supported in v0.6:

- `restart-service`
- `backup`
- `restore`
- `install-provider`
- `update-image`
- push
- tag
- release publication
- remote deployment
- rollback automation
- automatic approval
- automatic execution
