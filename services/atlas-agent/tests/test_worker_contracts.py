"""Tests for the versioned Agent-to-execution-worker contracts."""

from dataclasses import replace

import pytest
from app.execution.worker_contracts import (
    CODEX_WORKSPACE_EXEC_ARGV_PREFIX,
    BoundedOutput,
    WorkerAttestation,
    WorkerExecutionRequest,
    WorkerExecutionResult,
    WorkerExecutionStatus,
    WorkerFailureCode,
    validate_worker_execution_result,
)

HEAD = "a" * 40


def make_request(**overrides: object) -> WorkerExecutionRequest:
    values: dict[str, object] = {
        "execution_request_id": "execution-1",
        "workflow_id": "workflow-1",
        "candidate_id": "candidate-1",
        "candidate_fingerprint": "candidate-fingerprint-1",
        "plan_id": "plan-1",
        "plan_fingerprint": "plan-fingerprint-1",
        "execution_intent": "update-compose-stack",
        "repository_token": "repository-token-1",
        "expected_repository_head": HEAD,
        "repository_branch": "feature/worker",
        "argv": (*CODEX_WORKSPACE_EXEC_ARGV_PREFIX, "update compose image"),
        "working_directory": ".",
        "allowed_affected_files": ("compose.production.yaml",),
        "timeout_seconds": 120,
    }
    values.update(overrides)
    return WorkerExecutionRequest.build(**values)


def attestation() -> WorkerAttestation:
    return WorkerAttestation(
        runtime_uid=10001,
        readonly_rootfs=True,
        no_new_privileges=True,
        effective_capabilities="0000000000000000",
        sandbox_profile="atlas-execution-worker",
    )


def make_result(request: WorkerExecutionRequest, **overrides: object) -> WorkerExecutionResult:
    values: dict[str, object] = {
        "schema_version": 1,
        "execution_request_id": request.execution_request_id,
        "status": WorkerExecutionStatus.SUCCEEDED,
        "return_code": 0,
        "stdout": BoundedOutput("ok"),
        "stderr": BoundedOutput(""),
        "changed_files": ("compose.production.yaml",),
        "patch_digest": "sha256:" + "b" * 64,
        "patch_size_bytes": 12,
        "patch_truncated": False,
        "duration_seconds": 1.25,
        "failure_code": None,
        "workspace_head": HEAD,
        "worker_attestation": attestation(),
    }
    values.update(overrides)
    return WorkerExecutionResult(**values)


def test_request_canonicalizes_unordered_files_and_digest_is_deterministic() -> None:
    first = make_request(allowed_affected_files=("z.yaml", "a.yaml"))
    second = make_request(allowed_affected_files=("a.yaml", "z.yaml"))

    assert first.allowed_affected_files == ("a.yaml", "z.yaml")
    assert first.request_digest == second.request_digest
    assert first.request_digest.startswith("execution-request-digest-v1:")


def test_security_sensitive_request_changes_change_digest() -> None:
    request = make_request()
    assert (
        make_request(argv=(*CODEX_WORKSPACE_EXEC_ARGV_PREFIX, "other")).request_digest
        != request.request_digest
    )
    assert make_request(expected_repository_head="b" * 40).request_digest != request.request_digest
    assert make_request(plan_fingerprint="other-plan").request_digest != request.request_digest
    assert make_request(timeout_seconds=121).request_digest != request.request_digest


def test_request_json_round_trip_preserves_security_semantics() -> None:
    request = make_request()
    restored = WorkerExecutionRequest.from_json(request.to_json())

    assert restored == request
    restored.validate()


def test_request_rejects_unknown_fields_and_tampered_digest() -> None:
    payload = make_request().to_dict()
    payload["unexpected"] = True
    with pytest.raises(ValueError, match="unknown"):
        WorkerExecutionRequest.from_dict(payload)

    payload = make_request().to_dict()
    payload["request_digest"] = "execution-request-digest-v1:" + "0" * 64
    with pytest.raises(ValueError, match="mismatch"):
        WorkerExecutionRequest.from_dict(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("execution_intent", "restart-service"),
        ("schema_version", 2),
        ("expected_repository_head", "not-a-head"),
        ("repository_token", "/host/repository"),
        ("working_directory", "/tmp/repository"),
        ("working_directory", "../repository"),
        ("allowed_affected_files", ("../secret",)),
        ("allowed_affected_files", ("/etc/passwd",)),
        ("allowed_affected_files", ("compose.yaml", "compose.yaml")),
        ("argv", ("", "exec", "prompt")),
        ("argv", ("codex", "run", "prompt")),
        ("timeout_seconds", 0),
    ],
)
def test_request_rejects_unsafe_or_unsupported_fields(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        make_request(**{field: value})


def test_result_success_validates_against_request_and_round_trips() -> None:
    request = make_request()
    result = make_result(request)

    validate_worker_execution_result(result, request)
    assert WorkerExecutionResult.from_json(result.to_json()) == result


@pytest.mark.parametrize(
    "failure_code,status",
    [
        (code, WorkerExecutionStatus.BLOCKED)
        for code in (
            WorkerFailureCode.STALE_REPOSITORY,
            WorkerFailureCode.INVALID_REQUEST,
            WorkerFailureCode.INVALID_ARGV,
            WorkerFailureCode.SANDBOX_UNAVAILABLE,
            WorkerFailureCode.AUTH_UNAVAILABLE,
            WorkerFailureCode.OUT_OF_SCOPE_CHANGES,
            WorkerFailureCode.NO_COMMITTABLE_CHANGES,
            WorkerFailureCode.DUPLICATE_REQUEST,
            WorkerFailureCode.WORKER_UNAVAILABLE,
        )
    ]
    + [
        (WorkerFailureCode.TIMEOUT, WorkerExecutionStatus.FAILED),
        (WorkerFailureCode.CODEX_FAILED, WorkerExecutionStatus.FAILED),
        (WorkerFailureCode.WORKER_CRASH, WorkerExecutionStatus.UNKNOWN),
    ],
)
def test_failure_codes_have_explicit_status_and_round_trip(
    failure_code: WorkerFailureCode, status: WorkerExecutionStatus
) -> None:
    request = make_request()
    result = make_result(
        request,
        status=status,
        return_code=None,
        changed_files=(),
        failure_code=failure_code,
    )

    result.validate(request)
    assert WorkerExecutionResult.from_json(result.to_json()) == result


def test_result_rejects_mismatched_request_and_out_of_scope_files() -> None:
    request = make_request()
    with pytest.raises(ValueError, match="request ID"):
        make_result(request, execution_request_id="other-request").validate(request)
    with pytest.raises(ValueError, match="outside"):
        make_result(request, changed_files=("other.txt",)).validate(request)


def test_result_rejects_invalid_attestation_and_truncation_metadata() -> None:
    request = make_request()
    with pytest.raises(ValueError, match="confined"):
        make_result(
            request,
            worker_attestation=replace(attestation(), sandbox_profile="unconfined"),
        ).validate(request)
    with pytest.raises(ValueError, match="truncated"):
        make_result(
            request,
            stdout=BoundedOutput("partial", truncated=True, original_bytes=7),
        ).validate(request)
