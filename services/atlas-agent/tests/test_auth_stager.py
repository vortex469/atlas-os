"""Tests for the isolated root-to-agent Codex auth staging step."""

import os
import stat
import subprocess
from pathlib import Path

STAGER = Path("deploy/docker/atlas-agent-auth-stager.sh")
DOCKERFILE = Path("deploy/docker/atlas-agent.Dockerfile")


def run_stager(source: Path, destination: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(STAGER), str(source), str(destination)],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ,
    )


def test_staging_sets_agent_ownership_and_mode(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_text("{}\n")
    destination = tmp_path / "staging" / "auth.json"

    result = run_stager(source, destination)

    assert result.returncode == 0, result.stderr
    metadata = destination.stat()
    assert metadata.st_uid == 10001
    assert metadata.st_gid == 10001
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
    assert "atlas-execution-worker-net: {}" in compose
    assert "ATLAS_EXECUTION_WORKER_HOST: atlas-execution-worker" in compose
    assert 'ATLAS_EXECUTION_WORKER_EXECUTION_ENABLED: "false"' in compose
