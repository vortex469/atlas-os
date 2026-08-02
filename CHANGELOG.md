# Changelog

This project is under active development. Entries describe significant
operator-visible changes; Git tags remain the source of truth for exact
release boundaries.

## Unreleased

### Added

- Configurable loopback or LAN HTTP binding and an optional authenticated
  HTTPS ingress overlay.
- Online, integrity-checked backups and guarded restores for persistent
  action history and provider telemetry.
- Optional daily systemd backups with persistent scheduling, strict
  verification, and minimum-count retention safeguards.

## v1.0.0 — Foundry (2026-07-25)

### Added

- Specialized OPNsense, Frigate, Obsidian, Qdrant, and n8n providers.
- Provider-backed ACE findings with bounded concurrent collection.
- Persistent provider-intelligence telemetry, filtering, export, trends,
  and retention administration.
- Live provider policies, performance thresholds, structured validation
  diagnostics, and Mission Control policy views.
- Persistent action history with filtering, pagination, detail views,
  sanitized export, and confirmed retention maintenance.
- Reproducible development dependency manifests and runtime requirements.
- Hardened production containers for Atlas Core and Mission Control with
  health checks, an API proxy, and persistent telemetry storage.
- Isolated container release gate with runtime hardening assertions,
  HTTP smoke checks, automatic cleanup, and GitHub Actions coverage.
- Pinned Core and Mission Control quality gates, a release checklist, and
  the project MIT license.

### Changed

- Atlas Core integration tests now use a thread-free in-process ASGI
  harness.
- Mission Control exposes provider telemetry, trends, policy status, and
  operational retention controls.
- Removed a stale tracked test backup from release source archives.

## Historical development tags

- `v0.7.0-foundry` — deployment planning, risk engine, and Forge workflow.
- `foundry-0.4.0` — Mission Control provider architecture.
- `v0.3.0-alpha2` — reusable knowledge-engine assessment rules.
- `v0.3.0-alpha1` — Atlas Intelligence Engine and summary API.
- `v0.2.0` — typed ACE policy engine.

### Architecture

- Completed Phase 3 candidate workflow from Discovery compatibility evidence through local Git commit.
- Added deterministic end-to-end candidate workflow coverage, audit-chain validation, recovery matrix coverage, concurrency hardening, commit-path security hardening, strict request validation, and route-contract regression coverage.
- Documented v0.6 boundaries: only `update-compose-stack` is supported; Atlas does not push, tag, release, deploy remotely, auto-approve, auto-execute, or roll back changes.

### Security

- Candidate commits are constrained to exact reviewed files and reject unsafe paths such as `.git/`, `jcode/`, `logs/`, absolute paths, parent traversal, duplicates, empty paths, symlink escape, and unrelated changed files.
- Caller-controlled Phase 3 request bodies use strict validation so input cannot broaden command, path, approval, verification, evidence, or commit scope.
