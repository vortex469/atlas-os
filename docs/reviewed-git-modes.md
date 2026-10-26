# Git mode binding in commit review

The existing review fingerprint binds paths, status, raw content, deletion and
rename source, but not the Git executable flag. A disposable fixture proved that
changing a reviewed regular file from mode 100644 to 100755 left the fingerprint
unchanged and the committer accepted that unreviewed mode.

The maintenance contract is review-manifest version 2: regular-file evidence
includes its expected Git mode, either 100644 or 100755. Deletions have no mode.
The committer must match both staged blob bytes and that exact mode before
attempting a commit. Post-commit tree validation and the existing no-replay rule
remain required. No symlink, submodule or new execution capability is selected.

Evidence follows Git semantics: when `core.filemode` is true, the owner execute
bit determines the regular-file Git mode. When false, an existing index entry's
mode is retained and a new file uses 100644. Thus an ignored filesystem permission
change is not mistaken for a Git tree change. Unsupported/non-regular entries
remain refused. Review reads must not follow a file replaced by a symlink and
must obtain content and mode from the same opened regular file.

Approval fields and persisted snapshot schemas do not change. Newly computed
fingerprints include the version and mode. Pending version-1 commit approvals
cannot authorize version-2 evidence: existing validation blocks them before a
commit, requiring a new workflow/review and exact approval. It must not rewrite
or automatically upgrade the old approval. Completed historical records remain
readable without recomputing their old fingerprints.

Acceptance includes executable-flag drift before preflight/staging and after
staging, ignored-filemode behavior, new/executable/deleted/renamed files, binary
bytes, unsupported entry types, legacy pending-approval refusal and completed
record compatibility. Candidate local/worker, restart, audit, concurrency and
no-replay regressions remain required. Use only disposable fixtures, synthetic
approvals and local Git; no real model, saved login or runtime change.

Local validation passed all 1,253 Agent tests and 105 maintained guarded
approval/journey/recovery/audit checks; the checker report verified the stable
tested source digest. Focused repository checks passed 89 tests, and 33 candidate
journeys covered local/worker paths, response loss, mode drift, persisted legacy
approval refusal, completed-record reads, restart and no replay. Ruff and the
whitespace check passed. These are source/fixture results, not runtime or
production acceptance. No UI controls or public approval fields changed.
The generated OpenAPI schema remained identical across all 29 paths, and the
internal `git_mode` evidence field was not exposed in it.
