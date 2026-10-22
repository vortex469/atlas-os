"""Execution backend seam for local and future isolated execution."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
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
from app.execution.worker_client import TcpWorkerClient, WorkerTransportError
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

    def __init__(
        self,
        client: TcpWorkerClient,
        *,
        repository_token: str = "atlas-repository",
    ) -> None:
        self._client = client
        if not repository_token or "/" in repository_token or "\\" in repository_token:
            raise ValueError("repository token must be an opaque configured value")
        self.repository_token = repository_token

    @property
    def uses_worker(self) -> bool:
        return True

    def execute(
        self,
        request: ExecutionRequest,
        *,
        context: WorkerExecutionContext | None = None,
    ) -> ExecutionResult:
        worker_request = self.prepare(request, context=context)
        try:
            response = self._client.submit(worker_request)
        except WorkerTransportError:
            return self._unknown(request)
        return self._decode_response(request, worker_request, response)

    def prepare(
        self,
        request: ExecutionRequest,
        *,
        context: WorkerExecutionContext | None,
    ) -> WorkerExecutionRequest:
        """Build the exact request for durable recording before submission."""
        if context is None:
            raise ExecutionValidationError("Worker execution context is required")
        self._validate_context(request, context)
        return WorkerExecutionRequest.build(
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

    def reconcile(
        self,
        request: ExecutionRequest,
        *,
        context: WorkerExecutionContext,
    ) -> ExecutionResult:
        """Look up the original request once; never submit or retry execution."""
        worker_request = self.prepare(request, context=context)
        try:
            response = self._client.get_result(worker_request.execution_request_id)
        except WorkerTransportError:
            return self._unknown(request)
        return self._decode_response(request, worker_request, response)

    def _decode_response(
        self,
        request: ExecutionRequest,
        worker_request: WorkerExecutionRequest,
        response: object,
    ) -> ExecutionResult:
        if not isinstance(response, dict):
            return self._unknown(request)
        if response.get("request_digest") != worker_request.request_digest:
            return self._unknown(request)
        if response.get("state") not in {"completed", "failed_terminal"}:
            return self._unknown(request)
        raw_result = response.get("result")
        if not isinstance(raw_result, dict):
            return self._unknown(request)
        try:
            result = WorkerExecutionResult.from_dict(raw_result)
            result.validate(worker_request)
            if response["state"] == "failed_terminal" and result.status is WorkerExecutionStatus.SUCCEEDED:
                raise ValueError("worker terminal state mismatch")
            if result.base_repository_head not in (None, worker_request.expected_repository_head):
                raise ValueError("worker result base repository head mismatch")
            if result.changed_files and not set(result.changed_files).issubset(
                set(worker_request.allowed_affected_files)
            ) and result.failure_code is None:
                raise ValueError("worker result changed files exceed approved scope")
        except (TypeError, ValueError, KeyError):
            return self._unknown(request)
        return self._map_result(request, result)

    def _unknown(self, request: ExecutionRequest) -> ExecutionResult:
        return self._failure(
            request, ExecutionStatus.UNKNOWN, "worker_outcome_unknown",
            "Worker outcome is unknown. Check the original request; do not resubmit.",
        )

    def _validate_context(
        self, request: ExecutionRequest, context: WorkerExecutionContext
    ) -> None:
        """Reject subject substitution before any worker contact occurs."""
        if context.repository_token != self.repository_token:
            raise ExecutionValidationError("Worker repository token mismatch")
        if (
            context.expected_repository_head != request.plan.head_commit
            or context.repository_branch != request.plan.branch
        ):
            raise ExecutionValidationError("Worker repository subject mismatch")
        if set(context.allowed_affected_files) != {
            path.as_posix() for path in request.plan.affected_files
        }:
            raise ExecutionValidationError("Worker affected files mismatch")
        root = request.plan.repository_root.resolve(strict=False)
        working_directory = request.working_directory
        if not working_directory.is_absolute():
            working_directory = root / working_directory
        working_directory = working_directory.resolve(strict=False)
        if (
            not working_directory.is_relative_to(root)
            or (root / Path(context.working_directory)).resolve(strict=False)
            != working_directory
        ):
            raise ExecutionValidationError("Worker working directory mismatch")
        if (
            request.timeout_seconds is not None
            and context.timeout_seconds != request.timeout_seconds
        ):
            raise ExecutionValidationError("Worker timeout mismatch")
        if request.environment:
            raise ExecutionValidationError("Worker environment overrides are unsupported")

    @staticmethod
    def _map_result(
        request: ExecutionRequest,
        result: WorkerExecutionResult,
    ) -> ExecutionResult:
        if result.status is WorkerExecutionStatus.SUCCEEDED:
            status = ExecutionStatus.SUCCEEDED
        elif result.status is WorkerExecutionStatus.UNKNOWN:
            status = ExecutionStatus.UNKNOWN
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
            worker_result=result,
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
