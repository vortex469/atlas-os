"""Bounded Linux process lifetime and output for Agent-owned Git commands."""

from __future__ import annotations

import math
import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

READ_TIMEOUT_SECONDS = 10.0
COMMIT_TIMEOUT_SECONDS = 60.0
MAX_STDOUT_BYTES = 1_048_576
MAX_STDERR_BYTES = 65_536
_READ_BYTES = 65_536
_CLEANUP_SECONDS = 1.0


class GitProcessError(Exception):
    """Controlled failure containing no arguments, output or inherited secrets."""


@dataclass(frozen=True, slots=True)
class GitProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    stdout_digest: str | None = None


class GitProcessBudget:
    """One monotonic deadline shared by commands in a commit attempt."""

    def __init__(self, timeout: float) -> None:
        if (
            type(timeout) not in (int, float)
            or not 0 < timeout <= COMMIT_TIMEOUT_SECONDS
            or not math.isfinite(timeout)
        ):
            raise ValueError("Git budget must be finite, positive and at most sixty seconds")
        self.deadline = time.monotonic() + timeout

    def remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise GitProcessError("git_deadline_exceeded")
        return remaining


class GitProcessRunner:
    """Drain both pipes and clean up the command's owned process group."""

    def run(
        self,
        arguments: tuple[str, ...],
        *,
        cwd: Path,
        budget: GitProcessBudget | None = None,
        digest_stdout: bool = False,
        stdout_limit: int = MAX_STDOUT_BYTES,
        stderr_limit: int = MAX_STDERR_BYTES,
    ) -> GitProcessResult:
        if (
            type(stdout_limit) is not int or not 0 < stdout_limit <= MAX_STDOUT_BYTES
            or type(stderr_limit) is not int or not 0 < stderr_limit <= MAX_STDERR_BYTES
        ):
            raise ValueError("Invalid Git output bound")
        budget = budget if budget is not None else GitProcessBudget(READ_TIMEOUT_SECONDS)
        budget.remaining()
        try:
            process = subprocess.Popen(
                ["git", *arguments], cwd=cwd, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                bufsize=0, start_new_session=True,
            )
        except OSError:
            raise GitProcessError("git_launch_failed") from None

        stdout, stderr = bytearray(), bytearray()
        digest = sha256() if digest_stdout else None
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, "stdout")
                selector.register(process.stderr, selectors.EVENT_READ, "stderr")
                while selector.get_map():
                    for key, _ in selector.select(budget.remaining()):
                        chunk = os.read(key.fd, _READ_BYTES)
                        if not chunk:
                            selector.unregister(key.fileobj)
                        elif key.data == "stdout" and digest is not None:
                            digest.update(chunk)
                        else:
                            capture = stdout if key.data == "stdout" else stderr
                            limit = stdout_limit if key.data == "stdout" else stderr_limit
                            if len(capture) + len(chunk) > limit:
                                raise GitProcessError("git_output_limit_exceeded")
                            capture.extend(chunk)
                try:
                    process.wait(timeout=budget.remaining())
                except subprocess.TimeoutExpired:
                    raise GitProcessError("git_deadline_exceeded") from None
            return GitProcessResult(
                returncode=process.returncode,
                stdout=bytes(stdout), stderr=bytes(stderr),
                stdout_digest=digest.hexdigest() if digest is not None else None,
            )
        except OSError:
            raise GitProcessError("git_io_failed") from None
        finally:
            self._cleanup(process)

    @staticmethod
    def _cleanup(process: subprocess.Popen) -> None:
        try:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            finally:
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
            process.wait(timeout=_CLEANUP_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            raise GitProcessError("git_cleanup_failed") from None
