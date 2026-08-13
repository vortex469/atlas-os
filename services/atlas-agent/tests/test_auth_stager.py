"""Tests for the isolated root-to-agent Codex auth staging step."""

import os
import stat
import subprocess
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

STAGER = Path("deploy/docker/atlas-agent-auth-stager.sh")
DOCKERFILE = Path("deploy/docker/atlas-agent.Dockerfile")
EXECUTION_AUTH_STAGER = Path("deploy/docker/atlas-execution-auth-stager.py")


def run_stager(
    source: Path, destination: Path, *, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(STAGER), str(source), str(destination)],
        capture_output=True,
        text=True,
        check=False,
        env=environment or os.environ,
    )


def test_staging_sets_agent_ownership_and_mode(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_text("{}\n")
    destination = tmp_path / "staging" / "auth.json"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    chown_log = tmp_path / "chown.log"
    fake_chown = fake_bin / "chown"
    fake_chown.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" >"$CHOWN_LOG"\n')
    fake_chown.chmod(0o755)

    result = run_stager(
        source,
        destination,
        environment={
            **os.environ,
            "CHOWN_LOG": str(chown_log),
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
        },
    )

    assert result.returncode == 0, result.stderr
    metadata = destination.stat()
    assert chown_log.read_text().splitlines() == [
        "10001:10001",
        f"{destination}.tmp",
    ]
    assert stat.S_IMODE(metadata.st_mode) == 0o600
    assert result.stdout == ""
    assert result.stderr == ""


def test_missing_source_fails_closed_without_contents(tmp_path: Path) -> None:
    result = run_stager(tmp_path / "missing", tmp_path / "staging" / "auth.json")

    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr == "atlas-agent auth staging failed: auth source is missing\n"


def test_stager_sets_mode_before_transferring_ownership() -> None:
    script = STAGER.read_text()
    assert script.index('chmod 0600 "$temporary_path"') < script.index(
        'chown 10001:10001 "$temporary_path"'
    )
    assert 'rm -f "$destination_path" "$temporary_path"' in script


def test_agent_remains_non_root_and_execution_is_disabled() -> None:
    assert "USER atlas" in DOCKERFILE.read_text()
    compose = Path("compose.production.yaml").read_text()
    assert "atlas-agent-auth-staging:/run/secrets:ro" in compose
    assert "atlas-execution-transport-net: {}" in compose
    assert "ATLAS_EXECUTION_WORKER_HOST: atlas-execution-worker-relay" in compose
    assert 'ATLAS_EXECUTION_WORKER_EXECUTION_ENABLED: "false"' in compose


def test_execution_auth_stager_creates_and_preserves_private_token(
    tmp_path: Path, monkeypatch
) -> None:
    token = tmp_path / "staging" / "token"
    spec = spec_from_file_location("atlas_execution_auth_stager", EXECUTION_AUTH_STAGER)
    assert spec is not None and spec.loader is not None
    stager = module_from_spec(spec)
    spec.loader.exec_module(stager)
    ownership_calls: list[tuple[Path, int, int]] = []

    def fake_chown(path: Path, uid: int, gid: int) -> None:
        ownership_calls.append((path, uid, gid))

    def fake_stat(path: Path) -> SimpleNamespace:
        metadata = path.stat()
        return SimpleNamespace(st_uid=10001, st_gid=10001, st_mode=metadata.st_mode)

    monkeypatch.setenv("ATLAS_EXECUTION_AUTH_STAGING_FILE", str(token))
    stager.main(chown=fake_chown, inspect=fake_stat)
    original = token.read_text()
    stager.main(chown=fake_chown, inspect=fake_stat)

    assert len(original.strip()) >= 64
    assert token.read_text() == original
    assert ownership_calls == [(token, 10001, 10001)]
    assert stat.S_IMODE(token.stat().st_mode) == 0o400
