from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from app.execution.worker_contracts import (
    RC1_SMOKE_MARKER,
    RC1_SMOKE_TARGET,
    WorkerExecutionIntent,
    WorkerExecutionRequest,
    WorkerFailureCode,
)
from atlas_execution_worker.config import write_git_config
from atlas_execution_worker.runner import WorkspaceExecutionRunner
from atlas_execution_worker.workspace import WorkerWorkspaceManager


def _git(path: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True).stdout.strip()


def _request(head: str, *, request_id: str = "execution-1", allowed: tuple[str, ...] = ("compose.production.yaml",)) -> WorkerExecutionRequest:
    return WorkerExecutionRequest.build(
        execution_request_id=request_id,
        workflow_id="workflow-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fp-1",
        plan_id="plan-1",
        plan_fingerprint="plan-fp-1",
        execution_intent="update-compose-stack",
        repository_token="trusted-repository",
        expected_repository_head=head,
        repository_branch=None,
        argv=("codex", "exec", "test-prompt"),
        working_directory=".",
        allowed_affected_files=allowed,
        timeout_seconds=10,
    )


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "source"
    repo.mkdir()
    (repo / "compose.production.yaml").write_text("image: example/app:1.0\n")
    (repo / "forbidden.txt").write_text("unchanged\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "initial")
    return repo, _git(repo, "rev-parse", "HEAD")


def _fake_codex(tmp_path: Path, *, touch_forbidden: bool = False) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = bindir / "codex"
    extra = "Path('forbidden.txt').write_text('changed\\n')" if touch_forbidden else ""
    script.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "p = Path('compose.production.yaml')\n"
        "p.write_text(p.read_text().replace('1.0', '1.1'))\n"
        f"{extra}\n"
    )
    script.chmod(0o755)
    return bindir


def test_workspace_git_uses_exact_scoped_safe_directory(tmp_path: Path) -> None:
    path = tmp_path / "workspace"
    path.mkdir()
    with patch("atlas_execution_worker.workspace.subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="head\n", stderr=""
        )
        assert WorkerWorkspaceManager(path, tmp_path / "workspaces", "token", trusted_repository_paths=(path,), git_config_path=tmp_path / "gitconfig")._git(path, "rev-parse", "HEAD") == "head"
    command = run.call_args.args[0]
    assert command[:3] == ["git", "-C", str(path)]
    assert run.call_args.kwargs["env"]["GIT_CONFIG_GLOBAL"] == str((tmp_path / "gitconfig").resolve())
    assert "safe.directory=*" not in command


def test_workspace_clone_uses_exact_source_safe_directory_and_no_local(
    repository: tuple[Path, str], tmp_path: Path
) -> None:
    source, head = repository
    manager = WorkerWorkspaceManager(
        source,
        tmp_path / "workspaces",
        "trusted-repository",
        trusted_repository_paths=(source,),
        git_config_path=tmp_path / "gitconfig",
    )
    request = _request(head)
    with patch("atlas_execution_worker.workspace.subprocess.run") as run:
        run.side_effect = [
            subprocess.CompletedProcess([], 0, f"{head}\n", ""),
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, f"{head}\n", ""),
        ]
        manager.prepare(request)
    clone = run.call_args_list[1].args[0]
    assert clone[:2] == ["git", "clone"]
    assert run.call_args_list[1].kwargs["env"]["GIT_CONFIG_GLOBAL"] == str((tmp_path / "gitconfig").resolve())
    assert "--no-local" in clone
    assert "--no-hardlinks" in clone
    assert "safe.directory=*" not in clone


def test_unconfigured_source_is_not_implicitly_trusted(
    repository: tuple[Path, str], tmp_path: Path
) -> None:
    source, head = repository
    manager = WorkerWorkspaceManager(
        source,
        tmp_path / "workspaces",
        "trusted-repository",
        trusted_repository_paths=(),
        git_config_path=tmp_path / "gitconfig",
    )

    with pytest.raises(Exception, match="not configured"):
        manager.prepare(_request(head))


@pytest.mark.skipif(os.geteuid() != 0, reason="requires ownership change")
def test_real_clone_succeeds_for_differently_owned_configured_source(
    repository: tuple[Path, str], tmp_path: Path
) -> None:
    source, head = repository
    source_status_before = _git(source, "status", "--porcelain")
    os.chown(source, 65534, 65534)
    for path in source.rglob("*"):
        os.chown(path, 65534, 65534)
    config_path = tmp_path / "state" / "gitconfig"
    write_git_config([source], config_path)
    manager = WorkerWorkspaceManager(
        source,
        tmp_path / "workspaces",
        "trusted-repository",
        trusted_repository_paths=(source,),
        git_config_path=config_path,
    )

    workspace = manager.prepare(_request(head))

    assert _git(workspace.path, "rev-parse", "HEAD") == head
    assert (source / "compose.production.yaml").read_text() == "image: example/app:1.0\n"
    source_status_after = subprocess.run(
        ["git", "-C", str(source), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": str(config_path)},
    ).stdout.strip()
    assert source_status_after == source_status_before
    manager.cleanup("execution-1")


def test_enabled_runner_returns_bounded_patch_and_cleans_workspace(repository: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, head = repository
    monkeypatch.setenv("PATH", f"{_fake_codex(tmp_path)}:{os.environ['PATH']}")
    manager = WorkerWorkspaceManager(source, tmp_path / "workspaces", "trusted-repository", trusted_repository_paths=(source,), git_config_path=tmp_path / "gitconfig")
    result = WorkspaceExecutionRunner(manager, enabled=True).execute(_request(head))
    assert result.failure_code is None
    assert result.changed_files == ("compose.production.yaml",)
    assert result.base_repository_head == head
    assert result.patch is not None
    assert "1.0" in result.patch.text and "1.1" in result.patch.text
    assert not (tmp_path / "workspaces" / "execution-1").exists()
    assert _git(source, "diff") == ""


def test_out_of_scope_change_is_blocked(repository: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, head = repository
    monkeypatch.setenv("PATH", f"{_fake_codex(tmp_path, touch_forbidden=True)}:{os.environ['PATH']}")
    request = _request(head, allowed=("compose.production.yaml",))
    result = WorkspaceExecutionRunner(WorkerWorkspaceManager(source, tmp_path / "workspaces", "trusted-repository", trusted_repository_paths=(source,), git_config_path=tmp_path / "gitconfig"), enabled=True).execute(request)
    assert result.failure_code is WorkerFailureCode.OUT_OF_SCOPE_CHANGES
    assert result.status.value == "blocked"
    assert _git(source, "diff") == ""


def test_stale_head_is_rejected_before_runner(repository: tuple[Path, str], tmp_path: Path) -> None:
    source, _ = repository
    request = _request("0" * 40)
    result = WorkspaceExecutionRunner(WorkerWorkspaceManager(source, tmp_path / "workspaces", "trusted-repository", trusted_repository_paths=(source,), git_config_path=tmp_path / "gitconfig"), enabled=True).execute(request)
    assert result.failure_code is WorkerFailureCode.STALE_REPOSITORY
    assert not (tmp_path / "workspaces" / request.execution_request_id).exists()


def test_disabled_runner_never_launches_argv(repository: tuple[Path, str], tmp_path: Path) -> None:
    source, head = repository
    result = WorkspaceExecutionRunner(WorkerWorkspaceManager(source, tmp_path / "workspaces", "trusted-repository", trusted_repository_paths=(source,), git_config_path=tmp_path / "gitconfig"), enabled=False).execute(_request(head))
    assert result.failure_code is WorkerFailureCode.WORKER_UNAVAILABLE
    assert result.return_code is None
    assert _git(source, "diff") == ""


def test_rc1_smoke_directly_mutates_only_fixed_target(repository: tuple[Path, str], tmp_path: Path) -> None:
    source, head = repository
    target = source / RC1_SMOKE_TARGET
    target.parent.mkdir(parents=True)
    target.write_text("def test_placeholder():\n    pass\n")
    _git(source, "add", RC1_SMOKE_TARGET)
    _git(source, "commit", "-qm", "add smoke target")
    head = _git(source, "rev-parse", "HEAD")
    request = WorkerExecutionRequest.build(
        execution_request_id="smoke-1",
        workflow_id="workflow-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fp-1",
        plan_id="plan-1",
        plan_fingerprint="plan-fp-1",
        execution_intent=WorkerExecutionIntent.RC1_VALIDATION_SMOKE,
        repository_token="trusted-repository",
        expected_repository_head=head,
        repository_branch=None,
        argv=("atlas-rc1-validation-smoke",),
        working_directory=".",
        allowed_affected_files=(RC1_SMOKE_TARGET,),
        timeout_seconds=10,
    )
    with patch("atlas_execution_worker.runner.subprocess.run", wraps=subprocess.run) as run:
        result = WorkspaceExecutionRunner(
            WorkerWorkspaceManager(source, tmp_path / "workspaces", "trusted-repository", trusted_repository_paths=(source,), git_config_path=tmp_path / "gitconfig"),
            enabled=True,
        ).execute(request)
    assert result.failure_code is None
    assert result.changed_files == (RC1_SMOKE_TARGET,)
    assert result.patch is not None
    assert RC1_SMOKE_MARKER in result.patch.text
    assert "atlas-rc1-validation-smoke" not in [str(call) for call in run.call_args_list]
    assert _git(source, "diff") == ""


def test_rc1_smoke_rejects_arbitrary_command_and_scope(repository: tuple[Path, str]) -> None:
    _, head = repository
    with pytest.raises(ValueError, match="RC1 validation smoke"):
        WorkerExecutionRequest.build(
            execution_request_id="smoke-2",
            workflow_id="workflow-1",
            candidate_id="candidate-1",
            candidate_fingerprint="candidate-fp-1",
            plan_id="plan-1",
            plan_fingerprint="plan-fp-1",
            execution_intent=WorkerExecutionIntent.RC1_VALIDATION_SMOKE,
            repository_token="trusted-repository",
            expected_repository_head=head,
            repository_branch=None,
            argv=("python3", "-c", "pass"),
            working_directory=".",
            allowed_affected_files=(RC1_SMOKE_TARGET, "other.txt"),
            timeout_seconds=10,
        )


def test_manager_reuses_one_request_workspace(repository: tuple[Path, str], tmp_path: Path) -> None:
    source, head = repository
    manager = WorkerWorkspaceManager(source, tmp_path / "workspaces", "trusted-repository", trusted_repository_paths=(source,), git_config_path=tmp_path / "gitconfig")
    request = _request(head)
    first = manager.prepare(request)
    second = manager.prepare(request)
    assert first == second
    manager.cleanup(request.execution_request_id)


def test_symlinked_source_is_rejected(repository: tuple[Path, str], tmp_path: Path) -> None:
    source, _ = repository
    link = tmp_path / "source-link"
    link.symlink_to(source, target_is_directory=True)
    manager = WorkerWorkspaceManager(link, tmp_path / "workspaces", "trusted-repository", trusted_repository_paths=(source,), git_config_path=tmp_path / "gitconfig")
    with pytest.raises(Exception, match="trusted repository source"):
        manager.prepare(_request(_git(source, "rev-parse", "HEAD")))
