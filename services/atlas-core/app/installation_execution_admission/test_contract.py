from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.execution_permission_grant.contract import (
    CONFIRMATION_TEXT,
    ExecutionPermissionGrantCreateV1,
    build_grant,
)
from app.execution_permission_grant.contract import (
    derive_status as derive_grant_status,
)
from app.execution_permission_grant.test_contract import GRANT_ID, _validation
from app.installation_execution_admission import contract
from app.installation_execution_admission.contract import (
    ADMISSION_BLOCKERS,
    PERMISSION,
    InstallationExecutionAdmissionAuthorityContextV1,
    InstallationExecutionAdmissionCreateV1,
    InstallationExecutionAdmissionRedactedErrorV1,
    InstallationExecutionAdmissionValidationInputV1,
    StrictContractError,
    admission_fingerprint,
    build_admission,
    derive_status,
    parse_create_json,
)

ADMISSION_ID = "fe54fe78-2259-47d6-89dc-da7b37d13b8c"
REQUESTED_AT = "2026-08-27T12:00:30Z"


def _grant(tmp_path: Path):
    grant, _, _ = build_grant(_validation(tmp_path), grant_id=GRANT_ID)
    return grant, derive_grant_status(grant, observed_at=REQUESTED_AT)


def _input(tmp_path: Path, **changes) -> InstallationExecutionAdmissionValidationInputV1:
    grant, status = changes.pop("grant_status", _grant(tmp_path))
    create = changes.pop(
        "create",
        InstallationExecutionAdmissionCreateV1(
            permission_grant_id=grant.grant_id,
            permission_grant_fingerprint=grant.grant_fingerprint,
            grant_valid_until=grant.valid_until,
        ),
    )
    values = {
        "operator_id": grant.operator_id,
        "authority": InstallationExecutionAdmissionAuthorityContextV1(
            authenticated_operator_id=grant.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": grant.candidate_record_id,
        "create": create,
        "permission_grant": grant,
        "permission_grant_status": status,
        "idempotency_key": "admission-key-1",
    }
    values.update(changes)
    return InstallationExecutionAdmissionValidationInputV1.model_validate(values)


def test_valid_admission_is_deterministic_immutable_and_admission_gated(
    tmp_path: Path,
) -> None:
    first = build_admission(_input(tmp_path), admission_id=ADMISSION_ID)
    second = build_admission(_input(tmp_path), admission_id=ADMISSION_ID)
    assert first == second
    admission, idempotency, reservation = first
    assert admission.admission_fingerprint == admission_fingerprint(admission)
    assert admission.readiness == "admission_gated"
    assert admission.blockers == ADMISSION_BLOCKERS
    assert admission.valid_until == "2026-08-27T12:00:46Z"
    assert idempotency.permanent and not idempotency.raw_key_persisted
    assert reservation.idempotency_subject_reserved
    assert reservation.grant_subject_reserved
    assert not reservation.releasable and not reservation.reusable
    false_fields = (
        "execution_start_allowed", "runner_binding_allowed",
        "execution_authorized", "installation_allowed", "dispatch_allowed",
        "retry_allowed", "resend_allowed", "agent_invocation_allowed",
        "worker_allowed", "workflow_allowed", "docker_allowed",
        "podman_allowed", "shell_allowed", "process_allowed",
        "provider_mutation_allowed", "repository_mutation_allowed",
        "in_guest_mutation_allowed", "deployment_allowed", "rollback_allowed",
        "replay_allowed",
    )
    assert not any(getattr(admission, field) for field in false_fields)
    assert not admission.runner_eligibility.runner_selected
    assert not admission.runner_eligibility.runner_invocation_allowed
    with pytest.raises(ValidationError):
        admission.record_state = "executed"  # type: ignore[misc]


def test_closed_unknown_duplicate_and_body_rejection(tmp_path: Path) -> None:
    create = _input(tmp_path).create
    assert parse_create_json(create.model_dump_json()) == create
    duplicate = create.model_dump_json()[:-1] + ',"schema":"duplicate"}'
    with pytest.raises(StrictContractError):
        parse_create_json(duplicate)
    raw = create.model_dump(mode="python")
    raw["unknown"] = True
    with pytest.raises(ValidationError):
        InstallationExecutionAdmissionCreateV1.model_validate(raw)
    with pytest.raises(StrictContractError):
        parse_create_json(b"{" + b" " * 8192 + b"}")


def test_permission_ownership_and_linkage_fail_closed(tmp_path: Path) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["permission"] = "installation.execution.permission.grant"
    with pytest.raises(ValidationError):
        InstallationExecutionAdmissionValidationInputV1.model_validate(raw)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["authenticated_operator_id"] = "operator-b"
    with pytest.raises(ValidationError, match="ownership"):
        InstallationExecutionAdmissionValidationInputV1.model_validate(raw)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["permission_grant_fingerprint"]["value"] = "f" * 64
    with pytest.raises(ValidationError, match="binding"):
        InstallationExecutionAdmissionValidationInputV1.model_validate(raw)


def test_missing_and_mismatched_fingerprints_are_rejected(tmp_path: Path) -> None:
    raw = _input(tmp_path).create.model_dump(mode="python")
    raw.pop("permission_grant_fingerprint")
    with pytest.raises(ValidationError):
        InstallationExecutionAdmissionCreateV1.model_validate(raw)
    admission, _, _ = build_admission(_input(tmp_path), admission_id=ADMISSION_ID)
    raw = admission.linkage.model_dump(mode="python")
    raw["chain_fingerprint"]["value"] = "a" * 64
    with pytest.raises(ValidationError, match="chain fingerprint"):
        contract.InstallationExecutionAdmissionLinkageV1.model_validate(raw)


def test_stale_expired_and_inactive_grants_are_rejected(tmp_path: Path) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:01Z"
    with pytest.raises(ValidationError, match="stale|expired"):
        InstallationExecutionAdmissionValidationInputV1.model_validate(raw)

    grant, _ = _grant(tmp_path)
    expired = derive_grant_status(grant, observed_at=grant.valid_until)
    with pytest.raises(ValidationError, match="not active"):
        _input(tmp_path, grant_status=(grant, expired))


def test_home_assistant_is_blocked_golden(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="Home Assistant"):
        _input(tmp_path, home_assistant=True)


def test_readiness_and_blocker_vocabularies_are_closed(tmp_path: Path) -> None:
    admission, _, _ = build_admission(_input(tmp_path), admission_id=ADMISSION_ID)
    raw = admission.model_dump(mode="python")
    raw["readiness"] = "ready"
    with pytest.raises(ValidationError):
        contract.InstallationExecutionAdmissionV1.model_validate(raw)
    raw = admission.model_dump(mode="python")
    raw["blockers"] = ["runner_binding_not_defined", "unknown"]
    with pytest.raises(ValidationError):
        contract.InstallationExecutionAdmissionV1.model_validate(raw)
    assert derive_status(admission, observed_at=admission.recorded_at).lifecycle == "active"
    assert derive_status(admission, observed_at=admission.valid_until).lifecycle == "expired"


def test_redacted_error_is_closed_sanitized_and_non_retryable() -> None:
    error = InstallationExecutionAdmissionRedactedErrorV1(
        error_code="not_found",
        blocker_codes=("missing_evidence",),
        correlation_id="admission-error-1",
    )
    rendered = error.model_dump_json()
    assert error.redacted and not error.retryable and not error.replay_allowed
    for forbidden in ("operator_id", "credential", "token", "exception", "path"):
        assert forbidden not in rendered
    with pytest.raises(ValidationError, match="canonical order"):
        InstallationExecutionAdmissionRedactedErrorV1(
            error_code="not_eligible",
            blocker_codes=("expired_evidence", "missing_evidence"),
            correlation_id="admission-error-2",
        )


def test_v035_confirmation_remains_exact_and_contract_has_no_effect_calls() -> None:
    assert CONFIRMATION_TEXT in ExecutionPermissionGrantCreateV1.model_fields["confirmation_text"].annotation.__args__
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
