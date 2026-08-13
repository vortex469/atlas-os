"""Tests for Git repository inspection."""

import subprocess
from pathlib import Path

import pytest
from app.config.settings import Settings
from app.execution.patches import WorkerPatchApplier
from app.main import create_app
from app.repository.exceptions import (
    InvalidRepositoryError,
    RepositoryInspectionError,
)
from app.repository.inspector import GitInspector


def run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run a Git command in a temporary test repository."""

    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def initialize_repository(
    repository: Path,
    *,
    with_commit: bool = False,
) -> Path:
    """Initialize a deterministic temporary Git repository."""

    repository.mkdir()
    run_git(repository, "init")
    run_git(repository, "config", "user.name", "Atlas Tests")
    run_git(repository, "config", "user.email", "atlas-tests@example.invalid")

    if with_commit:
        tracked_file = repository / "tracked.txt"
        tracked_file.write_text("initial\n", encoding="utf-8")
        run_git(repository, "add", "tracked.txt")
        run_git(repository, "commit", "-m", "Initial commit")

    return repository


def test_rejects_nonexistent_path(tmp_path: Path) -> None:
    """A nonexistent repository path is rejected."""

    with pytest.raises(InvalidRepositoryError):
        GitInspector(tmp_path / "missing")


def test_rejects_existing_file(tmp_path: Path) -> None:
    """A regular file cannot be inspected as a repository."""

    file_path = tmp_path / "file.txt"
    file_path.write_text("content\n", encoding="utf-8")

    with pytest.raises(InvalidRepositoryError):
        GitInspector(file_path)


def test_rejects_non_git_directory(tmp_path: Path) -> None:
    """A directory outside a Git work tree is rejected."""

    directory = tmp_path / "directory"
    directory.mkdir()

    with pytest.raises(InvalidRepositoryError):
        GitInspector(directory)


def test_reports_clean_repository(tmp_path: Path) -> None:
    """A committed repository is reported as clean."""

    repository = initialize_repository(
        tmp_path / "repository",
        with_commit=True,
    )

    snapshot = GitInspector(repository).inspect()

    assert snapshot.root == repository.resolve()
    assert snapshot.branch is not None
    assert snapshot.head_commit is not None
    assert snapshot.is_clean is True
    assert snapshot.modified_files == ()
    assert snapshot.staged_files == ()
    assert snapshot.untracked_files == ()


def test_reports_actual_root_from_subdirectory(tmp_path: Path) -> None:
    """Inspection from a subdirectory reports the Git top-level path."""

    repository = initialize_repository(
        tmp_path / "repository",
        with_commit=True,
    )
    subdirectory = repository / "nested"
    subdirectory.mkdir()

    snapshot = GitInspector(subdirectory).inspect()

    assert snapshot.root == repository.resolve()


def test_reports_staged_only_file(tmp_path: Path) -> None:
    """An added file appears only in staged files."""

    repository = initialize_repository(tmp_path / "repository")
    (repository / "staged.txt").write_text("staged\n", encoding="utf-8")
    run_git(repository, "add", "staged.txt")

    snapshot = GitInspector(repository).inspect()

    assert snapshot.staged_files == ("staged.txt",)
    assert snapshot.modified_files == ()
    assert snapshot.untracked_files == ()
    assert snapshot.is_clean is False


def test_reports_worktree_only_modification(tmp_path: Path) -> None:
    """An unstaged modification appears only in modified files."""

    repository = initialize_repository(
        tmp_path / "repository",
        with_commit=True,
    )
    (repository / "tracked.txt").write_text("modified\n", encoding="utf-8")

    snapshot = GitInspector(repository).inspect()

    assert snapshot.modified_files == ("tracked.txt",)
    assert snapshot.staged_files == ()
    assert snapshot.untracked_files == ()


def test_reports_mm_file_in_both_collections(tmp_path: Path) -> None:
    """A file modified in index and work tree appears in both collections."""

    repository = initialize_repository(
        tmp_path / "repository",
        with_commit=True,
    )
    tracked_file = repository / "tracked.txt"
    tracked_file.write_text("staged version\n", encoding="utf-8")
    run_git(repository, "add", "tracked.txt")
    tracked_file.write_text("worktree version\n", encoding="utf-8")

    snapshot = GitInspector(repository).inspect()

    assert snapshot.staged_files == ("tracked.txt",)
    assert snapshot.modified_files == ("tracked.txt",)


def test_reports_untracked_file(tmp_path: Path) -> None:
    """An untracked file appears in the untracked collection."""

    repository = initialize_repository(tmp_path / "repository")
    (repository / "untracked.txt").write_text("new\n", encoding="utf-8")

    snapshot = GitInspector(repository).inspect()

    assert snapshot.untracked_files == ("untracked.txt",)
    assert snapshot.staged_files == ()
    assert snapshot.modified_files == ()


def test_rename_reports_destination_path(tmp_path: Path) -> None:
    """A staged rename reports its destination path."""

    repository = initialize_repository(
        tmp_path / "repository",
        with_commit=True,
    )
    run_git(repository, "mv", "tracked.txt", "renamed.txt")

    snapshot = GitInspector(repository).inspect()

    assert snapshot.staged_files == ("renamed.txt",)
    assert "tracked.txt" not in snapshot.staged_files


def test_preserves_filename_with_spaces(tmp_path: Path) -> None:
    """Status parsing preserves spaces in filenames."""

    repository = initialize_repository(tmp_path / "repository")
    filename = "file with spaces.txt"
    (repository / filename).write_text("content\n", encoding="utf-8")

    snapshot = GitInspector(repository).inspect()

    assert snapshot.untracked_files == (filename,)


def test_detached_head_returns_no_branch(tmp_path: Path) -> None:
    """Detached HEAD is represented by a None branch."""

    repository = initialize_repository(
        tmp_path / "repository",
        with_commit=True,
    )
    run_git(repository, "checkout", "--detach")

    snapshot = GitInspector(repository).inspect()

    assert snapshot.branch is None
    assert snapshot.head_commit is not None


def test_repository_without_commits_returns_no_head(tmp_path: Path) -> None:
    """An initialized repository without commits has no HEAD commit."""

    repository = initialize_repository(tmp_path / "repository")

    snapshot = GitInspector(repository).inspect()

    assert snapshot.head_commit is None


def test_unexpected_git_execution_failure_raises_domain_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected execution failures are exposed as domain errors."""

    repository = initialize_repository(
        tmp_path / "repository",
        with_commit=True,
    )
    inspector = GitInspector(repository)

    def fail_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git unavailable")

    monkeypatch.setattr(subprocess, "run", fail_run)

    with pytest.raises(RepositoryInspectionError, match="Unable to execute Git"):
        inspector.inspect()


def test_settings_default_to_atlas_repository_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default settings resolve deterministically to the Atlas root."""

    monkeypatch.delenv("ATLAS_AGENT_REPOSITORY_ROOT", raising=False)

    settings = Settings.from_environment()

    assert settings.repository_root == Path(__file__).resolve().parents[3]


def test_settings_repository_override_is_resolved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The environment repository override becomes a resolved Path."""

    repository = tmp_path / "repository"
    repository.mkdir()
    monkeypatch.setenv(
        "ATLAS_AGENT_REPOSITORY_ROOT",
        str(repository / ".." / "repository"),
    )

    settings = Settings.from_environment()

    assert settings.repository_root == repository.resolve()


def test_create_app_wires_repository_inspector(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Application composition wires the configured repository inspector."""

    repository = initialize_repository(
        tmp_path / "repository",
        with_commit=True,
    )
    settings = Settings(
        repository_root=repository.resolve(),
        atlas_core_timeout_seconds=42.0,
        ollama_base_url="http://ollama.example:11434",
        ollama_default_model="test-model:latest",
    )
    captured: dict[str, object] = {}
    provider = object()
    model_service = object()
    planning_advisor = object()

    def create_ollama_provider(
        *,
        base_url: str,
        timeout_seconds: float,
    ) -> object:
        captured["base_url"] = base_url
        captured["timeout_seconds"] = timeout_seconds
        return provider

    def create_model_service(
        *,
        provider: object,
        default_model: str,
    ) -> object:
        captured["provider"] = provider
        captured["default_model"] = default_model
        return model_service

    def create_planning_advisor(
        *,
        model_service: object,
    ) -> object:
        captured["advisor_model_service"] = model_service
        return planning_advisor

    monkeypatch.setattr(
        "app.main.load_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.main.OllamaProvider",
        create_ollama_provider,
    )
    monkeypatch.setattr(
        "app.main.ModelService",
        create_model_service,
    )
    monkeypatch.setattr(
        "app.main.PlanningAdvisor",
        create_planning_advisor,
    )

    application = create_app()
    container = application.state.container

    assert container.settings is settings
    assert isinstance(container.repository_inspector, GitInspector)
    assert container.repository_inspector.repository_root == repository.resolve()
    assert container.workflow_state.get_sprint() is None
    assert container.workflow_state.get_verification() is None
    assert container.workflow_state.get_review() is None
    assert container.model_service is model_service
    assert container.planning_advisor is planning_advisor
    assert captured == {
        "base_url": "http://ollama.example:11434",
        "timeout_seconds": 42.0,
        "provider": provider,
        "default_model": "test-model:latest",
        "advisor_model_service": model_service,
    }


def test_reviewed_change_evidence_hashes_modified_deleted_renamed_and_untracked(
    tmp_path: Path,
) -> None:
    repository = initialize_repository(tmp_path / "repository", with_commit=True)
    (repository / "delete.txt").write_text("delete\n", encoding="utf-8")
    run_git(repository, "add", "delete.txt")
    run_git(repository, "commit", "-m", "Add delete target")
    head = run_git(repository, "rev-parse", "HEAD").stdout.strip()
    (repository / "new.txt").write_text("new\n", encoding="utf-8")
    run_git(repository, "mv", "delete.txt", "renamed.txt")
    (repository / "renamed.txt").write_text("renamed\n", encoding="utf-8")
    run_git(repository, "rm", "tracked.txt")

    evidence = GitInspector(repository).reviewed_change_evidence(
        reviewed_files=(Path("new.txt"), Path("renamed.txt"), Path("tracked.txt")),
        expected_branch="master",
        expected_head=head,
        commit_message="feat(agent): reviewed evidence",
    )

    assert len(evidence.fingerprint) == 64
    assert evidence.reviewed_files == (
        Path("new.txt"),
        Path("renamed.txt"),
        Path("tracked.txt"),
    )
    by_path = {change.path: change for change in evidence.changes}
    assert by_path[Path("new.txt")].content_sha256 is not None
    assert by_path[Path("tracked.txt")].deletion_marker == "deleted"
    assert by_path[Path("renamed.txt")].rename_source == Path("delete.txt")


def test_reviewed_change_evidence_rejects_unexpected_changed_paths(
    tmp_path: Path,
) -> None:
    repository = initialize_repository(tmp_path / "repository", with_commit=True)
    head = run_git(repository, "rev-parse", "HEAD").stdout.strip()
    (repository / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (repository / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")

    with pytest.raises(RepositoryInspectionError, match="changed paths differ"):
        GitInspector(repository).reviewed_change_evidence(
            reviewed_files=(Path("tracked.txt"),),
            expected_branch="master",
            expected_head=head,
            commit_message="feat(agent): reviewed evidence",
        )


def _candidate_review_state(
    repository: Path,
) -> tuple[GitInspector, tuple[tuple[str, str], ...], tuple[tuple[str, str], ...], str]:
    """Capture a dirty baseline and one candidate-owned tracked change."""

    (repository / "compose.execution-smoke.override.yaml").write_text(
        "baseline\n",
        encoding="utf-8",
    )
    inspector = GitInspector(repository)
    baseline = WorkerPatchApplier.capture_baseline(repository)
    (repository / "tracked.txt").write_text("candidate\n", encoding="utf-8")
    post_execution = WorkerPatchApplier.capture_baseline(repository)
    head = run_git(repository, "rev-parse", "HEAD").stdout.strip()
    return inspector, baseline, post_execution, head


def test_candidate_review_evidence_uses_workflow_delta_over_dirty_baseline(
    tmp_path: Path,
) -> None:
    """Unchanged pre-existing dirt is excluded from candidate review evidence."""

    repository = initialize_repository(tmp_path / "repository", with_commit=True)
    inspector, baseline, post_execution, head = _candidate_review_state(repository)

    evidence = inspector.reviewed_candidate_change_evidence(
        reviewed_files=(Path("tracked.txt"),),
        baseline_status=baseline,
        post_execution_status=post_execution,
        expected_branch="master",
        expected_head=head,
        commit_message="feat(agent): candidate review",
    )

    assert evidence.reviewed_files == (Path("tracked.txt"),)
    assert tuple(change.path for change in evidence.changes) == (Path("tracked.txt"),)


@pytest.mark.parametrize("mutation", ("baseline", "new", "target", "staged"))
def test_candidate_review_evidence_rejects_post_execution_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    """Candidate review fails closed for baseline, scope, content, or index drift."""

    repository = initialize_repository(tmp_path / "repository", with_commit=True)
    inspector, baseline, post_execution, head = _candidate_review_state(repository)
    if mutation == "baseline":
        (repository / "compose.execution-smoke.override.yaml").write_text(
            "mutated\n",
            encoding="utf-8",
        )
    elif mutation == "new":
        (repository / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
    elif mutation == "target":
        (repository / "tracked.txt").write_text("changed again\n", encoding="utf-8")
    else:
        run_git(repository, "add", "tracked.txt")

    with pytest.raises(RepositoryInspectionError):
        inspector.reviewed_candidate_change_evidence(
            reviewed_files=(Path("tracked.txt"),),
            baseline_status=baseline,
            post_execution_status=post_execution,
            expected_branch="master",
            expected_head=head,
            commit_message="feat(agent): candidate review",
        )


def test_candidate_review_evidence_is_deterministic(tmp_path: Path) -> None:
    """Repeated candidate evidence for unchanged state has one fingerprint."""

    repository = initialize_repository(tmp_path / "repository", with_commit=True)
    inspector, baseline, post_execution, head = _candidate_review_state(repository)
    kwargs = {
        "reviewed_files": (Path("tracked.txt"),),
        "baseline_status": baseline,
        "post_execution_status": post_execution,
        "expected_branch": "master",
        "expected_head": head,
        "commit_message": "feat(agent): candidate review",
    }

    first = inspector.reviewed_candidate_change_evidence(**kwargs)
    second = inspector.reviewed_candidate_change_evidence(**kwargs)

    assert first == second


@pytest.mark.parametrize("drift", ("branch", "head"))
def test_candidate_review_evidence_rejects_repository_identity_drift(
    tmp_path: Path,
    drift: str,
) -> None:
    """Candidate review requires the validated branch and HEAD."""

    repository = initialize_repository(tmp_path / "repository", with_commit=True)
    inspector, baseline, post_execution, head = _candidate_review_state(repository)
    expected_branch = "other-branch" if drift == "branch" else "master"
    expected_head = "not-the-head" if drift == "head" else head

    with pytest.raises(RepositoryInspectionError):
        inspector.reviewed_candidate_change_evidence(
            reviewed_files=(Path("tracked.txt"),),
            baseline_status=baseline,
            post_execution_status=post_execution,
            expected_branch=expected_branch,
            expected_head=expected_head,
            commit_message="feat(agent): candidate review",
        )


def test_reviewed_change_evidence_ignores_existing_logs_policy(
    tmp_path: Path,
) -> None:
    repository = initialize_repository(tmp_path / "repository", with_commit=True)
    head = run_git(repository, "rev-parse", "HEAD").stdout.strip()
    (repository / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (repository / "logs").mkdir()
    (repository / "logs" / "agent.log").write_text("debug\n", encoding="utf-8")

    evidence = GitInspector(repository).reviewed_change_evidence(
        reviewed_files=(Path("tracked.txt"),),
        expected_branch="master",
        expected_head=head,
        commit_message="feat(agent): reviewed evidence",
    )

    assert evidence.reviewed_files == (Path("tracked.txt"),)
