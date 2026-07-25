# Dependency Security

## Accepted advisories

### React Router RSC action CSRF

- Reviewed: 2026-07-25
- Package: `react-router-dom@7.18.1` (`react-router@7.18.1`)
- Advisory: `GHSA-qwww-vcr4-c8h2`
- npm severity: high
- Status: accepted until an upstream stable fix is available

Mission Control is a client-rendered Vite application. It uses
`createBrowserRouter` and does not enable React Server Components, framework
mode, server actions, or React Router action routes. The vulnerable RSC action
request path is therefore not exposed by the application.

The npm-recommended downgrade to 7.11.0 is not suitable: that release is
covered by a broader set of high-severity React Router advisories, including
XSS, open redirect, denial-of-service, and server-side deserialization issues.
The npm registry had no stable release outside both affected ranges when this
exception was reviewed.

Re-run `npm audit --package-lock-only --audit-level=high` during every
dependency update and remove this exception as soon as a stable fixed release
is available.
