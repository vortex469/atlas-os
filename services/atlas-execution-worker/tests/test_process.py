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
    except FileNotFoundError:
        return False


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
        assert result.stdout == 'complete\n'
        pid = int(marker.read_text())
        deadline = time.monotonic() + 1
        while alive(pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not alive(pid)
    finally:
        if marker.exists() and alive(int(marker.read_text())):
            os.kill(int(marker.read_text()), signal.SIGKILL)
