# Local commit result validation

Atlas checks the actual local commit before reporting success. The committer
rechecks branch and HEAD after staging the exact allowed paths, records the
staged tree, and commits that index without restaging later working-tree edits.
This also preserves staged renames, including deletion of the source path.

After Git returns, metadata reads use one observed commit SHA. Its complete
parent list must match the approved base (or be empty for a root commit), its
tree must match the recorded staged tree, and its message and changed paths must
match the request. The final checkout must still have the expected branch and
that exact HEAD. Candidate result validation also refuses a missing observed
HEAD. Result branch and parent fields come from observations rather than being
copied from the request.

Both workflow commit paths carry the current reviewed evidence, already checked
against the persisted exact approval fingerprint, into the committer. Before
committing, it verifies that the evidence belongs to the same request and compares
each staged blob's raw-byte digest or deletion with that evidence. A content
change between approval preflight and staging is refused before creating a
commit. Missing or mismatched candidate evidence also blocks the workflow.
Evidence is rebuilt and validated on resume; approval fields and snapshot schemas
do not change. The low-level committer still supports callers without workflow
evidence, but that alone does not establish exact-content approval.

A refusal after Git commits can leave a local commit behind. Atlas does not
reset, amend, move references, undo another writer's edits, or automatically
replay the commit. Existing workflow failure handling blocks further progress;
the operator must inspect the repository before recovery.

These checks detect the tested staging/commit and final-observation races.
They do not provide an atomic lock against external Git writers or establish a
new hook policy. Existing exact approvals and reviewed-content preflight remain
required. The approved content digest describes raw regular-file bytes; a Git
clean filter or newline conversion that changes those bytes is refused rather
than silently treating the transformed blob as approved. This does not add
approval coverage for file modes, symlinks or submodules.
The follow-up [bounded Git contract](bounded-local-git.md) covers process
lifetime/output and explicit uncertain-result reporting. Automatic reconciliation
or recovery execution remains out of scope. No execution, installation,
deployment, or publication authority is added.

Regression tests cover branch/parent/index-content drift immediately before
commit, preservation of later unstaged edits, HEAD movement during metadata
reads, missing candidate HEAD observations, normal additions/deletions and
renames, raw binary/CRLF bytes, request/evidence mismatch and content drift at
staging. Candidate journeys cover local and worker-backed paths, response loss,
restart, and refusal without replay. Fixtures use disposable local repositories
and no model invocation.
