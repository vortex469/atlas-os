# Atlas execution worker

The worker owns its versioned execution ledger under
`/opt/atlas/execution-worker-state`. S6 uses SQLite with WAL and full
synchronous durability. A request ID and digest are claimed atomically, and a
committed `executing` marker is a one-way execution barrier. If startup finds
that marker without a terminal result, it records `unknown_outcome` and never
relaunches the command automatically.

The worker socket and ledger are separate from Atlas Agent state. The Agent
remains the workflow, approval, verification, review, and commit authority.
The S6 HTTP API remains execution-disabled, so submissions produce the
existing deterministic `worker_unavailable` result. S6 adds durable identity
and recovery semantics only. The ledger stores request identity fields and
bounded validated results, not secrets, environment dumps, or raw prompts.
