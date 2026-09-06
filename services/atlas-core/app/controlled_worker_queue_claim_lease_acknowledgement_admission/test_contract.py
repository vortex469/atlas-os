from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.controlled_worker_queue_claim_admission.contract import (
    build_admission as build_v049_admission,
)
from app.controlled_worker_queue_claim_admission.contract import (
    derive_status as derive_v049_status,
)
from app.controlled_worker_queue_claim_admission.test_contract import (
    REQUESTED_AT as V049_REQUESTED_AT,
)
from app.controlled_worker_queue_claim_admission.test_contract import (
    _input as v049_input,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_admission import (
    contract,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_admission.contract import (
    PERMISSION,
    SUCCESS_BLOCKERS,
    ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthorityContextV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCreateV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1,
    build_create,
    evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission,
    parse_create_json,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.contract import (
    SUCCESS_BLOCKERS as V050_SUCCESS_BLOCKERS,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.contract import (
    ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.contract import (
    build_create as build_v050_create,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.contract import (
    build_prerequisite as build_v050_prerequisite,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.contract import (
    derive_status as derive_v050_status,
)

REQUESTED_AT = "2026-08-27T12:00:44Z"


def _facts(tmp_path: Path):
    admission_validation = v049_input(tmp_path)
    admission = build_v049_admission(admission_validation)
    admission_status = derive_v049_status(admission, evaluated_at=V049_REQUESTED_AT)
    prerequisite_create = build_v050_create(
        admission=admission,
        admission_status=admission_status,
    )
    prerequisite_validation = {
        "operator_id": admission.operator_id,
        "authority": {
            "authenticated_operator_id": admission.operator_id,
            "permission": (
                "installation.execution."
                "controlled_worker_queue_claim_lease_acknowledgement_prerequisite.evaluate"
            ),
            "request_received_at": REQUESTED_AT,
        },
        "candidate_record_id": admission.candidate_record_id,
        "create": prerequisite_create,
        "controlled_worker_queue_claim_admission": admission,
        "controlled_worker_queue_claim_admission_status": admission_status,
        "idempotency_key": "v050-prereq-idempotency-key",
    }
    contract_input = (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1.model_validate(
            prerequisite_validation
        )
    )
    prerequisite = build_v050_prerequisite(contract_input)
    prerequisite_status = derive_v050_status(prerequisite, evaluated_at=REQUESTED_AT)
    create = build_create(
        prerequisite=prerequisite,
        prerequisite_status=prerequisite_status,
    )
    assert contract_input.create.requested_scope.endswith("_prerequisite_only")
    return prerequisite, prerequisite_status, create


def _input(
    tmp_path: Path, **changes
) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1:
    prerequisite, prerequisite_status, create = _facts(tmp_path)
    raw = {
        "operator_id": prerequisite.operator_id,
        "authority": (
            ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthorityContextV1(
                authenticated_operator_id=prerequisite.operator_id,
                permission=PERMISSION,
                request_received_at=REQUESTED_AT,
            )
        ),
        "candidate_record_id": prerequisite.candidate_record_id,
        "create": create,
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite": prerequisite,
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite_status": (
            prerequisite_status
        ),
        "idempotency_key": "v051-admission-idempotency-key",
    }
    raw.update(changes)
    return (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1.model_validate(
            raw
        )
    )


def test_active_v050_prerequisite_records_admission_without_effect_authority(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    first = evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
        validation
    )
    second = evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
        validation
    )
    assert first == second
    assert first.admission_state == "recorded"
    assert (
        first.eligibility
        == "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded"
    )
    assert first.blockers == SUCCESS_BLOCKERS
    assert first.blockers == V050_SUCCESS_BLOCKERS
    assert first.recognized_v050_prerequisite_count == 1
    assert first.controlled_worker_queue_claim_lease_acknowledgement_admission_recorded
    assert not first.later_queue_claim_lease_acknowledgement_allowed
    assert not first.runtime_effect_allowed
    assert not first.queue_adapter_defined
    assert not first.queue_polling_allowed
    assert not first.queue_claim_allowed
    assert not first.queue_lease_allowed
    assert not first.queue_ack_allowed
    assert not first.queue_claimed
    assert not first.queue_leased
    assert not first.queue_acknowledged
    assert not first.worker_activation_runtime_allowed
    assert not first.store_contact_allowed
    assert not first.runtime_contact_allowed
    assert not first.worker_start_admission_allowed
    assert not first.worker_start_admission_build_allowed
    assert not first.worker_start_allowed
    assert not first.worker_start_admitted
    assert not first.worker_started
    assert not first.agent_invocation_allowed
    assert not first.agent_invoked
    assert not first.execution_start_allowed
    assert not first.execution_start_admission_build_allowed
    assert not first.execution_started

    with pytest.raises(ValidationError):
        first.queue_claim_allowed = True  # type: ignore[misc]


def test_create_is_closed_strict_nfc_and_size_bounded(tmp_path: Path) -> None:
    create = _input(tmp_path).create
    assert parse_create_json(create.model_dump_json()) == create
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"\xff")
    non_nfc = create.model_dump_json().replace(
        "controlled-worker-queue-claim-lease-acknowledgement-admission-create-v1",
        "controlled-worker-queue-claim-lease-acknowledgement-admission-create-v1-e\u0301",
    )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(non_nfc)
    duplicate_key = create.model_dump_json().replace(
        '"prerequisite_id":',
        '"prerequisite_id":"00000000-0000-0000-0000-000000000000","prerequisite_id":',
        1,
    )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(duplicate_key)
    raw = create.model_dump(mode="python")
    raw["queue_selector"] = "default"
    with pytest.raises(ValidationError):
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCreateV1.model_validate(
            raw
        )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"{" + b" " * (16 * 1024) + b"}")


def test_rejects_material_tokens_payloads_and_authority(tmp_path: Path) -> None:
    for field, blocker in (
        ("credential_material_present", "caller_supplied_credential"),
        ("endpoint_material_present", "caller_supplied_endpoint"),
        ("command_material_present", "caller_supplied_command"),
        ("payload_material_present", "caller_supplied_command"),
        ("queue_selector_material_present", "caller_supplied_queue_selector"),
        ("claim_token_material_present", "caller_supplied_claim_token"),
        ("lease_token_material_present", "caller_supplied_lease_token"),
        (
            "acknowledgement_handle_material_present",
            "caller_supplied_acknowledgement_handle",
        ),
    ):
        raw = _input(tmp_path).model_dump(mode="python")
        raw["create"][field] = True
        blocked = (
            evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
                raw
            )
        )
        assert blocked.blockers == (blocker,)
        assert (
            not blocked.controlled_worker_queue_claim_lease_acknowledgement_admission_recorded
        )

    for field, blocker in (
        ("queue_selector", "caller_supplied_queue_selector"),
        ("claim_token", "caller_supplied_claim_token"),
        ("lease_token", "caller_supplied_lease_token"),
        ("acknowledgement_handle", "caller_supplied_acknowledgement_handle"),
        ("payload", "caller_supplied_command"),
    ):
        raw = _input(tmp_path).model_dump(mode="python")
        raw["create"][field] = "forbidden"
        blocked = (
            evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
                raw
            )
        )
        assert blocked.blockers == (blocker,)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["queue_claim_allowed"] = True
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
        raw
    )
    assert blocked.blockers == ("unsupported_authority",)
    with pytest.raises(ValidationError):
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthorityContextV1.model_validate(
            raw["authority"]
        )

    for field in (
        "later_queue_claim_lease_acknowledgement_allowed",
        "worker_start_admission_build_allowed",
        "execution_start_admission_build_allowed",
        "runtime_effect_allowed",
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
    ):
        raw = _input(tmp_path).model_dump(mode="python")
        raw["authority"][field] = True
        blocked = (
            evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
                raw
            )
        )
        assert blocked.blockers == ("unsupported_authority",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["boundary_enabled"] = True
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
        raw
    )
    assert blocked.blockers == ("unsupported_authority",)


def test_stale_unsupported_identity_and_ambiguity_fail_closed(tmp_path: Path) -> None:
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
        {}
    )
    assert blocked.blockers == ("evidence_not_found",)
    assert blocked.operator_id == "blocked-evaluation"
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
        "not an object"  # type: ignore[arg-type]
    )
    assert blocked.blockers == ("evidence_not_found",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:40Z"
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
        raw
    )
    assert blocked.blockers == ("evidence_stale",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["operator_id"] = "foreign-operator"
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
        raw
    )
    assert blocked.blockers == ("ownership_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["home_assistant"] = True
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
        raw
    )
    assert blocked.blockers == ("installation_capability_unsupported",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["ambiguous_prerequisite_count"] = 2
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
        raw
    )
    assert blocked.blockers == ("ambiguous_state",)


def test_rejects_expired_or_tampered_v050_prerequisite(tmp_path: Path) -> None:
    prerequisite, _, _ = _facts(tmp_path)
    expired_status = derive_v050_status(
        prerequisite,
        evaluated_at=prerequisite.valid_until,
    )
    raw = _input(tmp_path).model_dump(mode="python")
    raw["controlled_worker_queue_claim_lease_acknowledgement_prerequisite_status"] = (
        expired_status.model_dump(mode="python")
    )
    raw["create"]["prerequisite_status_fingerprint"] = (
        expired_status.status_fingerprint
    )
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
        raw
    )
    assert blocked.blockers == ("v050_prerequisite_not_active",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["controlled_worker_queue_claim_lease_acknowledgement_prerequisite"][
        "eligibility"
    ] = "blocked"
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
        raw
    )
    assert blocked.blockers == ("v050_prerequisite_not_frozen",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["prerequisite_record_fingerprint"]["value"] = "a" * 64
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
        raw
    )
    assert blocked.blockers == ("fingerprint_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inherited_limits_fingerprint"]["value"] = "b" * 64
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
        raw
    )
    assert blocked.blockers == ("inherited_limits_mismatch",)


def test_contract_has_no_persistence_route_or_effect_surfaces() -> None:
    path = Path(contract.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name if isinstance(node, ast.Import) else node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    forbidden = (
        "atlas_execution_worker",
        "dispatch",
        "docker",
        "fastapi",
        "provider",
        "repository",
        "requests",
        "socket",
        "sqlite",
        "subprocess",
        "workflow",
        "transport",
        "deployment",
        "rollback",
    )
    assert not [name for name in imports if any(term in name for term in forbidden)]
    source = path.read_text(encoding="utf-8").lower()
    for call in (
        "subprocess.",
        "os.system",
        "create_subprocess",
        ".enqueue(",
        ".dequeue(",
        ".publish(",
        ".send(",
        ".poll(",
        ".claim(",
        ".lease(",
        ".consume(",
        ".acknowledge(",
        ".delete(",
        ".dispatch(",
        ".start_worker(",
        ".execute(",
        ".invoke_agent(",
    ):
        assert call not in source
