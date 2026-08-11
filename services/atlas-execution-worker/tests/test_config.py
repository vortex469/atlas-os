"""Worker execution configuration tests."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from atlas_execution_worker.config import (
    WorkerConfigurationError,
    WorkerSettings,
    load_repository_mapping,
    parse_bool,
)


def git_repository(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    return path


def test_parse_bool_is_strict() -> None:
    assert parse_bool(None) is False
    assert parse_bool(" true ") is True
    assert parse_bool("FALSE") is False
    with pytest.raises(WorkerConfigurationError):
        parse_bool("yes")


def test_repository_mapping_requires_opaque_token_and_git_source(tmp_path: Path) -> None:
    source = git_repository(tmp_path / "source")
    assert load_repository_mapping(f"atlas-repository={source}") == {
        "atlas-repository": source.resolve()
    }
    with pytest.raises(WorkerConfigurationError):
        load_repository_mapping(f"bad/token={source}")
    with pytest.raises(WorkerConfigurationError):
        load_repository_mapping(f"missing={tmp_path / 'missing'}")


def test_repository_mapping_uses_exact_scoped_safe_directory(tmp_path: Path) -> None:
    source = git_repository(tmp_path / "source")
    with patch("atlas_execution_worker.config.subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="true\n", stderr=""
        )
        assert load_repository_mapping(f"atlas-repository={source}") == {
            "atlas-repository": source.resolve()
        }
    command = run.call_args.args[0]
    assert command[:4] == [
        "git",
        "-c",
        f"safe.directory={source.resolve()}",
        "-C",
    ]
    assert "safe.directory=*" not in command


def test_repository_mapping_rejects_duplicates_and_symlinks(tmp_path: Path) -> None:
    source = git_repository(tmp_path / "source")
    link = tmp_path / "link"
    link.symlink_to(source, target_is_directory=True)
    with pytest.raises(WorkerConfigurationError):
        load_repository_mapping(f"token={source},token={source}")
    with pytest.raises(WorkerConfigurationError):
        load_repository_mapping(f"token={link}")


def test_enabled_settings_require_repository_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_EXECUTION_WORKER_EXECUTION_ENABLED", "true")
    monkeypatch.delenv("ATLAS_EXECUTION_WORKER_REPOSITORY_MAP", raising=False)
    with pytest.raises(WorkerConfigurationError):
        WorkerSettings.from_environment()


def test_disabled_settings_do_not_require_repository_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_EXECUTION_WORKER_EXECUTION_ENABLED", "false")
    monkeypatch.delenv("ATLAS_EXECUTION_WORKER_REPOSITORY_MAP", raising=False)
    settings = WorkerSettings.from_environment()
    assert settings.execution_enabled is False
    assert settings.repository_mapping == {}
