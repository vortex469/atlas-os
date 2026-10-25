"""Bounded output and process-group lifetime for one worker command on Linux."""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app.execution.worker_contracts import BoundedOutput

MAX_CAPTURE_BYTES = 1_048_576
READ_BYTES = 65_536


@dataclass(frozen=True, slots=True)
class CapturedCommand:
    returncode: int
    stdout: BoundedOutput
    stderr: BoundedOutput


class CommandTimeout(subprocess.TimeoutExpired):
    def __init__(self, argv, timeout, stdout: BoundedOutput, stderr: BoundedOutput):
        super().__init__(argv, timeout, output=stdout.text, stderr=stderr.text)
        self.stdout_capture = stdout
        self.stderr_capture = stderr


class _Capture:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.prefix = bytearray()
        self.total = 0

    def add(self, chunk: bytes) -> None:
        self.total += len(chunk)
        self.prefix.extend(chunk[:max(0, self.limit - len(self.prefix))])

    def output(self) -> BoundedOutput:
        # Discard incomplete/invalid UTF-8 rather than expanding replacement
        # characters past the byte bound. Mark any discarded bytes explicitly.
        text = self.prefix.decode('utf-8', errors='ignore')
        retained = len(text.encode('utf-8'))
        return BoundedOutput(text, self.total > retained, self.total)


def _kill_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _drain(selector: selectors.BaseSelector, deadline: float) -> bool:
    while selector.get_map():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        for key, _ in selector.select(remaining):
            chunk = os.read(key.fd, READ_BYTES)
            if chunk:
                key.data.add(chunk)
            else:
                selector.unregister(key.fileobj)
    return True


def run_command(
    argv: list[str], *, cwd: Path, timeout: float,
    output_limit: int = MAX_CAPTURE_BYTES,
    environment: Mapping[str, str] | None = None,
) -> CapturedCommand:
    """Drain both streams without retaining more than output_limit per stream.

    A fresh session keeps the worker outside the owned group. Inherited
    children are stopped before return or workspace cleanup. Deliberate session
    escape still requires outer sandbox/container isolation. Timeout byte counts
    describe bytes drained, not bytes an escaped process might later produce.
    """
    if type(output_limit) is not int or not 0 < output_limit <= MAX_CAPTURE_BYTES:
        raise ValueError('invalid output capture bound')
    deadline = time.monotonic() + timeout
    process = subprocess.Popen(
        argv, cwd=cwd, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        bufsize=0, start_new_session=True, env=environment,
    )
    stdout, stderr = _Capture(output_limit), _Capture(output_limit)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, stdout)
            selector.register(process.stderr, selectors.EVENT_READ, stderr)
            completed = _drain(selector, deadline)
            if completed:
                try:
                    process.wait(timeout=max(0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    completed = False
            if not completed:
                _kill_group(process)
                _drain(selector, time.monotonic() + 1)
                raise CommandTimeout(argv, timeout, stdout.output(), stderr.output())
        return CapturedCommand(process.returncode, stdout.output(), stderr.output())
    finally:
        _kill_group(process)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
        process.wait(timeout=1)
