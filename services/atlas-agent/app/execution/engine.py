"""Approved implementation-plan execution."""

import os
import re
import time
from collections.abc import Callable
from pathlib import Path

from app.execution.exceptions import ExecutionValidationError
from app.execution.models import (
    EnvironmentVariable,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    RunnerOutcome,
)
from app.execution.runner import CommandRunner

_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class ExecutionEngine:
    """Validate and execute approved Codex requests."""

    def __init__(
        self,
        runner: CommandRunner,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._runner = runner
        self._clock = clock

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute one validated request and return its final result."""

        normalized = self._normalize_request(request)
        environment = dict(os.environ)

        for variable in normalized.environment:
            environment[variable.name] = variable.value

        started_at = self._clock()

        outcome = self._runner.run(
            argv=normalized.argv,
            cwd=normalized.working_directory,
            environment=environment,
            timeout_seconds=normalized.timeout_seconds,
        )

        duration = max(0.0, self._clock() - started_at)
        status, error = self._classify(outcome)

        return ExecutionResult(
            request_id=normalized.identifier,
            checkpoint_id=normalized.plan.checkpoint_id,
            argv=normalized.argv,
            working_directory=normalized.working_directory,
            status=status,
            return_code=outcome.return_code,
            stdout=outcome.stdout,
            stderr=outcome.stderr,
            duration_seconds=duration,
            error=error,
        )

    def _normalize_request(
        self,
        request: ExecutionRequest,
    ) -> ExecutionRequest:
        identifier = request.identifier.strip()

        if not identifier:
            raise ExecutionValidationError(
                "Execution request identifier must not be blank"
            )

        if not request.argv:
            raise ExecutionValidationError("Execution argv must not be empty")

        for index, argument in enumerate(request.argv):
            if not argument.strip():
                raise ExecutionValidationError(
                    f"Execution argv item {index} must not be blank"
                )

        executable = request.argv[0]

        if Path(executable).is_absolute():
            raise ExecutionValidationError(
                "Execution executable must not be an absolute path"
            )

        if Path(executable).name != executable:
            raise ExecutionValidationError(
                "Execution executable must not contain path components"
            )

        if executable != "codex":
            raise ExecutionValidationError("Execution executable must be codex")

        if request.timeout_seconds is not None and request.timeout_seconds <= 0:
            raise ExecutionValidationError("Execution timeout must be positive")

        repository_root = request.plan.repository_root.resolve(strict=False)

        if request.working_directory.is_absolute():
            working_directory = request.working_directory.resolve(strict=False)
        else:
            working_directory = (repository_root / request.working_directory).resolve(
                strict=False
            )

        if not working_directory.is_relative_to(repository_root):
            raise ExecutionValidationError(
                "Execution working directory must be inside the repository"
            )

        environment = self._normalize_environment(request.environment)

        return ExecutionRequest(
            identifier=identifier,
            plan=request.plan,
            argv=request.argv,
            working_directory=working_directory,
            timeout_seconds=request.timeout_seconds,
            environment=environment,
        )

    @staticmethod
    def _normalize_environment(
        variables: tuple[EnvironmentVariable, ...],
    ) -> tuple[EnvironmentVariable, ...]:
        normalized: list[EnvironmentVariable] = []
        names: set[str] = set()

        for variable in variables:
            name = variable.name.strip()

            if not name:
                raise ExecutionValidationError(
                    "Environment variable name must not be blank"
                )

            if _ENVIRONMENT_NAME.fullmatch(name) is None:
                raise ExecutionValidationError(
                    f"Invalid environment variable name: {name}"
                )

            if name in names:
                raise ExecutionValidationError(
                    f"Duplicate environment variable name: {name}"
                )

            names.add(name)
            normalized.append(
                EnvironmentVariable(
                    name=name,
                    value=variable.value,
                )
            )

        return tuple(normalized)

    @staticmethod
    def _classify(
        outcome: RunnerOutcome,
    ) -> tuple[ExecutionStatus, str | None]:
        if outcome.timed_out:
            return ExecutionStatus.TIMED_OUT, "Execution timed out"

        if outcome.launch_error is not None:
            return ExecutionStatus.LAUNCH_FAILED, outcome.launch_error

        if outcome.return_code == 0:
            return ExecutionStatus.SUCCEEDED, None

        return ExecutionStatus.FAILED, None
