from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts.atlas_data_restore_copy import copy_private_backup
from scripts.atlas_data_restore_prepare import prepare_target
from scripts.test_atlas_data_tool import _close, _source, create_backup

WRAPPER = Path(__file__).with_name("atlas-data-restore")


def _backup(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    connections = _source(source)
    backup = tmp_path / "backup"
    create_backup(source, backup, operator_auth_initialized=False)
    _close(connections)
    return backup


def _fake_docker(tmp_path: Path) -> tuple[Path, Path]:
    executable_directory = tmp_path / "bin"
    executable_directory.mkdir()
    log = tmp_path / "docker.log"
    docker = executable_directory / "docker"
    docker.write_text(
        """#!/usr/bin/env bash
printf '%s\\n' "$*" >>"$FAKE_DOCKER_LOG"
if [[ ${1:-} = volume && ${2:-} = inspect ]]; then
    [[ ${3:-} = disposable-test-volume ]]
    exit
fi
if [[ ${1:-} = ps ]]; then printf '%s' "${FAKE_ATTACHED:-}"; exit 0; fi
if [[ ${1:-} = volume && ${2:-} = create ]]; then exit 0; fi
if [[ ${1:-} = volume && ${2:-} = rm ]]; then exit 0; fi
count=0
if [[ -f $FAKE_DOCKER_COUNT ]]; then count=$(cat "$FAKE_DOCKER_COUNT"); fi
count=$((count + 1))
printf '%s' "$count" >"$FAKE_DOCKER_COUNT"
if [[ $count = ${FAKE_FAIL_RUN_NUMBER:-1} ]]; then
    exit "${FAKE_DOCKER_RUN_EXIT:-23}"
fi
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o700)
    return executable_directory, log


def _run_wrapper(
    tmp_path: Path,
    backup: Path,
    *,
    attached: str = "",
    run_exit: str = "23",
    fail_run_number: str = "1",
) -> tuple[subprocess.CompletedProcess[str], str]:
    executable_directory, log = _fake_docker(tmp_path)
    result = subprocess.run(
        [str(WRAPPER), str(backup), "--confirm"],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{executable_directory}:{os.environ['PATH']}",
            "FAKE_DOCKER_LOG": str(log),
            "FAKE_DOCKER_COUNT": str(tmp_path / "docker.count"),
            "FAKE_ATTACHED": attached,
            "FAKE_DOCKER_RUN_EXIT": run_exit,
            "FAKE_FAIL_RUN_NUMBER": fail_run_number,
            "ATLAS_DATA_VOLUME": "disposable-test-volume",
        },
    )
    return result, log.read_text(encoding="utf-8")


@pytest.mark.parametrize("container", ("running-core\n", "stopped-core\n"))
def test_wrapper_rejects_any_attached_container(
    tmp_path: Path, container: str
) -> None:
    result, log = _run_wrapper(tmp_path, _backup(tmp_path), attached=container)
    assert result.returncode == 1
    assert "containers are attached" in result.stderr
    assert "ps -a --filter volume=disposable-test-volume" in log
    assert "volume create" not in log


def test_wrapper_ignores_unrelated_containers_and_reaches_private_copy(
    tmp_path: Path,
) -> None:
    result, log = _run_wrapper(tmp_path, _backup(tmp_path))
    assert result.returncode == 23
    assert "ps -a --filter volume=disposable-test-volume" in log
    assert "volume create atlas-restore-staging-" in log
    assert "src=" in log and "dst=/source,readonly" in log
    assert "--network none" in log
    assert "--cap-add DAC_READ_SEARCH" in log
    assert "Atlas data volume restored" not in result.stdout


def test_wrapper_reports_no_success_when_target_preparation_fails(
    tmp_path: Path,
) -> None:
    result, log = _run_wrapper(
        tmp_path, _backup(tmp_path), fail_run_number="2"
    )
    assert result.returncode == 23
    assert log.count("run --rm") == 2
    assert "Atlas data volume restored" not in result.stdout


def test_wrapper_reports_success_only_after_restore_helper_completes(
    tmp_path: Path,
) -> None:
    result, log = _run_wrapper(
        tmp_path, _backup(tmp_path), fail_run_number="never"
    )
    assert result.returncode == 0
    assert log.count("run --rm") == 3
    assert "Atlas data volume restored: disposable-test-volume" in result.stdout


def test_private_copy_preserves_source_and_produces_private_runtime_copy(
    tmp_path: Path,
) -> None:
    source = _backup(tmp_path)
    before = {
        path.relative_to(source): (path.read_bytes(), path.stat().st_mode & 0o777)
        for path in source.rglob("*")
        if path.is_file()
    }
    destination = tmp_path / "staged"
    copy_private_backup(source, destination, os.getuid(), os.getgid())
    assert destination.stat().st_mode & 0o777 == 0o700
    assert all(
        path.stat().st_mode & 0o777 == 0o600
        for path in destination.rglob("*")
        if path.is_file()
    )
    assert before == {
        path.relative_to(source): (path.read_bytes(), path.stat().st_mode & 0o777)
        for path in source.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("unsafe", ("symlink", "hardlink"))
def test_private_copy_rejects_linked_backup_content(
    tmp_path: Path, unsafe: str
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside")
    linked = source / "manifest.json"
    if unsafe == "symlink":
        linked.symlink_to(outside)
    else:
        os.link(outside, linked)
    with pytest.raises(RuntimeError, match="symbolic links|unsafe filesystem"):
        copy_private_backup(source, tmp_path / "staged", os.getuid(), os.getgid())
    assert outside.read_bytes() == b"outside"


def test_target_preparation_touches_only_managed_parents(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    unrelated = target / "cache"
    unrelated.mkdir(mode=0o750)
    for name in ("config", "secrets"):
        (target / name).mkdir(mode=0o755)
    prepare_target(target, os.getuid(), os.getgid())
    assert all((target / name).stat().st_mode & 0o777 == 0o700 for name in ("config", "secrets"))
    assert unrelated.stat().st_mode & 0o777 == 0o750


def test_recovery_gate_explicitly_refuses_production_volume() -> None:
    gate = Path(__file__).with_name("data-recovery-gate").read_text(encoding="utf-8")
    assert 'PRODUCTION_VOLUME="atlas_atlas-data"' in gate
    assert 'if [[ "$volume" = "$PRODUCTION_VOLUME" ]]' in gate


def test_wrapper_rejects_unsafe_volume_name_before_docker_use(tmp_path: Path) -> None:
    executable_directory, log = _fake_docker(tmp_path)
    result = subprocess.run(
        [str(WRAPPER), str(_backup(tmp_path)), "--confirm"],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{executable_directory}:{os.environ['PATH']}",
            "FAKE_DOCKER_LOG": str(log),
            "ATLAS_DATA_VOLUME": "target,readonly",
        },
    )
    assert result.returncode == 2
    assert "valid Docker volume name" in result.stderr
    assert not log.exists()
