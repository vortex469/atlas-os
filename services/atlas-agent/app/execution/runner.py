"""Synchronous subprocess execution."""

import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from app.execution.models import RunnerOutcome


class CommandRunner(Protocol):
    """Runner contract used by the execution engine."""

    def run(
        self,
        *,
        argv: tuple[str, ...],
        cwd: Path,
        environment: Mapping[str, str],
        timeout_seconds: float | None,
    ) -> RunnerOutcome:
        """Execute one command and return its outcome."""


class SubprocessRunner:
    """Run one command synchronously without a shell."""

    def run(
        self,
        *,
        argv: tuple[str, ...],
        cwd: Path,
        environment: Mapping[str, str],
        timeout_seconds: float | None,
    ) -> RunnerOutcome:
        """Execute one subprocess and capture its output."""

        try:
            completed = subprocess.run(
                argv,
                cwd=cwd,
                env=dict(environment),
                text=True,
                capture_output=True,
                check=False,
                shell=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            return RunnerOutcome(
                return_code=None,
                stdout=self._output_text(error.stdout),
                stderr=self._output_text(error.stderr),
                timed_out=True,
            )
        except OSError as error:
            return RunnerOutcome(
                return_code=None,
                stdout="",
                stderr="",
                launch_error=str(error),
            )

        return RunnerOutcome(
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    @staticmethod
    def _output_text(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode(errors="replace")
        return value
