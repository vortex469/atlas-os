# Dependency Security

## Resolved advisories

### React Router RSC action CSRF

- Resolved: 2026-08-13
- Package: `react-router-dom@7.18.2` (`react-router@7.18.2`)
- Advisory: `GHSA-qwww-vcr4-c8h2`
- npm severity: high
- Status: fixed

The prior exception for `react-router-dom@7.18.1` is closed. The stable 7.18.2
release fixes the affected range without a major-version migration. Mission
Control remains a client-rendered Vite application and does not expose the RSC
action path, but the release no longer relies on that non-applicability finding.

The same lockfile remediation updates these transitive build/development
dependencies to fixed compatible releases:

- `brace-expansion` 5.0.8 to 5.0.9 for `GHSA-rgw5-rvv9-x895`, through
  `eslint` and `minimatch`;
- `nanoid` 3.3.16 to 3.3.18 for `GHSA-2v37-7h3g-55p8`, through `vite` and
  `postcss`;
- `postcss` 8.5.20 to 8.5.26 for `GHSA-fxqj-rqcc-2cmp`, through `vite`.

The final dependency review reports zero npm vulnerabilities and no known
vulnerabilities in the Atlas Core or Atlas Agent runtime and development Python
requirements. Re-run `npm audit --package-lock-only --audit-level=high` and the
Python requirement audits during every dependency update.
