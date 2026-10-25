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


def test_repository_mapping_trusts_multiple_sources_individually(tmp_path: Path) -> None:
    first = git_repository(tmp_path / "first")
    second = git_repository(tmp_path / "second")

    assert load_repository_mapping(f"one={first},two={second}") == {
        "one": first.resolve(),
        "two": second.resolve(),
    }


def test_repository_mapping_writes_only_exact_configured_source_paths(tmp_path: Path) -> None:
    source = git_repository(tmp_path / "source")
    other = git_repository(tmp_path / "other")
    config_path = tmp_path / "state" / "gitconfig"
    with patch("atlas_execution_worker.config.subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="true\n", stderr=""
        )
        assert load_repository_mapping(
            f"atlas-repository={source}", git_config_path=config_path
        ) == {"atlas-repository": source.resolve()}
    command = run.call_args.args[0]
    assert command[:3] == ["git", "-C", str(source.resolve())]
    assert run.call_args.kwargs["env"]["GIT_CONFIG_GLOBAL"] == str(config_path)
    assert config_path.read_text() == (
        "[safe]\n"
        f'\tdirectory = "{source.resolve()}"\n' 
        f'\tdirectory = "{source.resolve() / ".git"}"\n' 
    )
    assert config_path.stat().st_mode & 0o777 == 0o600
    assert "safe.directory=*" not in config_path.read_text()
    assert str(other.resolve()) not in config_path.read_text()


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


@pytest.mark.parametrize('token', ['bad\ntoken', '..', 'quarantine', 'a' * 257, 'with space'])
def test_repository_tokens_share_request_path_contract(tmp_path, token):
    source = git_repository(tmp_path / 'source')
    with pytest.raises(WorkerConfigurationError):
        load_repository_mapping(f'{token}={source}')


def test_safe_directory_config_round_trips_quotes_and_backslashes(tmp_path):
    from atlas_execution_worker.config import write_git_config

    source = git_repository(tmp_path / 'source "quoted" \\ path #comment')
    config = write_git_config([source], tmp_path / 'gitconfig')
    result = subprocess.run(['git', 'config', '--file', str(config), '--null',
                             '--get-all', 'safe.directory'], capture_output=True, check=True)
    assert result.stdout.decode().split('\0') == [str(source), str(source / '.git'), '']
    assert config.stat().st_mode & 0o777 == 0o600


def test_config_directive_injection_is_refused_before_write(tmp_path):
    from atlas_execution_worker.config import write_git_config

    source = tmp_path / 'source\n[include]\npath = private'
    source.mkdir()
    config = tmp_path / 'gitconfig'
    with pytest.raises(WorkerConfigurationError):
        write_git_config([source], config)
    assert not config.exists()
