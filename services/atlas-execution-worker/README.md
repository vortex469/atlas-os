# Atlas execution worker

The execution-worker stack packages an optional isolated backend for Atlas Agent repository execution. It consists of authenticated worker requests through the relay, a private worker boundary, disposable execution workspaces, a durable no-replay ledger, and egress constrained through the dedicated allowlisted proxy.

The worker authenticates requests at its own boundary and restricts its accepted peer to the isolated relay. The relay transports traffic across segmented internal networks; it is not by itself the client-authentication authority. The worker API is exposed only on private port `8081`, is not published to the host, and the worker has no general network attachment.

The versioned ledger under `/opt/atlas/execution-worker-state` uses SQLite WAL with full synchronous durability. Request ID and digest are claimed atomically, and the committed `executing` marker is a one-way barrier. If execution is interrupted without a terminal result, reconciliation records `unknown_outcome` and never automatically relaunches the request. Stored results are bounded and validated; secrets, environment dumps, and raw prompts are excluded.

Base production uses `ATLAS_EXECUTION_BACKEND=local`. Although worker, relay, auth staging, and egress components are packaged in `compose.production.yaml`, worker execution is default-disabled with `ATLAS_EXECUTION_WORKER_EXECUTION_ENABLED=false`. Activation requires separately gated configuration and runtime validation, including the repository runtime gate; packaging or container health alone does not activate the backend.

Atlas Agent remains the planning, workflow, approval, verification, review, and commit authority. Activating the worker changes only the execution backend. It does not expand the allowed repository intent beyond `update-compose-stack`, does not add arbitrary commands, and does not absorb Provider Intent, legacy provider actions, hardened operational dispatch, backup/restore, deployment, rollback, or release-publication authority.
