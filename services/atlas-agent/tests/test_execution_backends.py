"""Tests for the S3 execution backend seam and worker adapter."""

from pathlib import Path

import pytest

from app.execution.backends import (
    LocalExecutionBackend,
    WorkerExecutionBackend,
    WorkerExecutionContext,
)
from app.execution.exceptions import ExecutionValidationError
from app.execution.models import ExecutionRequest, ExecutionStatus, RunnerOutcome
from app.execution.worker_client import WorkerTransportError
from app.execution.worker_contracts import (
    BoundedOutput,
    WorkerAttestation,
    WorkerExecutionRequest,
    WorkerExecutionResult,
    WorkerExecutionStatus,
    WorkerFailureCode,
)
from app.planning.models import ImplementationPlan


class FakeRunner:
    def __init__(self, outcome: RunnerOutcome) -> None:
        self.outcome = outcome
        self.calls = 0

    def run(self, **kwargs: object) -> RunnerOutcome:
        self.calls += 1
        return self.outcome


class FakeWorkerClient:
    def __init__(self, response: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.requests = []

    def submit(self, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def make_request() -> ExecutionRequest:
    plan = ImplementationPlan(
        checkpoint_id="checkpoint-1",
        title="Update Compose",
        goal="Apply approved mutation",
        repository_root=Path("/workspace/repository"),
        branch="feature/worker",
        head_commit="a" * 40,
        scope_items=("compose",),
        affected_files=(Path("compose.production.yaml"),),
        required_tests=(),
        risks=(),
    )
    return ExecutionRequest(
        identifier="execution-1",
        plan=plan,
        argv=("codex", "exec", "approved prompt"),
        working_directory=plan.repository_root,
    )


def make_context() -> WorkerExecutionContext:
    return WorkerExecutionContext(
        workflow_id="workflow-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-1",
        plan_id="plan-1",
        plan_fingerprint="plan-fingerprint-1",
        expected_repository_head="a" * 40,
        repository_token="repository-token-1",
        allowed_affected_files=("compose.production.yaml",),
        repository_branch="feature/worker",
    )


def worker_request_for(request: ExecutionRequest, context: WorkerExecutionContext) -> WorkerExecutionRequest:
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


def worker_result(request: WorkerExecutionRequest, *, failure_code=None, status=WorkerExecutionStatus.BLOCKED):  # type: ignore[no-untyped-def]
    result = WorkerExecutionResult(
        schema_version=1,
        execution_request_id=request.execution_request_id,
        status=status,
        return_code=0 if status is WorkerExecutionStatus.SUCCEEDED else None,
        stdout=BoundedOutput("worker stdout"),
        stderr=BoundedOutput("worker stderr"),
        changed_files=(),
        patch_digest=None,
        patch_size_bytes=None,
        patch_truncated=False,
        duration_seconds=0.5,
        failure_code=failure_code,
        workspace_head="a" * 40 if status is WorkerExecutionStatus.SUCCEEDED else None,
        worker_attestation=WorkerAttestation(
            runtime_uid=10001,
            readonly_rootfs=True,
            no_new_privileges=True,
            effective_capabilities="0000000000000000",
            sandbox_profile="atlas-worker",
        ),
    )
    return {"state": "completed", "result": result.to_dict()}


def test_local_backend_preserves_runner_success() -> None:
    runner = FakeRunner(RunnerOutcome(0, "out", "err"))
    result = LocalExecutionBackend(runner).execute(make_request())

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.stdout == "out"
    assert runner.calls == 1


def test_worker_backend_preserves_exact_request_evidence() -> None:
    client = FakeWorkerClient()
    backend = WorkerExecutionBackend(client)
    request = make_request()
    worker_request = worker_request_for(request, make_context())
    client.response = worker_result(worker_request, failure_code=WorkerFailureCode.WORKER_UNAVAILABLE)
    result = backend.execute(request, context=make_context())

    sent = client.requests[0]
    assert sent.argv == request.argv
    assert sent.expected_repository_head == "a" * 40
    assert sent.allowed_affected_files == ("compose.production.yaml",)
    assert result.status is ExecutionStatus.LAUNCH_FAILED
    assert result.error == "worker_unavailable"


@pytest.mark.parametrize("failure", list(WorkerFailureCode))
def test_worker_failure_codes_map_deterministically(failure: WorkerFailureCode) -> None:
    request = make_request()
    context = make_context()
    client = FakeWorkerClient()
    backend = WorkerExecutionBackend(client)
    worker_request = worker_request_for(request, context)
    status = (
        WorkerExecutionStatus.UNKNOWN
        if failure is WorkerFailureCode.WORKER_CRASH
        else WorkerExecutionStatus.FAILED
        if failure is WorkerFailureCode.TIMEOUT
        else WorkerExecutionStatus.BLOCKED
    )
    client.response = worker_result(worker_request, failure_code=failure, status=status)
    result = backend.execute(request, context=context)
    assert result.error == failure.value
    assert result.status is (ExecutionStatus.TIMED_OUT if failure is WorkerFailureCode.TIMEOUT else ExecutionStatus.LAUNCH_FAILED if failure in {WorkerFailureCode.WORKER_UNAVAILABLE, WorkerFailureCode.WORKER_CRASH} else ExecutionStatus.FAILED)


def test_worker_transport_failure_has_no_local_fallback() -> None:
    request = make_request()
    runner = FakeRunner(RunnerOutcome(0, "must not run", ""))
    backend = WorkerExecutionBackend(FakeWorkerClient(error=WorkerTransportError("offline")))

    result = backend.execute(request, context=make_context())

    assert result.error.startswith("worker_unavailable:")
    assert runner.calls == 0


def test_worker_requires_explicit_context() -> None:
    with pytest.raises(ExecutionValidationError):
        WorkerExecutionBackend(FakeWorkerClient()).execute(make_request())
