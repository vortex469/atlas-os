# Saved file facts in commit review

The commit request already identifies exact paths and a reviewed-content
fingerprint. Operators also need to inspect the file facts behind that
fingerprint. New successful repository reviews retain their immutable version-2
manifest with the workflow: paths, Git status, raw-content digest, regular-file
Git mode, deletion and rename source. File content is never stored by this
feature.

The canonical version-2 fingerprint is unchanged. A frozen digest test protects
that compatibility. Both ordinary and candidate review paths validate the
manifest against the exact commit request before saving an approval boundary.
The manifest, request and approval remain bound to the same fingerprint;
retaining facts grants no approval or execution authority.

Snapshot schema 3 gains an optional `reviewed_change_evidence` member. New
snapshots validate its shape, supported manifest version, relative paths,
request linkage and digest on write and load. Unknown manifest or file fields,
malformed types and altered facts are refused. Existing snapshots without the
member remain readable and keep their original fingerprints. Facts are never
reconstructed from the current checkout. Older binaries can discard this
optional member when rewriting a snapshot; downgrade therefore loses the new
presentation details, not the underlying exact approval requirements. Pending
version-1 approvals still require a fresh review as described in
[Git mode binding](reviewed-git-modes.md).

The existing read-only workflow detail response adds nullable
`commit_request.reviewed_changes`, using a dedicated public DTO. Each entry
contains `path`, an owned change label, `executable`, `content_sha256` and
`rename_source`. The internal Git mode is translated to a boolean; deletions
have no executable flag or content digest. A missing or mismatched saved
manifest produces unavailable facts. Projection checks the actual stored
approval's repository, branch, head, paths, message and fingerprint as well as
the workflow request. Reading facts does not inspect Git, read file content,
refresh approval, resume a workflow or submit any decision.

Mission Control preserves the approved layout and adds a closed-by-default
“Files in this review” disclosure. It explains that facts were saved at review
time and the checkout may have changed. Per-file fingerprints remain in their
own disclosure. Older requests explain that details are unavailable. This is
file metadata, not a line-by-line diff or proof that the current checkout still
matches. Existing approval and resume controls retain their exact contracts.

Acceptance covers saved facts after restart, snapshot tampering and malformed
records, legacy records with no regeneration, unchanged approval fingerprints,
API refusal of unbound details, complete candidate journeys and read-only
phone/desktop browser checks. The browser fixture is synthetic and checked
against the native Agent projection. No installation capability, model run,
saved-login use, deployment, runtime enablement or release change is selected.
