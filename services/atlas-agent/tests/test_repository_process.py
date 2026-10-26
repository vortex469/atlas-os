"""Independent local process fixtures for Agent Git bounds and cleanup."""

import os
import shlex
import subprocess
import sys
import time
import traceback
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from app.repository.process import GitProcessBudget, GitProcessError, GitProcessRunner


def fixture_arguments(root: Path, source: str) -> tuple[str, ...]:
    script = root / "git-fixture.py"
    script.write_text(source, encoding="utf-8")
    command = f"!{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
    return ("-c", f"alias.fixture={command}", "fixture")


def assert_stopped(pid: int) -> None:
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        try:
            state = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()[0]
        except FileNotFoundError:
            return
        if state == "Z":
            return
        time.sleep(0.01)
    pytest.fail("Fixture child survived its owned process group")


def test_drains_both_streams_and_keeps_exact_bound(tmp_path: Path) -> None:
    arguments = fixture_arguments(tmp_path, """
import os
for _ in range(8):
    os.write(1, b'a' * 8192)
    os.write(2, b'b' * 8192)
""")
    result = GitProcessRunner().run(
        arguments, cwd=tmp_path, budget=GitProcessBudget(2),
        stdout_limit=65536, stderr_limit=65536,
    )
    assert result.returncode == 0
    assert result.stdout == b"a" * 65536
    assert result.stderr == b"b" * 65536


def test_streams_binary_blob_digest_without_retaining_stdout(tmp_path: Path) -> None:
    arguments = fixture_arguments(tmp_path, """
import os
for _ in range(64):
    os.write(1, b'\\xff\\x00\\r\\n' * 4096)
""")
    result = GitProcessRunner().run(
        arguments, cwd=tmp_path, budget=GitProcessBudget(2),
        digest_stdout=True, stdout_limit=1,
    )
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stdout_digest == sha256(b"\xff\x00\r\n" * (4096 * 64)).hexdigest()


@pytest.mark.parametrize("stream", (1, 2))
def test_noisy_command_is_refused_without_retaining_partial_output(
    tmp_path: Path, stream: int,
) -> None:
    arguments = fixture_arguments(tmp_path, f"""
import os
while True:
    os.write({stream}, b'x' * 65536)
""")
    started = time.monotonic()
    with pytest.raises(GitProcessError, match="git_output_limit_exceeded"):
        GitProcessRunner().run(
            arguments, cwd=tmp_path, budget=GitProcessBudget(2),
            stdout_limit=1024, stderr_limit=1024,
        )
    assert time.monotonic() - started < 3


@pytest.mark.parametrize("keep_pipes", (False, True))
def test_parent_exit_cleans_owned_child_even_with_inherited_pipes(
    tmp_path: Path, keep_pipes: bool,
) -> None:
    pidfile = tmp_path / "child.pid"
    arguments = fixture_arguments(tmp_path, f"""
import os
import time
from pathlib import Path
pid = os.fork()
if pid:
    Path({str(pidfile)!r}).write_text(str(pid))
    os._exit(0)
if not {keep_pipes!r}:
    os.close(1)
    os.close(2)
time.sleep(30)
""")
    try:
        if keep_pipes:
            with pytest.raises(GitProcessError, match="git_deadline_exceeded"):
                GitProcessRunner().run(arguments, cwd=tmp_path, budget=GitProcessBudget(0.5))
        else:
            result = GitProcessRunner().run(arguments, cwd=tmp_path, budget=GitProcessBudget(2))
            assert result.returncode == 0
        assert_stopped(int(pidfile.read_text()))
    finally:
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text()), 9)
            except ProcessLookupError:
                pass


def test_commands_share_one_deadline_instead_of_resetting_it(tmp_path: Path) -> None:
    arguments = fixture_arguments(tmp_path, "import time\ntime.sleep(0.45)\n")
    budget = GitProcessBudget(0.8)
    runner = GitProcessRunner()
    assert runner.run(arguments, cwd=tmp_path, budget=budget).returncode == 0
    with pytest.raises(GitProcessError, match="git_deadline_exceeded"):
        runner.run(arguments, cwd=tmp_path, budget=budget)


def test_expired_shared_budget_does_not_launch_another_command(tmp_path, monkeypatch) -> None:
    budget = GitProcessBudget(1)
    monkeypatch.setattr("app.repository.process.time.monotonic", lambda: budget.deadline + 1)
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(GitProcessError, match="git_deadline_exceeded"):
        GitProcessRunner().run(("status",), cwd=tmp_path, budget=budget)
    assert calls == []


@pytest.mark.parametrize("timeout", (True, False, 0, -1, float("nan"), float("inf"), 61, 10**1000, "1", None))
def test_invalid_budget_is_refused_before_launch(monkeypatch, timeout) -> None:
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(ValueError, match="Git budget"):
        GitProcessBudget(timeout)
    assert calls == []


@pytest.mark.parametrize("bound", (True, 0, -1, 1048577, "1", None))
def test_invalid_output_bound_is_refused_before_launch(tmp_path, monkeypatch, bound) -> None:
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(ValueError, match="output bound"):
        GitProcessRunner().run(("status",), cwd=tmp_path, stdout_limit=bound)
    assert calls == []


def test_launch_error_and_exception_chain_do_not_disclose_arguments_or_os_error(
    tmp_path: Path, monkeypatch,
) -> None:
    canary = uuid4().hex

    def fail_launch(*args, **kwargs):
        raise OSError(canary)

    monkeypatch.setattr(subprocess, "Popen", fail_launch)
    with pytest.raises(GitProcessError, match="git_launch_failed") as error:
        GitProcessRunner().run((canary,), cwd=tmp_path)
    assert canary not in "".join(traceback.format_exception(error.value))
