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

A refusal after Git commits can leave a local commit behind. Atlas does not
reset, amend, move references, undo another writer's edits, or automatically
replay the commit. Existing workflow failure handling blocks further progress;
the operator must inspect the repository before recovery.

These checks detect the tested staging/commit and final-observation races.
They do not provide an atomic lock against external Git writers, close every
interval between approval validation and staging, or establish a new hook
policy. Existing exact approvals and reviewed-content preflight remain required.
Bounded Git process lifetime/output and richer uncertain-outcome recovery remain
separate work. No execution, installation, deployment, or publication authority
is added.

Regression tests cover branch/parent/index-content drift immediately before
commit, preservation of later unstaged edits, HEAD movement during metadata
reads, missing candidate HEAD observations, normal additions/deletions and
renames. Fixtures use disposable local repositories and no model invocation.
