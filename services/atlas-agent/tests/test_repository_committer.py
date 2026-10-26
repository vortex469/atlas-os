"""Tests for explicit local Git commit orchestration."""

import subprocess
import traceback
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from app.repository.committer import GitCommitter
from app.repository.exceptions import (
    RepositoryCommitError,
    RepositoryCommitOutcomeUnknownError,
    RepositoryCommitValidationError,
)
from app.repository.inspector import GitInspector
from app.repository.models import CommitRequest
from app.repository.process import GitProcessResult


def run_git(
    repository: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def initialize_repository(repository: Path) -> tuple[Path, str]:
    repository.mkdir()
    run_git(repository, "init", "-b", "feature/atlas-agent")
    run_git(repository, "config", "user.name", "Atlas Tests")
    run_git(
        repository,
        "config",
        "user.email",
        "atlas-tests@example.invalid",
    )
    (repository / "tracked.txt").write_text("initial\n", encoding="utf-8")
    (repository / "delete.txt").write_text("delete\n", encoding="utf-8")
    run_git(repository, "add", "tracked.txt", "delete.txt")
    run_git(repository, "commit", "-m", "Initial commit")
    return repository, run_git(repository, "rev-parse", "HEAD").stdout.strip()


def make_request(
    repository: Path,
    head: str,
    *,
    paths: tuple[Path, ...] = (Path("tracked.txt"),),
    message: str = "feat(agent): commit orchestration",
) -> CommitRequest:
    return CommitRequest(
        repository_root=repository,
        expected_branch="feature/atlas-agent",
        expected_head=head,
        paths=paths,
        message=message,
    )


def test_commits_exact_paths_and_returns_metadata(tmp_path: Path) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    (repository / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (repository / "new.txt").write_text("new\n", encoding="utf-8")

    result = GitCommitter(repository).commit(
        make_request(
            repository,
            head,
            paths=(Path("new.txt"), Path("tracked.txt")),
        )
    )

    assert result.repository_root == repository.resolve()
    assert result.branch == "feature/atlas-agent"
    assert result.parent_head == head
    assert result.commit_sha == run_git(repository, "rev-parse", "HEAD").stdout.strip()
    assert result.message == "feat(agent): commit orchestration"
    assert result.committed_files == (Path("new.txt"), Path("tracked.txt"))
    assert (
        run_git(repository, "show", "-s", "--format=%s", "HEAD").stdout.strip()
        == result.message
    )


def test_commits_deletion_and_leaves_logs_untracked(tmp_path: Path) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    (repository / "delete.txt").unlink()
    logs = repository / "logs"
    logs.mkdir()
    (logs / "agent.log").write_text("runtime\n", encoding="utf-8")

    result = GitCommitter(repository).commit(
        make_request(
            repository,
            head,
            paths=(Path("delete.txt"),),
        )
    )

    assert result.committed_files == (Path("delete.txt"),)
    snapshot = GitInspector(repository).inspect()
    assert snapshot.untracked_files == ("logs/",)


def test_commits_rename_using_inspector_destination_path(tmp_path: Path) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    run_git(repository, "mv", "tracked.txt", "renamed.txt")
    snapshot = GitInspector(repository).inspect()

    result = GitCommitter(repository).commit(
        make_request(
            repository,
            head,
            paths=(Path(snapshot.staged_files[0]),),
        )
    )

    assert result.committed_files == (Path("renamed.txt"),)
    assert run_git(repository, "ls-tree", "--name-only", result.commit_sha).stdout.splitlines() == [
        "delete.txt", "renamed.txt",
    ]


def test_rejects_logs_path_without_staging_it(tmp_path: Path) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    logs = repository / "logs"
    logs.mkdir()
    (logs / "agent.log").write_text("runtime\n", encoding="utf-8")

    with pytest.raises(
        RepositoryCommitValidationError,
        match="must not include logs",
    ):
        GitCommitter(repository).commit(
            make_request(
                repository,
                head,
                paths=(Path("logs/agent.log"),),
            )
        )

    assert GitInspector(repository).inspect().staged_files == ()


@pytest.mark.parametrize(
    "denied_path",
    (
        Path(".git/config"),
        Path("jcode"),
        Path("jcode/file.py"),
        Path("logs"),
        Path("logs/run.log"),
        Path("agent-state/snapshot.json"),
    ),
)
def test_rejects_denied_commit_paths_without_staging(
    tmp_path: Path,
    denied_path: Path,
) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    target = repository / denied_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if denied_path.suffix:
        target.write_text("runtime\n", encoding="utf-8")

    with pytest.raises(RepositoryCommitValidationError):
        GitCommitter(repository).commit(
            make_request(repository, head, paths=(denied_path,))
        )

    assert GitInspector(repository).inspect().staged_files == ()


def test_rejects_symlink_escape_path(tmp_path: Path) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret\n", encoding="utf-8")
    (repository / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RepositoryCommitValidationError, match="escape"):
        GitCommitter(repository).commit(
            make_request(repository, head, paths=(Path("escape/secret.txt"),))
        )

    assert GitInspector(repository).inspect().staged_files == ()


@pytest.mark.parametrize(
    "paths",
    (
        (),
        (Path("."),),
        (Path("../outside.txt"),),
        (Path("/absolute.txt"),),
        (Path("tracked.txt"), Path("tracked.txt")),
    ),
)
def test_rejects_invalid_path_allowlists(
    tmp_path: Path,
    paths: tuple[Path, ...],
) -> None:
    repository, head = initialize_repository(tmp_path / "repository")

    with pytest.raises(RepositoryCommitValidationError):
        GitCommitter(repository).commit(
            make_request(repository, head, paths=paths)
        )


def test_rejects_changed_head_before_staging(tmp_path: Path) -> None:
    repository, _ = initialize_repository(tmp_path / "repository")
    (repository / "tracked.txt").write_text("changed\n", encoding="utf-8")

    with pytest.raises(
        RepositoryCommitValidationError,
        match="HEAD differs",
    ):
        GitCommitter(repository).commit(
            make_request(repository, "different-head")
        )

    assert GitInspector(repository).inspect().staged_files == ()


def test_rejects_staged_contamination(tmp_path: Path) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    (repository / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (repository / "unrelated.txt").write_text("unrelated\n", encoding="utf-8")
    run_git(repository, "add", "unrelated.txt")

    with pytest.raises(
        RepositoryCommitValidationError,
        match="Staged files do not match",
    ):
        GitCommitter(repository).commit(make_request(repository, head))

    assert run_git(repository, "rev-parse", "HEAD").stdout.strip() == head


def test_commit_command_failure_is_a_domain_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    (repository / "tracked.txt").write_text("changed\n", encoding="utf-8")
    committer = GitCommitter(repository)
    original_run = committer._run_git

    def fail_commit(*arguments: str) -> subprocess.CompletedProcess[str]:
        if arguments and arguments[0] == "commit":
            raise RepositoryCommitError("commit failed")
        return original_run(*arguments)

    monkeypatch.setattr(committer, "_run_git", fail_commit)

    with pytest.raises(RepositoryCommitOutcomeUnknownError, match="outcome is unknown"):
        committer.commit(make_request(repository, head))

    assert run_git(repository, "rev-parse", "HEAD").stdout.strip() == head


@pytest.mark.parametrize("drift", ("branch", "parent", "content"))
def test_rejects_commit_time_identity_or_content_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    run_git(repository, "branch", "other")
    alternate_parent = run_git(
        repository, "commit-tree", f"{head}^{{tree}}", "-p", head,
        "-m", "Concurrent parent",
    ).stdout.strip()
    (repository / "tracked.txt").write_text("reviewed\n", encoding="utf-8")
    committer = GitCommitter(repository)
    original_run = committer._run_git

    def change_before_commit(*arguments: str) -> subprocess.CompletedProcess[str]:
        if arguments[0] == "commit":
            if drift == "branch":
                run_git(repository, "symbolic-ref", "HEAD", "refs/heads/other")
            elif drift == "parent":
                run_git(repository, "update-ref", "HEAD", alternate_parent, head)
            else:
                (repository / "tracked.txt").write_text(
                    "unreviewed\n", encoding="utf-8"
                )
                run_git(repository, "add", "tracked.txt")
        return original_run(*arguments)

    monkeypatch.setattr(committer, "_run_git", change_before_commit)

    with pytest.raises(RepositoryCommitError, match="does not match"):
        committer.commit(make_request(repository, head))

    # A commit can already exist: refusal must not reset, amend, or replay it.
    created = run_git(repository, "rev-parse", "HEAD").stdout.strip()
    assert created != head
    if drift == "parent":
        assert run_git(repository, "rev-parse", f"{created}^").stdout.strip() == alternate_parent
    if drift == "content":
        assert run_git(repository, "show", f"{created}:tracked.txt").stdout == "unreviewed\n"


def test_commits_staged_content_without_restaging_later_worktree_edits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    (repository / "tracked.txt").write_text("reviewed\n", encoding="utf-8")
    request = make_request(repository, head)
    evidence = GitInspector(repository).reviewed_change_evidence(
        reviewed_files=request.paths, expected_branch=request.expected_branch,
        expected_head=head, commit_message=request.message,
    )
    committer = GitCommitter(repository)
    original_run = committer._run_git

    def edit_before_commit(*arguments: str) -> subprocess.CompletedProcess[str]:
        if arguments[0] == "commit":
            (repository / "tracked.txt").write_text("later edit\n", encoding="utf-8")
        return original_run(*arguments)

    monkeypatch.setattr(committer, "_run_git", edit_before_commit)
    result = committer.commit(request, reviewed_evidence=evidence)

    assert run_git(repository, "show", f"{result.commit_sha}:tracked.txt").stdout == "reviewed\n"
    assert (repository / "tracked.txt").read_text(encoding="utf-8") == "later edit\n"
    assert GitInspector(repository).inspect().modified_files == ("tracked.txt",)


def test_refuses_head_movement_during_metadata_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    (repository / "tracked.txt").write_text("reviewed\n", encoding="utf-8")
    committer = GitCommitter(repository)
    original_run = committer._run_git
    observed_commits: list[str] = []

    def move_after_observation(*arguments: str) -> subprocess.CompletedProcess[str]:
        result = original_run(*arguments)
        if arguments == ("rev-parse", "HEAD"):
            created = result.stdout.strip()
            observed_commits.append(created)
            run_git(repository, "update-ref", "HEAD", head, created)
        elif arguments[0] in {"show", "log", "diff-tree"}:
            assert arguments[-1] == observed_commits[0]
        return result

    monkeypatch.setattr(committer, "_run_git", move_after_observation)

    with pytest.raises(RepositoryCommitError, match="does not match"):
        committer.commit(make_request(repository, head))

    assert run_git(repository, "rev-parse", "HEAD").stdout.strip() == head
    assert run_git(repository, "show", f"{observed_commits[0]}:tracked.txt").stdout == "reviewed\n"


def test_commits_first_file_without_inventing_a_parent(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    run_git(repository, "init", "-b", "feature/atlas-agent")
    run_git(repository, "config", "user.name", "Atlas Tests")
    run_git(repository, "config", "user.email", "atlas-tests@example.invalid")
    (repository / "first.txt").write_text("first\n", encoding="utf-8")
    result = GitCommitter(repository).commit(CommitRequest(
        repository_root=repository,
        expected_branch="feature/atlas-agent", expected_head=None,
        paths=(Path("first.txt"),), message="Initial reviewed commit",
    ))

    assert result.parent_head is None
    assert run_git(repository, "show", "-s", "--format=%P", result.commit_sha).stdout.strip() == ""


def test_refuses_identity_drift_while_staging_without_creating_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    run_git(repository, "branch", "other")
    (repository / "tracked.txt").write_text("reviewed\n", encoding="utf-8")
    committer = GitCommitter(repository)
    original_run = committer._run_git

    def change_after_staging(*arguments: str) -> subprocess.CompletedProcess[str]:
        result = original_run(*arguments)
        if arguments[0] == "add":
            run_git(repository, "symbolic-ref", "HEAD", "refs/heads/other")
        assert arguments[0] != "commit"
        return result

    monkeypatch.setattr(committer, "_run_git", change_after_staging)
    with pytest.raises(RepositoryCommitValidationError, match="identity changed"):
        committer.commit(make_request(repository, head))
    assert run_git(repository, "rev-parse", "HEAD").stdout.strip() == head


@pytest.mark.parametrize("kind", ("edit", "new", "delete", "rename", "binary"))
def test_commits_content_bound_to_review_evidence(tmp_path: Path, kind: str) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    path = Path("tracked.txt")
    if kind == "new":
        path = Path("new.txt")
    elif kind == "rename":
        path = Path("renamed.txt")
        run_git(repository, "mv", "tracked.txt", str(path))
    if kind == "delete":
        (repository / path).unlink()
    elif kind != "rename":
        (repository / path).write_bytes(b"\xff\x00\r\nreviewed\r\n" if kind == "binary" else b"reviewed\n")
    request = make_request(repository, head, paths=(path,))
    evidence = GitInspector(repository).reviewed_change_evidence(
        reviewed_files=request.paths, expected_branch=request.expected_branch,
        expected_head=head, commit_message=request.message,
    )

    result = GitCommitter(repository).commit(request, reviewed_evidence=evidence)

    assert result.parent_head == head
    assert result.committed_files == (path,)


@pytest.mark.parametrize("drift", ("before-add", "after-add", "deleted-appears", "file-disappears"))
def test_refuses_staged_bytes_that_differ_from_approved_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    path = repository / "tracked.txt"
    if drift == "deleted-appears":
        path.unlink()
    else:
        path.write_text("reviewed\n", encoding="utf-8")
    request = make_request(repository, head)
    evidence = GitInspector(repository).reviewed_change_evidence(
        reviewed_files=request.paths, expected_branch=request.expected_branch,
        expected_head=head, commit_message=request.message,
    )
    committer = GitCommitter(repository)
    original_run = committer._run_git

    def inject(*arguments: str) -> subprocess.CompletedProcess[str]:
        if arguments[0] == "add" and drift != "after-add":
            if drift == "file-disappears":
                path.unlink()
            else:
                path.write_text("unreviewed\n", encoding="utf-8")
        result = original_run(*arguments)
        if arguments[0] == "add" and drift == "after-add":
            path.write_text("unreviewed\n", encoding="utf-8")
            run_git(repository, "add", "tracked.txt")
        assert arguments[0] != "commit"
        return result

    monkeypatch.setattr(committer, "_run_git", inject)
    with pytest.raises(RepositoryCommitValidationError, match="Staged content differs"):
        committer.commit(request, reviewed_evidence=evidence)
    assert run_git(repository, "rev-parse", "HEAD").stdout.strip() == head


@pytest.mark.parametrize("mismatch", ("branch", "head", "message", "paths", "changes", "root"))
def test_refuses_review_evidence_for_another_request_before_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    (repository / "tracked.txt").write_text("reviewed\n", encoding="utf-8")
    request = make_request(repository, head)
    evidence = GitInspector(repository).reviewed_change_evidence(
        reviewed_files=request.paths, expected_branch=request.expected_branch,
        expected_head=head, commit_message=request.message,
    )
    fields = {
        "branch": {"expected_branch": "other"},
        "head": {"expected_head": "other"},
        "message": {"commit_message": "Other message"},
        "paths": {"reviewed_files": (Path("other.txt"),)},
        "changes": {"changes": ()},
        "root": {"repository_root": tmp_path},
    }
    committer = GitCommitter(repository)
    calls = []
    monkeypatch.setattr(committer, "_run_git", lambda *args: calls.append(args))
    with pytest.raises(RepositoryCommitValidationError, match="Reviewed evidence does not match"):
        committer.commit(request, reviewed_evidence=replace(evidence, **fields[mismatch]))
    assert calls == []
    assert GitInspector(repository).inspect().staged_files == ()


def test_refuses_git_newline_conversion_of_reviewed_raw_bytes(tmp_path: Path) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    run_git(repository, "config", "core.autocrlf", "true")
    (repository / "tracked.txt").write_bytes(b"reviewed\r\n")
    request = make_request(repository, head)
    evidence = GitInspector(repository).reviewed_change_evidence(
        reviewed_files=request.paths, expected_branch=request.expected_branch,
        expected_head=head, commit_message=request.message,
    )

    with pytest.raises(RepositoryCommitValidationError, match="Staged content differs"):
        GitCommitter(repository).commit(request, reviewed_evidence=evidence)

    assert run_git(repository, "rev-parse", "HEAD").stdout.strip() == head


def test_staged_blob_read_failure_refuses_commit_without_disclosing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    (repository / "tracked.txt").write_text("reviewed\n", encoding="utf-8")
    request = make_request(repository, head)
    evidence = GitInspector(repository).reviewed_change_evidence(
        reviewed_files=request.paths, expected_branch=request.expected_branch,
        expected_head=head, commit_message=request.message,
    )
    committer = GitCommitter(repository)
    original_run = committer._process_runner.run
    canary = b"synthetic-sensitive-blob-output"

    def fail_blob(arguments, **kwargs):
        if arguments[:2] == ("cat-file", "blob"):
            return GitProcessResult(1, stdout=canary, stderr=canary)
        return original_run(arguments, **kwargs)

    monkeypatch.setattr(committer._process_runner, "run", fail_blob)
    with pytest.raises(RepositoryCommitError, match="Unable to read staged Git blob") as error:
        committer.commit(request, reviewed_evidence=evidence)

    assert canary.decode() not in str(error.value)
    assert run_git(repository, "rev-parse", "HEAD").stdout.strip() == head


def test_failing_hook_remains_enabled_and_does_not_disclose_output_or_message(
    tmp_path: Path,
) -> None:
    repository, head = initialize_repository(tmp_path / "repository")
    (repository / "tracked.txt").write_text("reviewed\n", encoding="utf-8")
    canary = uuid4().hex
    hook = repository / ".git" / "hooks" / "pre-commit"
    hook.write_text(
        f"#!/bin/sh\nprintf '%s' '{canary}'\nprintf '%s' '{canary}' >&2\n"
        "printf 'ran' > .git/fixture-pre-commit-ran\nexit 1\n",
        encoding="utf-8",
    )
    hook.chmod(0o700)
    request = make_request(repository, head, message=f"Fixture {canary}")

    with pytest.raises(RepositoryCommitOutcomeUnknownError) as error:
        GitCommitter(repository).commit(request)

    assert canary not in "".join(traceback.format_exception(error.value))
    assert (repository / ".git" / "fixture-pre-commit-ran").read_text() == "ran"
    assert run_git(repository, "rev-parse", "HEAD").stdout.strip() == head
