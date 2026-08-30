from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.execution_permission_grant import contract
from app.execution_permission_grant.contract import (
    CONFIRMATION_TEXT,
    PERMISSION,
    ExecutionPermissionGrantAuthorityContextV1,
    ExecutionPermissionGrantCreateV1,
    ExecutionPermissionGrantRedactedErrorV1,
    ExecutionPermissionGrantValidationInputV1,
    StrictContractError,
    build_grant,
    derive_status,
    grant_fingerprint,
    parse_create_json,
)
from app.installation_readiness_review.contract import (
    create_installation_readiness_review,
)
from app.installation_readiness_review.test_contract import (
    CORRELATION_ID,
    OPERATOR,
)
from app.installation_readiness_review.test_contract import (
    _input as readiness_input,
)

GRANT_ID = "319e9180-02fe-442e-88fc-4adf6709546a"
RECORDED_AT = "2026-08-27T12:00:20Z"


def _readiness(tmp_path: Path, **changes):
    return create_installation_readiness_review(
        readiness_input(tmp_path, **changes), correlation_id=CORRELATION_ID
    )


def _validation(tmp_path: Path, **changes) -> ExecutionPermissionGrantValidationInputV1:
    response = changes.pop("readiness_response", _readiness(tmp_path))
    create = changes.pop(
        "create",
        ExecutionPermissionGrantCreateV1(
            readiness_review_id=response.review.review_id,
            readiness_review_fingerprint=response.review.review_fingerprint,
            review_observed_at=response.review.observed_at,
            confirmation_text=CONFIRMATION_TEXT,
        ),
    )
    values = {
        "operator_id": OPERATOR,
        "authority": ExecutionPermissionGrantAuthorityContextV1(
            authenticated_operator_id=OPERATOR,
            permission=PERMISSION,
            request_received_at=RECORDED_AT,
        ),
        "candidate_record_id": response.review.candidate_record_id,
        "create": create,
        "readiness_response": response,
        "idempotency_key": "grant-key-1",
    }
    values.update(changes)
    return ExecutionPermissionGrantValidationInputV1.model_validate(values)


def test_valid_grant_is_deterministic_immutable_and_non_authorizing(
    tmp_path: Path,
) -> None:
    first = build_grant(_validation(tmp_path), grant_id=GRANT_ID)
    second = build_grant(_validation(tmp_path), grant_id=GRANT_ID)
    assert first == second
    grant, idempotency, reservation = first
    assert grant.grant_fingerprint == grant_fingerprint(grant)
    assert grant.valid_until == "2026-08-27T12:00:46Z"
    assert idempotency.permanent and not idempotency.raw_key_persisted
    assert reservation.reservation_state == "permanent"
    assert reservation.idempotency_subject_reserved
    assert reservation.review_subject_reserved
    assert not reservation.releasable and not reservation.reusable
    false_fields = (
        "execution_admission_granted",
        "execution_authorized",
        "installation_allowed",
        "dispatch_allowed",
        "agent_invocation_allowed",
        "worker_allowed",
        "workflow_allowed",
        "provider_mutation_allowed",
        "repository_mutation_allowed",
        "in_guest_mutation_allowed",
        "deployment_allowed",
        "rollback_allowed",
        "retry_allowed",
        "resend_allowed",
        "docker_allowed",
        "podman_allowed",
        "shell_allowed",
        "process_allowed",
        "replay_allowed",
    )
    assert not any(getattr(grant, field) for field in false_fields)
    with pytest.raises(ValidationError):
        grant.record_state = "executed"  # type: ignore[misc]


def test_lifecycle_is_only_active_or_expired(tmp_path: Path) -> None:
    grant, _, _ = build_grant(_validation(tmp_path), grant_id=GRANT_ID)
    assert (
        derive_status(grant, observed_at="2026-08-27T12:00:45Z").lifecycle == "active"
    )
    assert derive_status(grant, observed_at=grant.valid_until).lifecycle == "expired"
    raw = derive_status(grant, observed_at=grant.valid_until).model_dump(mode="python")
    raw["lifecycle"] = "ready"
    with pytest.raises(ValidationError):
        contract.ExecutionPermissionGrantStatusV1.model_validate(raw)


def test_closed_unknown_duplicate_and_confirmation_rejection(tmp_path: Path) -> None:
    create = _validation(tmp_path).create
    assert parse_create_json(create.model_dump_json()) == create
    duplicate = create.model_dump_json()[:-1] + ',"confirmation_text":"duplicate"}'
    with pytest.raises(StrictContractError):
        parse_create_json(duplicate)
    raw = create.model_dump(mode="python")
    raw["unknown"] = True
    with pytest.raises(ValidationError):
        ExecutionPermissionGrantCreateV1.model_validate(raw)
    raw.pop("unknown")
    raw["confirmation_text"] = "I approve."
    with pytest.raises(ValidationError):
        ExecutionPermissionGrantCreateV1.model_validate(raw)


def test_fingerprint_owner_permission_and_time_fail_closed(tmp_path: Path) -> None:
    response = _readiness(tmp_path)
    raw = _validation(tmp_path).model_dump(mode="python")
    raw["create"]["readiness_review_fingerprint"]["value"] = "f" * 64
    with pytest.raises(ValidationError, match="binding"):
        ExecutionPermissionGrantValidationInputV1.model_validate(raw)

    raw = _validation(tmp_path).model_dump(mode="python")
    raw["authority"]["authenticated_operator_id"] = "operator-b"
    with pytest.raises(ValidationError, match="ownership"):
        ExecutionPermissionGrantValidationInputV1.model_validate(raw)

    raw = _validation(tmp_path).model_dump(mode="python")
    raw["authority"]["permission"] = "installation.read"
    with pytest.raises(ValidationError):
        ExecutionPermissionGrantValidationInputV1.model_validate(raw)

    stale = ExecutionPermissionGrantAuthorityContextV1(
        authenticated_operator_id=OPERATOR,
        permission=PERMISSION,
        request_received_at="2026-08-27T12:00:47Z",
    )
    with pytest.raises(ValidationError, match="stale"):
        _validation(tmp_path, authority=stale, readiness_response=response)


def test_expired_evidence_and_home_assistant_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="not readiness gated"):
        _validation(tmp_path, home_assistant=True)
    blocked = _readiness(
        tmp_path, home_assistant=True, installation_capability_supported=False
    )
    assert blocked.review.blockers == ("installation_capability_unsupported",)
    with pytest.raises(ValidationError, match="not readiness gated"):
        _validation(tmp_path, readiness_response=blocked)


def test_grant_linkage_and_fingerprint_tampering_is_rejected(tmp_path: Path) -> None:
    grant, _, _ = build_grant(_validation(tmp_path), grant_id=GRANT_ID)
    raw = grant.model_dump(mode="python")
    raw["grant_fingerprint"]["value"] = "a" * 64
    with pytest.raises(ValidationError, match="grant fingerprint"):
        contract.ExecutionPermissionGrantV1.model_validate(raw)
    raw = grant.linkage.model_dump(mode="python")
    raw["v034_review_fingerprint"]["value"] = "b" * 64
    with pytest.raises(ValidationError, match="linkage fingerprint"):
        contract.ExecutionPermissionGrantLinkageV1.model_validate(raw)


def test_redacted_error_has_no_secret_or_object_values() -> None:
    error = ExecutionPermissionGrantRedactedErrorV1(
        error_code="not_found", correlation_id="grant-error-1"
    )
    rendered = error.model_dump_json()
    assert error.redacted and not error.retryable
    for forbidden in (
        "candidate_record_id",
        "operator_id",
        "credential",
        "token",
        "exception",
    ):
        assert forbidden not in rendered


def test_contract_has_no_forbidden_runtime_imports_or_calls() -> None:
    tree = ast.parse(Path(contract.__file__).read_text())
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imports.isdisjoint(
        {"subprocess", "docker", "requests", "httpx", "socket", "sqlalchemy"}
    )
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert calls.isdisjoint({"open", "exec", "eval", "system", "run", "Popen"})
