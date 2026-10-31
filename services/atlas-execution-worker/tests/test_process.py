"""Command lifetime tests with real subprocesses, never a model."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from atlas_execution_worker.process import run_command


def alive(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().split()[2] != 'Z'
    except (FileNotFoundError, ProcessLookupError):
        return False


@pytest.mark.parametrize('disappearing_error', [FileNotFoundError, ProcessLookupError])
def test_process_disappearing_during_procfs_read_is_not_alive(monkeypatch, disappearing_error):
    def read_text(self):
        raise disappearing_error()

    monkeypatch.setattr(Path, 'read_text', read_text)
    assert not alive(12345)


@pytest.mark.parametrize('parent_exits', [False, True])
def test_deadline_kills_child_holding_output_pipe(tmp_path, parent_exits):
    marker = tmp_path / 'child.pid'
    code = (
        "import subprocess,sys,time; from pathlib import Path; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        f"Path({str(marker)!r}).write_text(str(p.pid)); "
        + ("sys.exit(0)" if parent_exits else "time.sleep(60)")
    )
    started = time.monotonic()
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            run_command([sys.executable, '-c', code], cwd=tmp_path, timeout=0.3)
        pid = int(marker.read_text())
        deadline = time.monotonic() + 1
        while alive(pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not alive(pid)
        assert time.monotonic() - started < 3
    finally:
        if marker.exists() and alive(int(marker.read_text())):
            os.kill(int(marker.read_text()), signal.SIGKILL)


def test_success_also_stops_background_child_without_output_pipes(tmp_path):
    marker = tmp_path / 'child.pid'
    code = (
        "import subprocess,sys; from pathlib import Path; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],"
        "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
        f"Path({str(marker)!r}).write_text(str(p.pid)); print('complete')"
    )
    try:
        result = run_command([sys.executable, '-c', code], cwd=tmp_path, timeout=2)
        assert result.returncode == 0
        assert result.stdout.text == 'complete\n'
        pid = int(marker.read_text())
        deadline = time.monotonic() + 1
        while alive(pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not alive(pid)
    finally:
        if marker.exists() and alive(int(marker.read_text())):
            os.kill(int(marker.read_text()), signal.SIGKILL)


def test_concurrent_large_streams_are_drained_with_bounded_memory(tmp_path):
    import tracemalloc

    size = 4 * 1024 * 1024
    code = ("import os,threading; "
            f"t=threading.Thread(target=lambda: os.write(2,b'e'*{size})); t.start(); "
            f"os.write(1,b'o'*{size}); t.join()")
    tracemalloc.start()
    try:
        result = run_command([sys.executable, '-c', code], cwd=tmp_path, timeout=5, output_limit=65536)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result.returncode == 0
    for output in (result.stdout, result.stderr):
        output.validate()
        assert output.original_bytes == size
        assert output.truncated
        assert len(output.text.encode()) == 65536
    assert peak < 1024 * 1024


def test_invalid_utf8_and_partial_character_remain_within_contract(tmp_path):
    code = "import os; os.write(1,b'a' + bytes([0xff]) + '€'.encode()*3)"
    result = run_command([sys.executable, '-c', code], cwd=tmp_path, timeout=2, output_limit=4)
    result.stdout.validate()
    assert result.stdout.text == 'a'
    assert result.stdout.original_bytes == 11
    assert result.stdout.truncated


def test_chatty_command_timeout_preserves_bounded_capture(tmp_path):
    code = "import os\nwhile True: os.write(1,b'x'*4096)"
    with pytest.raises(subprocess.TimeoutExpired) as raised:
        run_command([sys.executable, '-c', code], cwd=tmp_path, timeout=0.2, output_limit=4096)
    output = raised.value.stdout_capture
    output.validate()
    assert len(output.text) == 4096
    assert output.original_bytes > 4096
    assert output.truncated


@pytest.mark.parametrize('timeout', [0, -1, float('nan'), float('inf'), 1e100, 10**1000, True, '1'])
def test_invalid_timeout_never_launches_process(tmp_path, monkeypatch, timeout):
    from atlas_execution_worker import process
    launches = []
    monkeypatch.setattr(process.subprocess, 'Popen', lambda *args, **kwargs: launches.append(args))
    with pytest.raises(ValueError, match='finite and positive'):
        run_command([sys.executable, '-c', 'pass'], cwd=tmp_path, timeout=timeout)
    assert launches == []
