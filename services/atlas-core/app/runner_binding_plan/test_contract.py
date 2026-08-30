from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_execution_admission.contract import (
    build_admission,
)
from app.installation_execution_admission.contract import (
    derive_status as derive_admission_status,
)
from app.installation_execution_admission.test_contract import (
    ADMISSION_ID,
)
from app.installation_execution_admission.test_contract import (
    _input as admission_input,
)
from app.runner_binding_plan import contract
from app.runner_binding_plan.contract import (
    PERMISSION,
    PLAN_BLOCKERS,
    RunnerBindingPlanAuthorityContextV1,
    RunnerBindingPlanCollectionV1,
    RunnerBindingPlanCreateV1,
    RunnerBindingPlanRedactedErrorV1,
    RunnerBindingPlanResultV1,
    RunnerBindingPlanValidationInputV1,
    RunnerFilesystemLimitsV1,
    RunnerNetworkLimitsV1,
    RunnerResourceLimitsV1,
    RunnerSandboxLimitsV1,
    StrictContractError,
    build_limits,
    build_plan,
    build_runner_reference,
    derive_status,
    opaque_fingerprint,
    parse_create_json,
    plan_fingerprint,
)

PLAN_ID = "40f029e7-3b29-4e85-b89f-c3add6f1793d"
RUNNER_ID = "524238cb-02a3-4ff2-8e7a-dd8c53523a82"
REQUESTED_AT = "2026-08-27T12:00:32Z"


def _admission(tmp_path: Path):
    admission, _, _ = build_admission(
        admission_input(tmp_path), admission_id=ADMISSION_ID
    )
    return admission, derive_admission_status(
        admission, observed_at="2026-08-27T12:00:31Z"
    )


def _runner(operator_id: str):
    return build_runner_reference(
        runner_reference_id=RUNNER_ID,
        owner_operator_id=operator_id,
        identity_fingerprint=opaque_fingerprint(
            "atlas:test:runner-identity:v1", "runner-one"
        ),
        capability_profile_fingerprint=opaque_fingerprint(
            "atlas:test:runner-capability:v1", "confined-plan-only"
        ),
        limits=build_limits(),
        valid_from="2026-08-27T12:00:20Z",
        valid_until="2026-08-27T12:00:45Z",
    )


def _validation(tmp_path: Path, **changes) -> RunnerBindingPlanValidationInputV1:
    admission, status = changes.pop("admission_status", _admission(tmp_path))
    runner = changes.pop("runner_reference", _runner(admission.operator_id))
    create = changes.pop(
        "create",
        RunnerBindingPlanCreateV1(
            admission_id=admission.admission_id,
            admission_fingerprint=admission.admission_fingerprint,
            admission_valid_until=admission.valid_until,
            runner_reference_id=runner.runner_reference_id,
            runner_reference_fingerprint=runner.reference_fingerprint,
            limits_fingerprint=runner.limits.limits_fingerprint,
        ),
    )
    values = {
        "operator_id": admission.operator_id,
        "authority": RunnerBindingPlanAuthorityContextV1(
            authenticated_operator_id=admission.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": admission.candidate_record_id,
        "create": create,
        "execution_admission": admission,
        "execution_admission_status": status,
        "runner_reference": runner,
        "idempotency_key": "runner-binding-plan-key-1",
    }
    values.update(changes)
    return RunnerBindingPlanValidationInputV1.model_validate(values)


def test_valid_plan_is_deterministic_immutable_and_binding_planned(
    tmp_path: Path,
) -> None:
    first = build_plan(_validation(tmp_path), plan_id=PLAN_ID)
    second = build_plan(_validation(tmp_path), plan_id=PLAN_ID)
    assert first == second
    plan, idempotency, reservation = first
    assert plan.plan_fingerprint == plan_fingerprint(plan)
    assert plan.eligibility == "binding_planned"
    assert plan.blockers == PLAN_BLOCKERS
    assert plan.valid_until == "2026-08-27T12:00:45Z"
    assert idempotency.retained_forever and not idempotency.raw_key_persisted
    assert reservation.retained_forever and not reservation.releasable
    assert not reservation.replay_allowed
    assert plan.linkage.execution_admission_linkage == (
        _validation(tmp_path).execution_admission.linkage
    )
    with pytest.raises(ValidationError):
        plan.record_state = "bound"  # type: ignore[misc]


def test_all_effect_authority_is_fixed_false(tmp_path: Path) -> None:
    plan, _, _ = build_plan(_validation(tmp_path), plan_id=PLAN_ID)
    fields = (
        "runner_registered", "runner_contacted", "runner_reserved",
        "runner_bound", "runner_binding_allowed", "execution_start_allowed",
        "execution_authorized", "installation_allowed", "dispatch_allowed",
        "retry_allowed", "resend_allowed", "agent_invocation_allowed",
        "worker_allowed", "workflow_allowed", "docker_allowed",
        "podman_allowed", "shell_allowed", "process_allowed",
        "provider_mutation_allowed", "repository_mutation_allowed",
        "in_guest_mutation_allowed", "deployment_allowed", "rollback_allowed",
        "replay_allowed",
    )
    assert not any(getattr(plan, field) for field in fields)
    assert not plan.runner_reference.registered
    assert not plan.runner_reference.invocation_allowed


def test_closed_unknown_duplicate_and_body_bounds(tmp_path: Path) -> None:
    create = _validation(tmp_path).create
    assert parse_create_json(create.model_dump_json()) == create
    duplicate = create.model_dump_json()[:-1] + ',"schema":"duplicate"}'
    with pytest.raises(StrictContractError):
        parse_create_json(duplicate)
    raw = create.model_dump(mode="python")
    raw["unknown"] = True
    with pytest.raises(ValidationError):
        RunnerBindingPlanCreateV1.model_validate(raw)
    with pytest.raises(StrictContractError):
        parse_create_json(b"{" + b" " * 4096 + b"}")


def test_missing_and_mismatched_fingerprints_are_rejected(tmp_path: Path) -> None:
    raw = _validation(tmp_path).create.model_dump(mode="python")
    raw.pop("limits_fingerprint")
    with pytest.raises(ValidationError):
        RunnerBindingPlanCreateV1.model_validate(raw)
    plan, _, _ = build_plan(_validation(tmp_path), plan_id=PLAN_ID)
    raw = plan.linkage.model_dump(mode="python")
    raw["v020_v035_chain_fingerprint"]["value"] = "a" * 64
    with pytest.raises(ValidationError, match="embedded"):
        contract.RunnerBindingPlanLinkageV1.model_validate(raw)
    raw = plan.model_dump(mode="python")
    raw["plan_fingerprint"]["value"] = "b" * 64
    with pytest.raises(ValidationError, match="fingerprint"):
        contract.RunnerBindingPlanV1.model_validate(raw)


def test_permission_ownership_and_admission_linkage_fail_closed(tmp_path: Path) -> None:
    raw = _validation(tmp_path).model_dump(mode="python")
    raw["authority"]["permission"] = "installation.execution.admission.record"
    with pytest.raises(ValidationError):
        RunnerBindingPlanValidationInputV1.model_validate(raw)
    raw = _validation(tmp_path).model_dump(mode="python")
    raw["authority"]["authenticated_operator_id"] = "operator-b"
    with pytest.raises(ValidationError, match="ownership"):
        RunnerBindingPlanValidationInputV1.model_validate(raw)
    raw = _validation(tmp_path).model_dump(mode="python")
    raw["create"]["admission_fingerprint"]["value"] = "c" * 64
    with pytest.raises(ValidationError, match="admission linkage"):
        RunnerBindingPlanValidationInputV1.model_validate(raw)


def test_runner_reference_and_limit_fingerprints_fail_closed(tmp_path: Path) -> None:
    raw = _validation(tmp_path).runner_reference.model_dump(mode="python")
    raw["reference_fingerprint"]["value"] = "d" * 64
    with pytest.raises(ValidationError, match="reference fingerprint"):
        contract.RunnerReferenceV1.model_validate(raw)
    raw = _validation(tmp_path).runner_reference.model_dump(mode="python")
    raw["eligibility"] = "invokable"
    with pytest.raises(ValidationError):
        contract.RunnerReferenceV1.model_validate(raw)
    raw = _validation(tmp_path).model_dump(mode="python")
    raw["create"]["runner_reference_fingerprint"]["value"] = "e" * 64
    with pytest.raises(ValidationError, match="runner reference"):
        RunnerBindingPlanValidationInputV1.model_validate(raw)


@pytest.mark.parametrize(
    ("model", "field", "value"),
    (
        (RunnerSandboxLimitsV1, "privileged", True),
        (RunnerResourceLimitsV1, "cpu_millis_max", 1001),
        (RunnerNetworkLimitsV1, "egress_allowed", True),
        (RunnerFilesystemLimitsV1, "host_mounts_allowed", True),
        (RunnerFilesystemLimitsV1, "ephemeral_workspace_bytes_max", 268435457),
    ),
)
def test_sandbox_resource_network_and_filesystem_ceilings_are_closed(
    model, field: str, value,
) -> None:
    raw = model().model_dump(mode="python")
    raw[field] = value
    with pytest.raises(ValidationError):
        model.model_validate(raw)


def test_stale_expired_and_non_active_admission_are_rejected(tmp_path: Path) -> None:
    raw = _validation(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:01Z"
    with pytest.raises(ValidationError, match="stale|expired"):
        RunnerBindingPlanValidationInputV1.model_validate(raw)
    admission, _ = _admission(tmp_path)
    expired = derive_admission_status(admission, observed_at=admission.valid_until)
    with pytest.raises(ValidationError, match="not active"):
        _validation(tmp_path, admission_status=(admission, expired))


def test_binding_planned_admission_gated_blocked_and_lifecycle_states(
    tmp_path: Path,
) -> None:
    validation = _validation(tmp_path)
    assert validation.execution_admission.readiness == "admission_gated"
    plan, _, _ = build_plan(validation, plan_id=PLAN_ID)
    assert plan.eligibility == "binding_planned"
    assert derive_status(plan, observed_at=plan.recorded_at).lifecycle == "active"
    assert derive_status(plan, observed_at=plan.valid_until).lifecycle == "expired"
    error = RunnerBindingPlanRedactedErrorV1(
        error_code="not_eligible",
        correlation_fingerprint=opaque_fingerprint(
            "atlas:test:correlation:v1", "blocked"
        ),
    )
    blocked = RunnerBindingPlanResultV1(
        disposition="blocked", plan=None, status=None, audit_evidence=None, error=error
    )
    assert blocked.disposition == "blocked"
    assert not blocked.execution_authorized


def test_home_assistant_is_blocked_golden(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="Home Assistant"):
        _validation(tmp_path, home_assistant=True)


def test_redacted_error_and_collection_are_closed() -> None:
    error = RunnerBindingPlanRedactedErrorV1(
        error_code="not_found",
        correlation_fingerprint=opaque_fingerprint(
            "atlas:test:correlation:v1", "not-found"
        ),
    )
    rendered = error.model_dump_json()
    assert error.redacted and not error.retryable and not error.replay_allowed
    for forbidden in (
        "operator_id", "credential", "endpoint", "command", "stdout",
        "internal_path", "exception",
    ):
        assert forbidden not in rendered
    collection = RunnerBindingPlanCollectionV1(plans=())
    assert collection.plans == () and not collection.mutation_allowed


def test_contract_has_no_forbidden_imports_or_effect_calls() -> None:
    tree = ast.parse(Path(contract.__file__).read_text(encoding="utf-8"))
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
