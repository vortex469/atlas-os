"""Tests for explicit local Git commit orchestration."""

import subprocess
from pathlib import Path

import pytest

from app.repository.committer import GitCommitter
from app.repository.exceptions import (
    RepositoryCommitError,
    RepositoryCommitValidationError,
)
from app.repository.inspector import GitInspector
from app.repository.models import CommitRequest


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

    with pytest.raises(RepositoryCommitError, match="commit failed"):
        committer.commit(make_request(repository, head))

    assert run_git(repository, "rev-parse", "HEAD").stdout.strip() == head
