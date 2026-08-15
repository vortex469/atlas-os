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

## Dependency security

The prior React Router RSC action CSRF exception is resolved by
`react-router-dom@7.18.2`. The final dependency review reports zero npm
vulnerabilities and no known vulnerabilities in the Core or Agent Python
requirements. The dated resolution and transitive remediation record are in
`docs/DEPENDENCY_SECURITY.md`.

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

- [x] Record the exact commit checked for atlas-v0.6-rc1 packaging.
- [x] Record commands used and pass/fail status for:
  - `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-core`
  - `cd services/atlas-core && PATH=/opt/atlas/.venv/bin:$PATH python -m pytest -q`
  - `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-agent`
  - `PATH=/opt/atlas/.venv/bin:$PATH PYTHONPATH=services/atlas-agent python -m pytest -q services/atlas-agent/tests`
  - `cd services/mission-control && npm run lint`
  - `cd services/mission-control && npm test -- --run`
  - `cd services/mission-control && npm run build`
  - `./scripts/container-release-gate`

Validated on 2026-08-13 at commit
`70997b398727471d261a297e41831f5901b83a18`. Commands ran from
`/opt/atlas` unless a different working directory is shown:

| Command | Working directory | Exit | Result |
| --- | --- | ---: | --- |
| `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-core` | `/opt/atlas` | 0 | All changed-file checks passed. |
| `PATH=/opt/atlas/.venv/bin:$PATH python -m pytest -q` | `/opt/atlas/services/atlas-core` | 0 | 692 passed, 1 dependency deprecation warning. |
| `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-agent` | `/opt/atlas` | 0 | All changed-file checks passed. |
| `PATH=/opt/atlas/.venv/bin:$PATH PYTHONPATH=services/atlas-agent python -m pytest -q services/atlas-agent/tests` | `/opt/atlas` | 0 | 816 passed, 1 dependency deprecation warning. |
| `npm run lint` | `/opt/atlas/services/mission-control` | 0 | 0 errors, 1 React hook dependency warning. |
| `npm test -- --run` | `/opt/atlas/services/mission-control` | 0 | 28 files and 190 tests passed. |
| `npm run build` | `/opt/atlas/services/mission-control` | 0 | Production build passed with a chunk-size warning. |
| `./scripts/container-release-gate` | `/opt/atlas` | 0 | Compose rendering, production images, isolated hardened runtime, HTTP/HTTPS, data recovery, and Rest Server recovery passed. |

The literal Python commands were also attempted without the repository virtual
environment on this validation host. Both exited `127` because the host has no
global `python` executable. The successful commands above make the required
repository-local tool context explicit; CI supplies the equivalent Python tool
context through `actions/setup-python` and dependency installation.

### RC1 candidate execution boundary

- [x] Supported execution intent is limited to `update-compose-stack`.
- [x] Structured Compose mutation evidence is required before implementation
  approval.
- [x] Legacy planning sessions without mutation evidence are non-actionable
  and require successor planning or replanning.
- [x] Approval binding, persistence/recovery, stale/fingerprint rejection, and
  successor concurrency/idempotent reuse are validated.
- [x] Codex authentication and runtime provisioning are validated.
- [x] Codex-backed repository mutation is production-ready through the exact
  approval-gated candidate path.
- [x] A reviewed narrow seccomp/AppArmor policy or isolated execution runtime
  passes disposable workspace-write, outside-workspace denial, authenticated
  end-to-end execution, verification, review, and commit-boundary tests while
  preserving uid `10001`, `CapDrop=ALL` where applicable,
  `no-new-privileges`, and read-only rootfs.

### RC1 production execution smoke validation

Validated on commit `c333937e61343aed714a475395b41077bad86e28` using the final
production-like smoke workflow `candidate-workflow-6da0da7b4da397219e6f507ebd5439959584559529eb02a9598cdbd6a93aa866` and planning session
`candidate-plan-158f8db4f0c204de90f857ce2911cbf219dd900ae21e2b2f1a16037982baf200`.
The evidence bundle is retained at `/root/atlas-rc1-smoke-evidence/final-c333937/`.

- [x] Candidate intake, planning, candidate plan, workflow shell, shell
  approval, exact implementation approval, isolated worker execution, exact
  verification approval, deterministic RC1 verification, baseline-aware review,
  and the exact commit approval boundary were traversed successfully.
- [x] Worker execution succeeded with the worker attestation showing runtime
  uid `10001`, read-only rootfs, `no-new-privileges`, zero effective
  capabilities, and `runsc-squid` sandbox profile.
- [x] Repository HEAD remained frozen at
  `c333937e61343aed714a475395b41077bad86e28` throughout the successful
  lineage.
- [x] Exactly one approved tracked file changed:
  `services/atlas-agent/tests/test_execution_engine.py`.
- [x] The exact verification plan was persisted before approval. The gated
  RC1 zero-command verification passed without a fake or dummy command, and
  preserved repository HEAD and the validated changed-files digest.
- [x] Baseline-aware review excluded the pre-existing untracked
  `compose.execution-smoke.override.yaml`, passed with zero findings, and
  produced an exact commit approval request for branch `feature/atlas-agent`,
  the validated HEAD, and the one reviewed file.
- [x] The validation-only commit was intentionally not approved or performed.
  The marker was restored afterward and the tracked working tree is clean.
- [x] The smoke remediation set is covered by regression validation: worker
  journal exactly-once recovery, candidate audit approval-boundary projection,
  gated RC1 verification intent, baseline-aware verification, exact
  verification approval binding, candidate verification resume dispatch,
  approval-repository storage identity, AtlasCoreClient event-loop ownership,
  deterministic zero-check verification, and baseline-aware candidate review
  and commit validation.

The untracked `compose.execution-smoke.override.yaml` remains outside workflow
provenance. Recommendation: retain it as a maintained operator smoke harness
until the evidence and operator procedure are no longer needed, then remove it
through a separate reviewed cleanup decision.

## Atlas v0.7 P1.3 release-candidate readiness

### Operational capability and security boundary

- [x] Production capability is closed to `restart-service / proxmox / qemu`.
- [x] Core-owned operator sessions require authenticated HTTPS, one exact
  trusted origin, CSRF validation, and `operational_intent:create`.
- [x] Edge Basic authentication remains defense-in-depth and is not accepted as
  Core operator identity.
- [x] Agent-to-Core authentication is separate from browser authentication.
- [x] Authoritative QEMU identity and fingerprint revalidation bind planning,
  approval, dispatch, and verification.
- [x] Exact `OPERATIONAL_ACTION` approval binds the immutable action request ID,
  digest, target, provider action, verification policy, and expiry.
- [x] Core persists the dispatch barrier before provider mutation and never
  replays a crossed or ambiguous mutation boundary.
- [x] UPID-backed verification and verifier-only recovery are read-only.

### Production acceptance — 2026-08-14

- [x] Approved target: `vorex469 / VM 110 / Frigate`.
- [x] The normal operator-intent, planning, preparation-approval, exact-action
  approval, Agent dispatch, Core handler, and verification path completed.
- [x] Exactly one new `qmreboot`, one dispatching transition, one barrier
  crossing, one provider-operation capture, and one dispatch result occurred.
- [x] The production ledger reached `verified`; Agent projected the workflow as
  `completed`.
- [x] Final VM and QMP states were running and the authoritative fingerprint was
  unchanged.
- [x] No replay, sandbox path, non-production ledger, direct provider mutation,
  commit, tag, or release action occurred.

### Deployment sign-off required before an RC

- [x] Re-run and record the full Core, Agent, Mission Control, worker, Compose,
  container, dependency, and credential-hygiene gates on the final RC commit.
- [x] Push the reviewed documentation commit and require both GitHub workflows
  to pass on that exact SHA.
- [x] Document the supported
  [v0.6.0 to v0.7 upgrade and rollback](DEPLOYMENT.md#atlas-v060-to-v07-upgrade-and-rollback),
  including schema-v3 downgrade handling and in-flight dispatch preservation.
- [x] Review those v0.7 upgrade and rollback instructions and record
  release-lead sign-off.
- [x] Create an immutable RC tag only after the exact pushed SHA is green.
- [x] The final immutable `atlas-v0.7.0` tag was published at
  `8dbc43de73dda300b50c121f19324cb5174df2a9` after the documentation provenance
  fix and required CI passed on that exact final SHA.

### Final RC1 provenance and production soak — 2026-08-14

Release candidate `atlas-v0.7-rc1` resolves to
`5b1321091af0fc191844cdf71e9e0d919e4ea415`.

- [x] Quality gates run `31850208419` passed on the exact RC SHA: `atlas-core`,
  `atlas-agent`, and `mission-control` all succeeded.
- [x] Container release gate run `31850208435` passed on the exact RC SHA.
- [x] Dependency Graph run `31850211284` passed on the exact RC SHA.
- [x] Production was rebuilt from the exact RC1 checkout with no-cache images
  and deployed using only `compose.production.yaml`, `compose.https.yaml`, and
  `compose.operator-auth.yaml`. The untracked
  `compose.execution-smoke.override.yaml` was not used.
- [x] Running Core and Agent source checksums matched the RC1 checkout, and the
  running Mission Control image identity matched the exact RC1 build.
- [x] Sequential restarts of Atlas Agent, Atlas Core, Mission Control, and Atlas
  Edge passed; all production services were healthy afterward.
- [x] The completed operational workflow remained terminal, and the production
  ledger remained unchanged with exactly one historical barrier crossing, one
  historical provider operation, one historical dispatch result, and no
  replay.
- [x] VM 110's `qmreboot` count remained `3`, and its authoritative target
  fingerprint remained unchanged throughout the redeploy and soak.
- [x] Operator-auth private files remained untracked, and the trusted origin
  remained exactly `https://atlas.internal`.
- [x] Agent and Core execution gates remained exactly `restart-service`; the
  production registry remained exactly one tuple:
  `restart-service / proxmox / qemu`.

### Post-hardening RC1 execution validation

Validated on commit `0bddaf6ee46fbef94a2a1eb9f20cfcb1db0ca2be` using a fresh
isolated production-like stack, planning session
`candidate-plan-fa0a537f0715ad4f607287801dc6345e8b3f87ead146f0abb611a962ba6bd75e`,
and workflow
`candidate-workflow-783edad93fa08cf30c039b92fa94db0098b7431e170a37ee57c864adef28417d`.

- [x] Authenticated Agent-to-worker execution traversed the segmented relay.
- [x] Worker execution succeeded with uid `10001`, read-only rootfs,
  `no-new-privileges`, zero effective capabilities, and the
  `runsc-squid+atlas-workspace` sandbox profile.
- [x] Exactly `services/atlas-agent/tests/test_execution_engine.py` changed,
  with patch digest
  `sha256:8a97f55e972fadfe5d2e0a3d49456b38a057be61794da862ee4ad00c36e2455f`.
- [x] Exact zero-check verification passed, review approved with zero findings,
  and the machine-readable audit chain validated without a failure code.
- [x] The workflow stopped at `awaiting_commit_approval`; commit approval
  `approval-commit-candidate-workflow-783edad93fa08cf30c039b92fa94db0098b7431e170a37ee57c864adef28417d`
  remains pending and no validation-only commit was created.
- [x] The validation marker was restored and the isolated stack, volumes, and
  locally built smoke images were removed. The retained smoke override was not
  modified.

### RC1 Python lint baseline

The blocking RC1 Ruff gate checks Python files changed after commit
`0216b7bfe7f3b160a762269802aa34244ae70a72`, including untracked Python files,
using the pinned Ruff version in each service's development requirements. Core
checks `services/atlas-core/app`; Core has no separate `tests/` directory. Agent
checks both `services/atlas-agent/app` and `services/atlas-agent/tests`. Changed
production and test files must pass: no new Ruff violation may be introduced by
RC1 changes. Existing documented debt does not block RC1 by itself and remains
tracked for later cleanup rather than being fixed as release scope.

A fresh repository-wide informational scan with the validated toolchain on
2026-08-13 reports exactly 90 Core findings and 20 Agent findings. The Agent
count supersedes the earlier 18-finding observation; do not use the older
expected count of 22 unless it is independently reproduced.

The commands above show the repository-local virtual environment used for local
release validation. CI installs the same development requirements into the
Python environment supplied by `actions/setup-python`, so its equivalent
commands intentionally use `python` without the local `.venv` path prefix.

### Manual release sign-off

- [x] Release lead confirms changelog entry names the intended tag and scope.
- [x] Rollback path and restore procedures are reviewed and approved for this RC.
- [x] Operator confirms the upgrade and post-upgrade smoke verification
  procedure was reviewed.
- [x] Release blocker list is empty for the following:
  - no auto-approve, no auto-execute,
  - no push, tag, release publication, remote deploy, and no rollback automation.
- [x] Operator sign-off and date are recorded in release notes or issue tracker:
  - Sign-off name: Kenny Horner
  - Sign-off date: 2026-08-13
  - Release candidate commit: `0c7fde2c233799453948a81fd42b53717524f4c1`

- [x] Changelog, version, tag name, upgrade notes, and manual rollback notes are
  reviewed.
- [x] Use an immutable RC tag that does not overwrite existing release tags.
  `atlas-v0.6-rc1.9` was published at
  `6d85df5b112b4bde28ec31fc60cce88560c9dbfc` on 2026-08-13 and remains the
  immutable validated RC baseline.

### Atlas v0.6.0 final release

Authorized final tag candidate: `atlas-v0.6.0`.

- [x] Record the exact final integration commit SHA:
  `2d4a1b1929316589cdf6ea96993442b430826f10` on `main`.
- [x] Run and record the complete final technical validation. The local
  validation matrix and both required CI workflows are green.

The final local validation matrix was recorded on 2026-08-13 at
`d4abb0016f95aab3bee7ef7ce7820fb3fd941388`. Commands ran from `/opt/atlas`
unless a different working directory is shown:

| Command | Working directory | Exit | Result |
| --- | --- | ---: | --- |
| `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-core` | `/opt/atlas` | 0 | Baseline-aware Core Ruff passed. |
| `PATH=/opt/atlas/.venv/bin:$PATH python -m pytest -q` | `/opt/atlas/services/atlas-core` | 0 | 692 passed; 1 accepted dependency deprecation warning. |
| `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-agent` | `/opt/atlas` | 0 | Baseline-aware Agent Ruff passed. |
| `PATH=/opt/atlas/.venv/bin:$PATH PYTHONPATH=services/atlas-agent python -m pytest -q services/atlas-agent/tests` | `/opt/atlas` | 0 | 816 passed; 1 accepted dependency deprecation warning. |
| `npm ci` | `/opt/atlas/services/mission-control` | 0 | Clean install passed; 284 packages installed. |
| `npm audit --package-lock-only --audit-level=high` | `/opt/atlas/services/mission-control` | 0 | Zero vulnerabilities. |
| `npm run lint` | `/opt/atlas/services/mission-control` | 0 | 0 errors; 1 accepted hook warning. |
| `npm test -- --run` | `/opt/atlas/services/mission-control` | 0 | 28 files and 190 tests passed. |
| `npm run build` | `/opt/atlas/services/mission-control` | 0 | Production build passed with the accepted 681.92 kB chunk warning. |
| `/opt/atlas/.venv/bin/python -m pip_audit -r services/atlas-core/requirements.txt` | `/opt/atlas` | 0 | No known vulnerabilities. |
| `/opt/atlas/.venv/bin/python -m pip_audit -r services/atlas-core/requirements-dev.txt` | `/opt/atlas` | 0 | No known vulnerabilities. |
| `/opt/atlas/.venv/bin/python -m pip_audit -r services/atlas-agent/requirements.txt` | `/opt/atlas` | 0 | No known vulnerabilities. |
| `/opt/atlas/.venv/bin/python -m pip_audit -r services/atlas-agent/requirements-dev.txt` | `/opt/atlas` | 0 | No known vulnerabilities. |
| `docker compose --env-file /dev/null -f compose.production.yaml config --no-interpolate --quiet` | `/opt/atlas` | 0 | Production Compose render passed. |
| `docker compose --env-file /dev/null -f compose.production.yaml -f compose.https.yaml config --no-interpolate --quiet` | `/opt/atlas` | 0 | Production plus HTTPS Compose render passed. |
| `./scripts/data-recovery-gate` | `/opt/atlas` | 0 | Tamper rejection, backup, retention, restore, and persistence passed. |
| `./scripts/container-release-gate` | `/opt/atlas` | 0 | Images, isolated runtime, worker hardening, Codex sandbox, HTTP/HTTPS, recovery, and Rest Server gates passed. |
| `git grep -nF '# Atlas RC1 validation smoke marker.' -- .` | `/opt/atlas` | 1 | Expected: validation marker absent from tracked files. |
| `git diff --check` | `/opt/atlas` | 0 | Passed. |

The isolated container gate verified the worker runtime hardening, Codex
`atlas-workspace` write proof, and outside-workspace mutation denial. The
published RC baseline remains immutable: `atlas-v0.6-rc1.9` resolves to
`6d85df5b112b4bde28ec31fc60cce88560c9dbfc`. The local operator harness
`compose.execution-smoke.override.yaml` remained intentionally untracked and
outside release provenance.

- [x] Confirm required CI checks passed on exact validated integration commit
  `2d4a1b1929316589cdf6ea96993442b430826f10`:
  - Quality gates: SUCCESS, GitHub Actions run `31753221630`.
  - Container release gate: SUCCESS, GitHub Actions run `31753221621`.
  - Both required workflows passed on that exact SHA. Together with the local
    matrix above, the complete final technical validation is green.
- [x] Re-review dependency and accepted-advisory status for the final release.
  npm reports zero vulnerabilities, all four Python requirement audits report
  no known vulnerabilities, and no accepted security advisory remains.
- [x] Confirm the final tracked tree contains only intended release files and
  that local-only smoke artifacts remain outside release provenance.
- [x] Record final operator/release-lead sign-off name and date:
  - Sign-off name: Kenny Horner
  - Sign-off date: 2026-08-13
- [x] Confirm `atlas-v0.6.0` was unused before final tag preparation on
  2026-08-13. It must still be reconfirmed immediately before tag creation.
- [x] The immutable annotated `atlas-v0.6.0` tag was published at
  `03c1e03099b0f638dc674235312a3b3e70768c2f` after the required CI passed on
  that final documentation SHA.

### Core

- [x] `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-core`
- [x] `cd services/atlas-core && PATH=/opt/atlas/.venv/bin:$PATH python -m pytest -q`
- [x] Execution candidate, planning-intake, and route-contract tests pass.
- [x] API/OpenAPI contract regression is current.

### Atlas Agent

- [x] `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-agent`
- [x] `PATH=/opt/atlas/.venv/bin:$PATH PYTHONPATH=services/atlas-agent python -m pytest -q services/atlas-agent/tests`
- [x] End-to-end candidate workflow test passes.
- [x] Audit-chain validator tests pass.
- [x] Restart-recovery matrix tests pass.
- [x] Concurrency and idempotency tests pass.
- [x] Commit-path security tests pass.
- [x] Roadmap workflow regression tests pass.

### Mission Control

- [x] `cd services/mission-control && npm run lint`
- [x] `cd services/mission-control && npm test -- --run`
- [x] `cd services/mission-control && npm run build`
- [x] UI does not imply unsupported Phase 3 execution controls.

### Security and release operation

- [x] Approval-boundary review confirms exact immutable implementation, verification, and commit approvals.
- [x] No automatic approval, automatic execution, push, tag, release, remote deploy, or rollback path is enabled.
- [x] No secrets, logs, `jcode/`, local state, dependency folders, virtual environments, or generated builds are committed.
- [x] State migration and restart-recovery tests pass.
- [x] Docker or Compose smoke validation passes when deployment packaging is in scope.
- [x] `git diff --check` passes.
- [x] `git status --short` is clean except explicitly local-only ignored directories before tagging.
- [x] Review docs for RC tag/sequence selection before creating the next release tag.
