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
- [ ] Review deployment-specific inventory, policy, and TLS settings.
- [ ] Confirm the target branch contains only intended release commits.
- [ ] Run `./scripts/container-release-gate` on the release commit.
- [ ] Confirm required GitHub checks pass.
- [ ] Create an annotated Foundry release tag and publish release notes.
