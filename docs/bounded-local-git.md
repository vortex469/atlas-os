# Bounded local Git and uncertain commit outcomes

This maintenance scope tightens the existing approved repository-edit journey.
It adds no action, approval shortcut, retry, runtime activation or release.

## Operator outcome and contract

Git subprocesses used by the repository inspector and committer cannot wait or
retain output indefinitely. Read-only commands
have a ten-second budget. A commit call shares a sixty-second budget across
inspection, staging, hooks and result checks, with at most one further second for
process cleanup. Repository validation during committer construction is separate
and uses the read-only command budget. These are fixed implementation ceilings,
not user-configurable approval extensions. Existing exact approval fields,
reviewed-byte checks, paths, message, base and branch remain required.

Metadata stdout is limited to 1 MiB and stderr to 64 KiB per command. Crossing a
limit fails the command; partial metadata is never interpreted as a complete
result. Blob hashing streams bytes into a digest without retaining blob output,
under the same time budget and stderr bound. Git failure output and command
arguments do not enter domain errors or exception chains.

Each command starts in an owned process group with noninteractive stdin. Both
output pipes are drained concurrently. Timeouts, overflow, failures and normal
return clean up owned descendants before returning. Deliberate session escape
still requires the existing outer sandbox; a process group is not an isolation
boundary. Git's existing hooks, filters and environment remain in effect; no
hook is bypassed and no new network or credential permission is granted.

If the commit command has been attempted and completion cannot be established,
the workflow remains blocked with `commit_outcome_unknown`. This does not prove
that no commit exists. Operators must inspect the repository before recovery.
Refresh, resume and restart never repeat that commit attempt. This patch adds
no automatic reconciliation or recovery execution. Failures before the commit
attempt remain ordinary refusals; metadata/content mismatches remain refused.
The API returns HTTP 409 with the stable code `commit_outcome_unknown` and plain
inspection/no-repeat guidance. Observed metadata/content conflicts use
`commit_result_mismatch` with HTTP 424. Neither response permits retry.

Audit projections mark the attempted commit `unknown` (or `invalid` for a known
result mismatch), rather than `not_reached` or `completed`. The workflow stays
blocked; valid partial evidence does not prove a successful commit. Mission
Control explains these server-owned outcomes, including the legacy restart
reason, and adds no mutation controls. The new audit status is additive; older
clients may not recognize it and must be upgraded with this presentation change.
Snapshot schema and approval subject fields remain unchanged. Existing persisted
blocked records are not rewritten; newly recovered COMMITTING sessions use the
owned uncertainty code.

## Implementation and acceptance

Use one Agent-owned Git process primitive for inspection, staging, committing,
metadata reads and streamed blob hashes. It must not import worker runtime
authority or change verification-runner semantics.
The inspector's dirty-baseline helper also uses this bounded reader. Patch
application and other execution/verification runners remain separate; this is
not a deadline for the entire repository-edit workflow.

Disposable fixtures must independently show finite time/output retention,
concurrent pipe draining, cleanup of inherited children, no child surviving a
normal parent exit, sanitized failures, and invalid budgets refused before
launch. A synthetic hook that creates a commit and then loses its response must
leave an uncertain blocked workflow without replay, including after restart.
Existing exact-approval, content drift, path safety, audit linkage, concurrency
and ordinary local-commit tests remain required. Use no real model, saved login,
production service or user repository for verification.

Local validation: all 1,221 Agent tests passed, including disposable real-Git
post-commit timeout and result-mismatch journeys across local and worker-backed
paths, response loss and persisted-approval restart. Twenty-five independent
process tests cover bounds, shared deadline, owned child cleanup and sanitized
errors. UI, browser and GitHub validation are recorded separately in the PR;
none constitutes running-service or production acceptance.

On the repair branch, all 2,425 UI component tests and the two new phone/desktop
browser cases passed. Its older UI base still reproduces ten existing browser
failures and the old lint/chunk warnings. Combined locally with Mission Control
PR #39, all 2,582 UI component tests, 69 development-browser journeys, 44 built-app
journeys and 1,222 Agent tests passed; lint/build passed without those warnings.
The native-projected browser fixture includes the combined audit contract's
repository effect kind. The maintained guarded repository checker passed 89
approval/journey/recovery/audit checks with a verified stable source digest.

The local integration required preserving both sets of imports and the existing
maintenance-audit component while adding the unknown stage normalizer. That
integration branch is a validation checkout, not a merge into main. The repair
is stacked on PR #40 and must be reviewed alongside the screen fixes in PR #39.
