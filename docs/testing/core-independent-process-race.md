# Independent-process evidence race: bounded test waiting

Quality run 40287727227 failed only Core shard 1 at
`test_independent_processes_share_permanent_reservation`: one child remained
alive and progressed through recursive contract validation beyond the parent's
60-second pipe wait. Other Core shards, Agent, UI and container checks passed.
An earlier attempt on run 40280294414 also recorded a child SIGSEGV (-11); its
rerun passed. Both original failures remain recorded.

A controlled reproduction used the cached Python 3.12.13 image
`72b4d5968da5dd01a2e46a3ffd321823ec1213c4d7403083db8605c3580ea7a2`,
the existing Core dependencies, a half-CPU quota, no network, read-only source
and configuration, and temporary data/log directories. This matches the
observed slow-child condition, not CI's exact Python 3.12.15 runtime:

- Original fixture: one failure in 93.21 seconds; the child did not return.
- Repaired fixture: one pass in 115.83 seconds, including the unchanged full
  reservation, evidence, result-validation and reopen assertions.
- Nine fast harness cases passed: success, EOF, malformed/failure replies,
  nonzero child exit, timeout, ignored termination, partial frame and a shared
  deadline across two children. Ruff and whitespace checks passed.

The harness now uses one 180-second deadline for child startup, complete replies
and joins. It collects both replies before expensive parent-side model
validation. Reader threads enforce the deadline even if a child writes a frame
header and then stops; `Connection.poll()` alone only covers initial readiness.
Timeout/error cleanup terminates owned children, kills termination-resistant
children after bounded grace, joins readers and checks that none survive.
EOF, crashes, malformed replies and incomplete evidence remain failures.

## Periodic diagnostic isolation

The combined local check subsequently reproduced SIGSEGV during the child’s
15-second periodic stack dump: the traceback stopped mid-frame after `File`.
Disabling only that periodic child diagnostic in a temporary bootstrap passed
all ten selected checks in 67.34 seconds. The fixture now keeps fatal-signal
reporting for the current child thread, but no periodic live-frame sampling.
The parent deadline, stage timing, exit checks and complete evidence validation
remain active. This avoids the observed diagnostic path; it does not assert a
particular interpreter-version root cause or a production interpreter fix.

Related upstream reports describe crashes while traversing live frames:
[CPython #116008](https://github.com/python/cpython/issues/116008) and
[CPython #131580](https://github.com/python/cpython/issues/131580). They are
context for this defensive test-only change, not proof that Atlas encountered
the same version-specific bug.

Three final half-CPU runs of all ten selected checks passed in 152.13, 151.60
and 152.27 seconds. Further CI outcomes are recorded in the PR. Any actual child
crash, EOF, malformed or incomplete reply still fails the test.

The original test still uses independently spawned interpreters and SQLite
connections. It still reparses the full result contracts and requires exactly
one newly recorded reservation, identical successful records, exact journal
counts and persistence after reopening. No test is skipped and no authority,
fingerprint, freshness, replay or corruption assertion is removed.

The wait budget is test infrastructure, not a product latency guarantee.
Production contracts, services, SQLite settings and default-disabled runtime
construction are unchanged. No deployment, runtime activation, main merge, tag
change or publication is authorized by this result.
