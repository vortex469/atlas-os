"""Execution backend seam for local and future isolated execution."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

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
from app.execution.worker_client import UnixSocketWorkerClient, WorkerTransportError
from app.execution.worker_contracts import (
    WorkerExecutionRequest,
    WorkerExecutionResult,
    WorkerExecutionStatus,
    WorkerFailureCode,
)


class ExecutionBackend(Protocol):
    """Synchronous execution backend selected by the Agent."""

    def execute(
        self,
        request: ExecutionRequest,
        *,
        context: WorkerExecutionContext | None = None,
    ) -> ExecutionResult:
        """Execute one already-approved request."""


@dataclass(frozen=True, slots=True)
class WorkerExecutionContext:
    """Explicit candidate evidence required to build a worker request."""

    workflow_id: str
    candidate_id: str
    candidate_fingerprint: str
    plan_id: str
    plan_fingerprint: str
    expected_repository_head: str
    repository_token: str
    allowed_affected_files: tuple[str, ...]
    execution_intent: str = "update-compose-stack"
    repository_branch: str | None = None
    working_directory: str = "."
    timeout_seconds: float = 120.0


class LocalExecutionBackend:
    """Preserve the existing local subprocess execution semantics."""

    def __init__(
        self,
        runner: CommandRunner,
        clock: Callable[[], float] = time.monotonic,
        policy: ToolPolicy | None = None,
    ) -> None:
        self._runner = runner
        self._clock = clock
        self._policy = policy or ToolPolicy()

    def execute(
        self,
        request: ExecutionRequest,
        *,
        context: WorkerExecutionContext | None = None,
    ) -> ExecutionResult:
        del context
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
    def _classify(outcome: RunnerOutcome) -> tuple[ExecutionStatus, str | None]:
        if outcome.timed_out:
            return ExecutionStatus.TIMED_OUT, "Execution timed out"
        if outcome.launch_error is not None:
            return ExecutionStatus.LAUNCH_FAILED, outcome.launch_error
        if outcome.return_code == 0:
            return ExecutionStatus.SUCCEEDED, None
        return ExecutionStatus.FAILED, None


class WorkerExecutionBackend:
    """Submit approved requests to the isolated worker without fallback."""

    def __init__(self, client: UnixSocketWorkerClient) -> None:
        self._client = client

    def execute(
        self,
        request: ExecutionRequest,
        *,
        context: WorkerExecutionContext | None = None,
    ) -> ExecutionResult:
        if context is None:
            raise ExecutionValidationError("Worker execution context is required")
        worker_request = WorkerExecutionRequest.build(
            execution_request_id=request.identifier,
            workflow_id=context.workflow_id,
            candidate_id=context.candidate_id,
            candidate_fingerprint=context.candidate_fingerprint,
            plan_id=context.plan_id,
            plan_fingerprint=context.plan_fingerprint,
            execution_intent=context.execution_intent,
            repository_token=context.repository_token,
            expected_repository_head=context.expected_repository_head,
            repository_branch=context.repository_branch,
            argv=request.argv,
            working_directory=context.working_directory,
            allowed_affected_files=context.allowed_affected_files,
            timeout_seconds=context.timeout_seconds,
        )
        try:
            response = self._client.submit(worker_request)
        except WorkerTransportError as exc:
            return self._failure(request, ExecutionStatus.LAUNCH_FAILED, "worker_unavailable", str(exc))
        raw_result = response.get("result")
        if not isinstance(raw_result, dict):
            return self._failure(request, ExecutionStatus.LAUNCH_FAILED, "invalid_result", "Worker result missing")
        try:
            result = WorkerExecutionResult.from_dict(raw_result)
            result.validate(worker_request)
        except (TypeError, ValueError, KeyError) as exc:
            return self._failure(request, ExecutionStatus.LAUNCH_FAILED, "invalid_result", str(exc))
        return self._map_result(request, result)

    @staticmethod
    def _map_result(
        request: ExecutionRequest,
        result: WorkerExecutionResult,
    ) -> ExecutionResult:
        if result.status is WorkerExecutionStatus.SUCCEEDED:
            status = ExecutionStatus.SUCCEEDED
        elif result.failure_code is WorkerFailureCode.TIMEOUT:
            status = ExecutionStatus.TIMED_OUT
        elif result.failure_code in {
            WorkerFailureCode.WORKER_UNAVAILABLE,
            WorkerFailureCode.WORKER_CRASH,
        }:
            status = ExecutionStatus.LAUNCH_FAILED
        else:
            status = ExecutionStatus.FAILED
        error = result.failure_code.value if result.failure_code is not None else None
        return ExecutionResult(
            request_id=request.identifier,
            checkpoint_id=request.plan.checkpoint_id,
            argv=request.argv,
            working_directory=request.working_directory,
            status=status,
            return_code=result.return_code,
            stdout=result.stdout.text,
            stderr=result.stderr.text,
            duration_seconds=result.duration_seconds,
            error=error,
        )

    @staticmethod
    def _failure(
        request: ExecutionRequest,
        status: ExecutionStatus,
        code: str,
        message: str,
    ) -> ExecutionResult:
        return ExecutionResult(
            request_id=request.identifier,
            checkpoint_id=request.plan.checkpoint_id,
            argv=request.argv,
            working_directory=request.working_directory,
            status=status,
            return_code=None,
            stdout="",
            stderr="",
            duration_seconds=0,
            error=f"{code}: {message}",
        )
