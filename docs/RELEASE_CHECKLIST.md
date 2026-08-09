# Foundry Release Checklist

Use this checklist before creating a Foundry release tag.

## Automated gates

- [x] Atlas Core installs from `requirements-dev.txt`.
- [x] Atlas Core test suite passes.
- [x] Mission Control installs reproducibly with `npm ci`.
- [x] Mission Control tests, lint, and production build pass.
- [x] Production Compose configuration validates without resolving
  credential values.
- [x] Both production images build from digest-pinned bases.
- [x] Isolated containers become healthy and run as non-root users with
  read-only root filesystems, dropped capabilities, and privilege
  escalation disabled.
- [x] Mission Control, the API proxy, security headers, and SPA deep links
  pass live HTTP smoke checks.
- [x] Container-gate cleanup leaves no temporary Docker resources.
- [x] Python dependency audit reports no known vulnerabilities.
- [x] Repository scan contains no committed production credentials.

The application quality gates run in `.github/workflows/quality-gates.yml`.
The production container gate runs the same
`scripts/container-release-gate` command locally and in GitHub Actions.
Third-party actions are pinned to exact commits.

## Release artifacts

- [x] MIT license is present.
- [x] README, changelog, roadmap, architecture, deployment, and dependency
  security documentation are populated.
- [x] `.dockerignore` excludes credentials, local databases, virtual
  environments, dependencies, builds, and logs.
- [x] Tracked editor backup files are removed.
- [x] The public release identifier is consistently `Foundry`.

## Accepted exception

`npm audit` currently reports the React Router RSC action CSRF advisory.
Mission Control is a client-rendered SPA and does not expose the affected
RSC/server-action path. No stable React Router version avoids both that
advisory and the older high-severity advisory range. The dated rationale
and re-audit requirement are recorded in `docs/DEPENDENCY_SECURITY.md`.

## Operator approval

Complete these items immediately before tagging:

- [x] Rotate and verify any credentials exposed during pre-release
  validation.
- [x] Review deployment-specific inventory, policy, and TLS settings.
- [x] Confirm the target branch contains only intended release commits.
- [x] Run `./scripts/container-release-gate` on the release commit.
- [x] Confirm required GitHub checks pass.
- [x] Create an annotated Foundry release tag and publish release notes.

Foundry `v1.0.0` was published on 2026-07-25 from commit `b32b21d`.
Production validation reported no critical issues. The release notes record
the operator-accepted warning for unavailable or unknown Home Assistant
entities.

## Atlas v0.6 release gates

### RC1 verification artifacts

- [ ] Record the exact commit checked for atlas-v0.6-rc1 packaging.
- [ ] Record commands used and pass/fail status for:
  - `cd services/atlas-core && python -m ruff check app tests`
  - `cd services/atlas-core && python -m pytest -q`
  - `cd services/atlas-agent && python -m ruff check app tests`
  - `cd services/atlas-agent && python -m pytest -q`
  - `cd services/mission-control && npm run lint`
  - `cd services/mission-control && npm test -- --run`
  - `cd services/mission-control && npm run build`
  - `./scripts/container-release-gate`

### RC1 candidate execution boundary

- [x] Supported execution intent is limited to `update-compose-stack`.
- [x] Structured Compose mutation evidence is required before implementation
  approval.
- [x] Legacy planning sessions without mutation evidence are non-actionable
  and require successor planning or replanning.
- [x] Approval binding, persistence/recovery, stale/fingerprint rejection, and
  successor concurrency/idempotent reuse are validated.
- [x] Codex authentication and runtime provisioning are validated.
- [ ] Codex-backed repository mutation is production-ready. This remains
  deferred to **Codex Execution Sandbox Hardening**.
- [ ] A reviewed narrow seccomp/AppArmor policy or isolated execution runtime
  passes disposable workspace-write, outside-workspace denial, authenticated
  end-to-end execution, verification, review, and commit-boundary tests while
  preserving uid `10001`, `CapDrop=ALL` where applicable,
  `no-new-privileges`, and read-only rootfs.

### Manual release sign-off

- [ ] Release lead confirms changelog entry names the intended tag and scope.
- [ ] Rollback path and restore procedures are reviewed and approved for this RC.
- [ ] Operator confirms upgrade and post-upgrade smoke verification were performed.
- [ ] Release blocker list is empty for the following:
  - no auto-approve, no auto-execute,
  - no push, tag, release publication, remote deploy, and no rollback automation.
- [ ] Operator sign-off and date are recorded in release notes or issue tracker:
  - Sign-off name:
  - Sign-off date:

- [ ] Changelog, version, tag name, upgrade notes, and manual rollback notes are
  reviewed.
- [ ] Use an immutable RC tag that does not overwrite existing release tags.

### Core

- [ ] `cd services/atlas-core && python -m ruff check app tests`
- [ ] `cd services/atlas-core && python -m pytest -q`
- [ ] Execution candidate, planning-intake, and route-contract tests pass.
- [ ] API/OpenAPI contract regression is current.

### Atlas Agent

- [ ] `cd services/atlas-agent && python -m ruff check app tests`
- [ ] `cd services/atlas-agent && python -m pytest -q`
- [ ] End-to-end candidate workflow test passes.
- [ ] Audit-chain validator tests pass.
- [ ] Restart-recovery matrix tests pass.
- [ ] Concurrency and idempotency tests pass.
- [ ] Commit-path security tests pass.
- [ ] Roadmap workflow regression tests pass.

### Mission Control

- [ ] `cd services/mission-control && npm run lint`
- [ ] `cd services/mission-control && npm test -- --run`
- [ ] `cd services/mission-control && npm run build`
- [ ] UI does not imply unsupported Phase 3 execution controls.

### Security and release operation

- [ ] Approval-boundary review confirms exact immutable implementation, verification, and commit approvals.
- [ ] No automatic approval, automatic execution, push, tag, release, remote deploy, or rollback path is enabled.
- [ ] No secrets, logs, `jcode/`, local state, dependency folders, virtual environments, or generated builds are committed.
- [ ] State migration and restart-recovery tests pass.
- [ ] Docker or Compose smoke validation passes when deployment packaging is in scope.
- [ ] `git diff --check` passes.
- [ ] `git status --short` is clean except explicitly local-only ignored directories before tagging.
- [ ] Review docs for RC tag/sequence selection before creating the next release tag.
