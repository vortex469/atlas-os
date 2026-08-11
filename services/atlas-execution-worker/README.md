# Atlas execution worker

The worker owns its versioned execution ledger under
`/opt/atlas/execution-worker-state`. S6 uses SQLite with WAL and full
synchronous durability. A request ID and digest are claimed atomically, and a
committed `executing` marker is a one-way execution barrier. If startup finds
that marker without a terminal result, it records `unknown_outcome` and never
relaunches the command automatically.

The worker exposes its HTTP API on private TCP port `8081` on the internal
`atlas-execution-worker-net` Compose network. The port is not published to the
host, and the worker is only attached to that private network. Worker egress
is forced through the dedicated Squid proxy.

The Agent remains the workflow, approval, verification, review, and commit
authority. Worker execution is controlled by
`ATLAS_EXECUTION_WORKER_EXECUTION_ENABLED`; production currently sets it to
`false`. The ledger stores request identity fields and bounded validated
results, not secrets, environment dumps, or raw prompts. Interrupted execution
is reconciled as `unknown_outcome` and is never relaunched automatically.

The contract also defines `rc1-validation-smoke` for one explicit RC1 test
only. It directly appends the fixed marker `# Atlas RC1 execution smoke
marker` to `services/atlas-agent/tests/test_execution_engine.py` inside the
disposable clone. Its argv, working directory, target file, and content are
all fixed by the contract. It is not a general command-execution interface,
does not invoke a shell or subprocess, and is not enabled by production
Compose.
