from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.controlled_worker_queue_claim_admission.contract import (
    build_admission as build_v049_admission,
)
from app.controlled_worker_queue_claim_admission.contract import (
    build_create as build_v049_create,
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
from app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite import (
    contract,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.contract import (
    PERMISSION,
    SUCCESS_BLOCKERS,
    ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteAuthorityContextV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCreateV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1,
    build_create,
    evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite,
    parse_create_json,
)

REQUESTED_AT = "2026-08-27T12:00:44Z"


def _facts(tmp_path: Path):
    admission_validation = v049_input(tmp_path)
    admission = build_v049_admission(admission_validation)
    admission_status = derive_v049_status(admission, evaluated_at=V049_REQUESTED_AT)
    create = build_create(admission=admission, admission_status=admission_status)
    return admission, admission_status, create


def _input(
    tmp_path: Path, **changes
) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1:
    admission, admission_status, create = _facts(tmp_path)
    raw = {
        "operator_id": admission.operator_id,
        "authority": (
            ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteAuthorityContextV1(
                authenticated_operator_id=admission.operator_id,
                permission=PERMISSION,
                request_received_at=REQUESTED_AT,
            )
        ),
        "candidate_record_id": admission.candidate_record_id,
        "create": create,
        "controlled_worker_queue_claim_admission": admission,
        "controlled_worker_queue_claim_admission_status": admission_status,
    }
    raw.update(changes)
    return (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1.model_validate(
            raw
        )
    )


def test_active_v049_admission_freezes_prerequisite_without_effect_authority(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    first = evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
        validation
    )
    second = evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
        validation
    )
    assert first == second
    assert first.prerequisite_state == "frozen"
    assert first.eligibility == "v0.50_prerequisite_frozen"
    assert first.blockers == SUCCESS_BLOCKERS
    assert first.recognized_v049_admission_count == 1
    assert first.v0_50_prerequisite_frozen
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
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-create-v1",
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-create-v1-e\u0301",
    )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(non_nfc)
    raw = create.model_dump(mode="python")
    raw["queue_selector"] = "default"
    with pytest.raises(ValidationError):
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCreateV1.model_validate(
            raw
        )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"{" + b" " * (16 * 1024) + b"}")


def test_rejects_queue_material_tokens_payloads_and_authority(tmp_path: Path) -> None:
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
            evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
                raw
            )
        )
        assert blocked.blockers == (blocker,)
        assert not blocked.v0_50_prerequisite_frozen

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
            evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
                raw
            )
        )
        assert blocked.blockers == (blocker,)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["queue_claim_allowed"] = True
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
        raw
    )
    assert blocked.blockers == ("unsupported_authority",)
    with pytest.raises(ValidationError):
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteAuthorityContextV1.model_validate(
            raw["authority"]
        )

    raw = _input(tmp_path).model_dump(mode="python")
    raw["boundary_enabled"] = True
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
        raw
    )
    assert blocked.blockers == ("unsupported_authority",)


def test_stale_unsupported_identity_and_ambiguity_fail_closed(tmp_path: Path) -> None:
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
        {}
    )
    assert blocked.blockers == ("evidence_not_found",)
    assert blocked.operator_id == "blocked-evaluation"
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
        "not an object"  # type: ignore[arg-type]
    )
    assert blocked.blockers == ("evidence_not_found",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:40Z"
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
        raw
    )
    assert blocked.blockers == ("evidence_stale",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["operator_id"] = "foreign-operator"
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
        raw
    )
    assert blocked.blockers == ("ownership_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["home_assistant"] = True
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
        raw
    )
    assert blocked.blockers == ("installation_capability_unsupported",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["ambiguous_admission_count"] = 2
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
        raw
    )
    assert blocked.blockers == ("ambiguous_state",)


def test_rejects_expired_or_tampered_v049_admission(tmp_path: Path) -> None:
    admission, _, _ = _facts(tmp_path)
    expired_status = derive_v049_status(admission, evaluated_at=admission.valid_until)
    raw = _input(tmp_path).model_dump(mode="python")
    raw["controlled_worker_queue_claim_admission_status"] = (
        expired_status.model_dump(mode="python")
    )
    raw["create"]["admission_status_fingerprint"] = expired_status.status_fingerprint
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
        raw
    )
    assert blocked.blockers == ("v049_admission_not_active",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["controlled_worker_queue_claim_admission"]["eligibility"] = "blocked"
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
        raw
    )
    assert blocked.blockers == ("v049_admission_not_recorded",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["admission_record_fingerprint"]["value"] = "a" * 64
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
        raw
    )
    assert blocked.blockers == ("fingerprint_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inherited_limits_fingerprint"]["value"] = "b" * 64
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
        raw
    )
    assert blocked.blockers == ("inherited_limits_mismatch",)


def test_prior_boundary_still_records_only_v049_admission(tmp_path: Path) -> None:
    validation = v049_input(tmp_path)
    admission = build_v049_admission(validation)
    create = build_v049_create(
        activation_evidence=admission.worker_binding_activation_evidence,
        activation_evidence_status=admission.worker_binding_activation_evidence_status,
    )
    assert create.requested_scope == "controlled_worker_queue_claim_admission_only"
    assert admission.controlled_worker_queue_claim_admission_recorded
    assert not admission.queue_claim_allowed
    assert not admission.queue_claimed
    assert not admission.queue_lease_allowed
    assert not admission.queue_leased
    assert not admission.queue_ack_allowed
    assert not admission.queue_acknowledged
    assert not admission.worker_start_admission_allowed
    assert not admission.worker_start_allowed
    assert not admission.execution_start_allowed


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
