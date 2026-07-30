"""Approved implementation-plan execution."""

import os
import time
from collections.abc import Callable

from app.execution.exceptions import ExecutionValidationError
from app.execution.models import (
    AllowedCommand,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    PolicyViolation,
    RunnerOutcome,
)
from app.execution.policy import ToolPolicy
from app.execution.runner import CommandRunner


class ExecutionEngine:
    """Validate and execute approved Codex requests."""

    def __init__(
        self,
        runner: CommandRunner,
        clock: Callable[[], float] = time.monotonic,
        policy: ToolPolicy | None = None,
    ) -> None:
        self._runner = runner
        self._clock = clock
        self._policy = policy or ToolPolicy()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute one validated request and return its final result."""

        decision = self._policy.validate(request)
        if isinstance(decision, PolicyViolation):
            raise ExecutionValidationError(decision.message)

        normalized: AllowedCommand = decision
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
