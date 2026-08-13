"""Tests for the production Atlas Agent credential staging gate."""

import os
import stat
import subprocess
from pathlib import Path

ENTRYPOINT = Path("deploy/docker/atlas-agent-entrypoint.sh")
DOCKERFILE = Path("deploy/docker/atlas-agent.Dockerfile")


def run_gate(
    tmp_path: Path, source: Path, *, codex_status: int = 0
) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "codex-home"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    codex = fake_bin / "codex"
    codex.write_text(f"#!/bin/sh\nexit {codex_status}\n")
    codex.chmod(0o755)
    return subprocess.run(
        ["sh", str(ENTRYPOINT), "sh", "-c", "test -f \"$CODEX_HOME/auth.json\""],
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "CODEX_AUTH_SOURCE": str(source),
            "CODEX_HOME": str(home),
        },
        capture_output=True,
        text=True,
        check=False,
    )


def test_missing_auth_fails_closed_without_logging_contents(tmp_path: Path) -> None:
    result = run_gate(tmp_path, tmp_path / "missing-auth.json")
    assert result.returncode != 0
    assert "missing-auth.json" not in result.stderr


def test_non_file_auth_source_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "auth-directory"
    source.mkdir()

    result = run_gate(tmp_path, source)

    assert result.returncode != 0


def test_valid_auth_is_staged_with_restrictive_mode(tmp_path: Path) -> None:
    source = tmp_path / "source-auth.json"
    source.write_text("{}\n")

    result = run_gate(tmp_path, source)

    assert result.returncode == 0, result.stderr
    staged = tmp_path / "codex-home" / "auth.json"
    assert staged.is_file()
    assert stat.S_IMODE(staged.stat().st_mode) == 0o600
    assert result.stdout == ""
    assert result.stderr == ""


def test_unauthenticated_codex_status_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "source-auth.json"
    source.write_text("{}\n")

    result = run_gate(tmp_path, source, codex_status=1)

    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr == (
        "atlas-agent startup gate failed: "
        "Codex authentication status is not authenticated\n"
    )


def test_agent_image_remains_non_root() -> None:
    assert "USER atlas" in DOCKERFILE.read_text()
    assert "useradd" in DOCKERFILE.read_text()
