"""Process-group lifetime for one bounded worker command on Linux."""
from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path


def _kill_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_command(argv: list[str], *, cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    """Stop the owned process group before returning or cleaning its workspace.

    A fresh session prevents the worker/relay from belonging to the command's
    group. This covers inherited children, not processes deliberately escaping
    that session; outer sandbox/container isolation remains required.
    """
    process = subprocess.Popen(
        argv, cwd=cwd, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    try:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            _kill_group(process)
            try:
                stdout, stderr = process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                # Do not hang on an escaped process retaining a pipe. No output
                # collected after the approved deadline can authorize a patch.
                stdout, stderr = error.stdout, error.stderr
            raise subprocess.TimeoutExpired(argv, timeout, output=stdout, stderr=stderr) from None
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    finally:
        _kill_group(process)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
        process.wait(timeout=1)
