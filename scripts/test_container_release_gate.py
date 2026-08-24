import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/container-release-gate"


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, check=check, text=True, capture_output=True
    )


def initialize_repository(path: Path) -> str:
    path.mkdir()
    run("git", "init", "--quiet", str(path))
    run("git", "config", "user.name", "Release Gate Test", cwd=path)
    run("git", "config", "user.email", "gate@example.invalid", cwd=path)
    (path / "candidate.txt").write_text("candidate\n", encoding="utf-8")
    run("git", "add", "candidate.txt", cwd=path)
    run("git", "commit", "--quiet", "-m", "candidate", cwd=path)
    return run("git", "rev-parse", "HEAD", cwd=path).stdout.strip()


def stage(source: Path, destination: Path) -> subprocess.CompletedProcess[str]:
    return run(
        "bash",
        "-c",
        'source "$1"; stage_candidate_repository "$2" "$3"',
        "stage-test",
        str(GATE),
        str(source),
        str(destination),
        check=False,
    )


@pytest.mark.parametrize("linked", [False, True], ids=["normal", "linked-worktree"])
def test_stages_self_contained_checkout_at_exact_head(tmp_path: Path, linked: bool) -> None:
    repository = tmp_path / "repository"
    expected_head = initialize_repository(repository)
    source = repository
    if linked:
        source = tmp_path / "linked"
        run("git", "worktree", "add", "--quiet", str(source), "HEAD", cwd=repository)
        assert (source / ".git").is_file()

    staged = tmp_path / "staged"
    result = stage(source, staged)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected_head
    assert (staged / ".git").is_dir()
    assert run("git", "rev-parse", "--is-inside-work-tree", cwd=staged).stdout.strip() == "true"
    assert run("git", "rev-parse", "HEAD", cwd=staged).stdout.strip() == expected_head
    shutil.rmtree(repository)
    assert run("git", "rev-parse", "HEAD", cwd=staged).stdout.strip() == expected_head


def test_stale_or_mismatched_staged_head_fails_closed(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    expected_head = initialize_repository(repository)
    (repository / "candidate.txt").write_text("second\n", encoding="utf-8")
    run("git", "commit", "--all", "--quiet", "-m", "second", cwd=repository)
    staged = tmp_path / "staged"
    assert stage(repository, staged).returncode == 0

    result = run(
        "bash", "-c",
        'source "$1"; verify_staged_repository_head "$2" "$3"',
        "verify-test", str(GATE), str(staged), expected_head, check=False,
    )
    assert result.returncode != 0
    assert "HEAD mismatch" in result.stderr


def test_tracked_dirty_candidate_fails_before_staging(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    initialize_repository(repository)
    (repository / "candidate.txt").write_text("dirty\n", encoding="utf-8")
    staged = tmp_path / "staged"

    result = stage(repository, staged)

    assert result.returncode != 0
    assert "tracked uncommitted changes" in result.stderr
    assert not staged.exists()


def test_stage_failure_precedes_compose_and_cleanup_removes_checkout(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    initialize_repository(repository)
    scripts = repository / "scripts"
    scripts.mkdir()
    shutil.copy2(GATE, scripts / GATE.name)
    run("git", "add", "scripts/container-release-gate", cwd=repository)
    run("git", "commit", "--quiet", "-m", "add gate", cwd=repository)

    gate_directory = tmp_path / "gate-owned"
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    (bin_directory / "mktemp").write_text(
        f"#!/bin/sh\nmkdir '{gate_directory}'\nprintf '%s\\n' '{gate_directory}'\n",
        encoding="utf-8",
    )
    (bin_directory / "mktemp").chmod(0o755)
    git_log = tmp_path / "git.log"
    real_git = shutil.which("git")
    assert real_git is not None
    (bin_directory / "git").write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >>'{git_log}'\n"
        "if [ \"$1\" = clone ]; then\n"
        "    for destination do :; done\n"
        "    mkdir -p \"$destination\"\n"
        "    printf 'partial staging\\n' >\"$destination/partial\"\n"
        "    printf 'controlled staging failure\\n' >&2\n"
        "    exit 73\n"
        "fi\n"
        f"exec '{real_git}' \"$@\"\n",
        encoding="utf-8",
    )
    (bin_directory / "git").chmod(0o755)
    docker_log = tmp_path / "docker.log"
    (bin_directory / "docker").write_text(
        f"#!/bin/sh\nprintf '%s\\n' \"$*\" >>'{docker_log}'\nexit 0\n",
        encoding="utf-8",
    )
    (bin_directory / "docker").chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bin_directory}:{env['PATH']}"

    result = subprocess.run(
        ("bash", str(scripts / GATE.name)), cwd=repository, env=env,
        text=True, capture_output=True,
    )

    assert result.returncode != 0
    assert "controlled staging failure" in result.stderr
    assert any(line.startswith("clone ") for line in git_log.read_text().splitlines())
    assert not gate_directory.exists()
    assert not docker_log.exists()


def test_repository_mount_security_contract_remains_read_only() -> None:
    compose = (ROOT / "compose.production.yaml").read_text(encoding="utf-8")
    gate = GATE.read_text(encoding="utf-8")
    worker_config = (
        ROOT / "services/atlas-execution-worker/atlas_execution_worker/config.py"
    ).read_text(encoding="utf-8")

    assert (
        "${ATLAS_REPOSITORY_HOST_PATH:?set ATLAS_REPOSITORY_HOST_PATH}"
        ":/workspace/repository:ro"
    ) in compose
    assert 'export ATLAS_REPOSITORY_HOST_PATH="$GATE_STAGED_REPOSITORY"' in gate
    assert "repository map source must be a git worktree" in worker_config


def test_runtime_policy_probe_preserves_lxc_inventory_without_management_identity() -> (
    None
):
    gate = GATE.read_text(encoding="utf-8")

    assert "resources/110/expectation" in gate
    assert '"resource_id":"110"' in gate
    assert '"110":{"expected":"stopped"}' in gate
    assert '"vmid": 109' in gate
    assert '"type": "lxc"' in gate
    assert '"vmid": 110' in gate
    assert '"type": "qemu"' in gate
    assert (
        'assert {item.resource_id for item in observed.resources} == {"109", "110"}'
        in gate
    )
    assert "lxc_support.authoritative_identity_supported is False" in gate
    assert "lxc_support.provider_intent_capability_supported is False" in gate
    assert "lxc_projection.management_fingerprint is None" in gate
    assert "lxc_projection.mutation_available is False" in gate
    assert "qemu_projection.management_fingerprint is not None" in gate
    assert 'resources["109"].expectation.value == "stopped"' not in gate
