# Core contention and browser setup checks

Quality run 40337284978 failed Core job 121622158822 in
`test_competing_keys_cannot_reserve_same_subject`: the competing request returned
`unavailable`, where the test required `permanent_subject_reserved`. The store's
existing SQLite connection has a five-second lock budget and maps operational
errors to `unavailable`; the existing lock-contention test verifies rejection
before reservation. Production store, service and error contracts are unchanged.

The race still requires exactly one successful record and exactly one loser,
with one reservation, one evidence record and no failure record. It permits the
existing fail-closed lock outcome, then reopens both stores: the losing key must
be permanently rejected, and the winner must read back as an exact duplicate
with the identical record and unchanged row counts. A controlled test holds the
owner's write lock until the competitor returns `unavailable`, then proves the
same durable rejection and that the competitor never reads prerequisites.
The original CI failure is retained. This reproduces an allowed contention path;
it does not claim access to the redacted underlying exception from CI.

Quality run 40341315768 cancelled UI job 121636459714 during system dependency
installation. Its logs show slow font-package downloads consuming the existing
ten-minute job budget before browser tests began. Use the official Playwright
1.63.0 Noble image with preinstalled browsers/system dependencies, pinned to
OCI digest `sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27`.
The installed package must match that version and its browser must exist. Keep
the existing test suites, two browser workers and ten-minute job budget. No
package-install retry or reduced test coverage is used. Node setup remains
22.12 in CI. The image's local default Node version is recorded separately.

The image is for trusted synthetic tests, with a private 1 GiB shared-memory
allocation and process reaping. Local checks disable network access. No worker
activation, deployment, production service contact, saved credentials or real
model invocation is involved. Earlier independent-process test-harness repairs
are carried forward unchanged from the passing source in PR #43.

Primary guidance: [Playwright Docker documentation at v1.63.0](https://github.com/microsoft/playwright/blob/v1.63.0/docs/src/docker.md)
and [CI documentation](https://github.com/microsoft/playwright/blob/v1.63.0/docs/src/ci.md).

Local validation passed the three focused contention checks with a half-CPU
limit in 45.81 seconds, and all 61 tests in the persistence module with one CPU
in 135.54 seconds. Both used network-disabled containers, read-only source and
disposable state. The pinned Playwright image passed 2,578 UI tests, all 67
development-browser and 42 built-app journeys, lint and build with networking
disabled. Its default Node was v24.20.0; CI still selects Node 22.12, so remote
CI remains required before an exact-head gate-ready claim.
