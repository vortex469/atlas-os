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
from app.controlled_worker_queue_claim_lease_acknowledgement import contract
from app.controlled_worker_queue_claim_lease_acknowledgement.contract import (
    PERMISSION,
    SUCCESS_BLOCKERS,
    ControlledWorkerQueueAdapterReceiptFactsV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementAuthorityContextV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1,
    build_adapter_receipt,
    build_create,
    evaluate_controlled_worker_queue_claim_lease_acknowledgement,
    parse_create_json,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_admission.contract import (
    ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_admission.contract import (
    build_admission as build_v051_admission,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_admission.contract import (
    build_create as build_v051_create,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_admission.contract import (
    derive_status as derive_v051_status,
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
V050_REQUESTED_AT = "2026-08-27T12:00:44Z"


def _facts(tmp_path: Path):
    v049_validation = v049_input(tmp_path)
    v049_admission = build_v049_admission(v049_validation)
    v049_status = derive_v049_status(v049_admission, evaluated_at=V049_REQUESTED_AT)
    v050_create = build_v050_create(
        admission=v049_admission,
        admission_status=v049_status,
    )
    v050_validation = (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1.model_validate(
            {
                "operator_id": v049_admission.operator_id,
                "authority": {
                    "authenticated_operator_id": v049_admission.operator_id,
                    "permission": (
                        "installation.execution."
                        "controlled_worker_queue_claim_lease_acknowledgement_"
                        "prerequisite.evaluate"
                    ),
                    "request_received_at": V050_REQUESTED_AT,
                },
                "candidate_record_id": v049_admission.candidate_record_id,
                "create": v050_create,
                "controlled_worker_queue_claim_admission": v049_admission,
                "controlled_worker_queue_claim_admission_status": v049_status,
                "idempotency_key": "v050-prereq-idempotency-key",
            }
        )
    )
    v050_prerequisite = build_v050_prerequisite(v050_validation)
    v050_status = derive_v050_status(v050_prerequisite, evaluated_at=V050_REQUESTED_AT)
    v051_create = build_v051_create(
        prerequisite=v050_prerequisite,
        prerequisite_status=v050_status,
    )
    v051_validation = (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1.model_validate(
            {
                "operator_id": v050_prerequisite.operator_id,
                "authority": {
                    "authenticated_operator_id": v050_prerequisite.operator_id,
                    "permission": (
                        "installation.execution."
                        "controlled_worker_queue_claim_lease_acknowledgement_"
                        "admission.evaluate"
                    ),
                    "request_received_at": REQUESTED_AT,
                },
                "candidate_record_id": v050_prerequisite.candidate_record_id,
                "create": v051_create,
                "controlled_worker_queue_claim_lease_acknowledgement_prerequisite": (
                    v050_prerequisite
                ),
                "controlled_worker_queue_claim_lease_acknowledgement_prerequisite_status": (
                    v050_status
                ),
                "idempotency_key": "v051-admission-idempotency-key",
            }
        )
    )
    v051_admission = build_v051_admission(v051_validation)
    v051_status = derive_v051_status(v051_admission, evaluated_at=REQUESTED_AT)
    adapter_receipt = build_adapter_receipt(
        admission=v051_admission,
        adapter_label="controlled.adapter.v052",
        observed_at=REQUESTED_AT,
    )
    create = build_create(
        admission=v051_admission,
        admission_status=v051_status,
        adapter_receipt=adapter_receipt,
    )
    return v051_admission, v051_status, adapter_receipt, create


def _input(
    tmp_path: Path, **changes
) -> ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1:
    admission, status, adapter_receipt, create = _facts(tmp_path)
    raw = {
        "operator_id": admission.operator_id,
        "authority": ControlledWorkerQueueClaimLeaseAcknowledgementAuthorityContextV1(
            authenticated_operator_id=admission.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": admission.candidate_record_id,
        "create": create,
        "controlled_worker_queue_claim_lease_acknowledgement_admission": admission,
        "controlled_worker_queue_claim_lease_acknowledgement_admission_status": status,
        "adapter_receipt": adapter_receipt,
        "idempotency_key": "v052-receipt-idempotency-key",
    }
    raw.update(changes)
    return ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1.model_validate(raw)


def test_active_v051_admission_and_adapter_receipt_record_boundary_only(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    first = evaluate_controlled_worker_queue_claim_lease_acknowledgement(validation)
    second = evaluate_controlled_worker_queue_claim_lease_acknowledgement(validation)
    assert first == second
    assert first.receipt_state == "recorded"
    assert first.eligibility == "controlled_worker_queue_claim_lease_acknowledgement_recorded"
    assert first.blockers == SUCCESS_BLOCKERS
    assert first.recognized_v051_admission_count == 1
    assert first.recognized_adapter_receipt_count == 1
    assert first.controlled_queue_claim_recorded
    assert first.controlled_queue_lease_recorded
    assert first.controlled_queue_acknowledgement_recorded
    assert first.controlled_worker_queue_claim_lease_acknowledgement_recorded
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
    assert not first.runtime_effect_allowed

    with pytest.raises(ValidationError):
        first.worker_start_allowed = True  # type: ignore[misc]


def test_create_and_adapter_receipt_are_closed_strict_nfc_and_bounded(
    tmp_path: Path,
) -> None:
    create = _input(tmp_path).create
    assert parse_create_json(create.model_dump_json()) == create
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"\xff")
    non_nfc = create.model_dump_json().replace(
        "controlled-worker-queue-claim-lease-acknowledgement-create-v1",
        "controlled-worker-queue-claim-lease-acknowledgement-create-v1-e\u0301",
    )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(non_nfc)
    duplicate_key = create.model_dump_json().replace(
        '"admission_id":',
        '"admission_id":"foreign","admission_id":',
        1,
    )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(duplicate_key)
    raw = create.model_dump(mode="python")
    raw["queue_selector"] = "default"
    with pytest.raises(ValidationError):
        ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1.model_validate(raw)
    receipt = _input(tmp_path).adapter_receipt.model_dump(mode="python")
    receipt["claim_token"] = "forbidden"
    with pytest.raises(ValidationError):
        ControlledWorkerQueueAdapterReceiptFactsV1.model_validate(receipt)
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
        blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
        assert blocked.blockers == (blocker,)
        assert not blocked.controlled_worker_queue_claim_lease_acknowledgement_recorded

    for field, blocker in (
        ("queue_selector", "caller_supplied_queue_selector"),
        ("claim_token", "caller_supplied_claim_token"),
        ("lease_token", "caller_supplied_lease_token"),
        ("acknowledgement_handle", "caller_supplied_acknowledgement_handle"),
        ("payload", "caller_supplied_command"),
    ):
        raw = _input(tmp_path).model_dump(mode="python")
        raw["create"][field] = "forbidden"
        blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
        assert blocked.blockers == (blocker,)

    for field in (
        "worker_start_admission_allowed",
        "worker_start_allowed",
        "agent_invocation_allowed",
        "execution_start_allowed",
        "deployment_allowed",
        "rollback_allowed",
        "release_publication_allowed",
        "controlled_worker_queue_claim_lease_acknowledgement_recorded",
    ):
        raw = _input(tmp_path).model_dump(mode="python")
        raw["authority"][field] = True
        blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
        assert blocked.blockers == ("unsupported_authority",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["boundary_enabled"] = True
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
    assert blocked.blockers == ("unsupported_authority",)


def test_missing_stale_wrong_owner_and_ambiguity_fail_closed(tmp_path: Path) -> None:
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement({})
    assert blocked.blockers == ("evidence_not_found",)
    assert blocked.operator_id == "blocked-evaluation"
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(
        "not an object"  # type: ignore[arg-type]
    )
    assert blocked.blockers == ("evidence_not_found",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:40Z"
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
    assert blocked.blockers == ("evidence_stale",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["operator_id"] = "foreign-operator"
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
    assert blocked.blockers == ("ownership_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["home_assistant"] = True
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
    assert blocked.blockers == ("installation_capability_unsupported",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["ambiguous_adapter_receipt_count"] = 1
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
    assert blocked.blockers == ("ambiguous_state",)


def test_rejects_malformed_lineage_wrong_fingerprints_and_stale_prerequisites(
    tmp_path: Path,
) -> None:
    admission, _, _, _ = _facts(tmp_path)
    expired_status = derive_v051_status(admission, evaluated_at=admission.valid_until)
    raw = _input(tmp_path).model_dump(mode="python")
    raw["controlled_worker_queue_claim_lease_acknowledgement_admission_status"] = (
        expired_status.model_dump(mode="python")
    )
    raw["create"]["admission_status_fingerprint"] = expired_status.status_fingerprint
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
    assert blocked.blockers == ("v051_admission_not_active",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["controlled_worker_queue_claim_lease_acknowledgement_admission"][
        "eligibility"
    ] = "blocked"
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
    assert blocked.blockers == ("v051_admission_not_recorded",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["admission_record_fingerprint"]["value"] = "a" * 64
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
    assert blocked.blockers == ("fingerprint_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inherited_limits_fingerprint"]["value"] = "b" * 64
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
    assert blocked.blockers == ("inherited_limits_mismatch",)


def test_rejects_adapter_identity_receipt_replay_and_corruption(tmp_path: Path) -> None:
    for field, blocker in (
        ("adapter_identity_fingerprint", "adapter_identity_mismatch"),
        ("claim_receipt_fingerprint", "claim_receipt_mismatch"),
        ("lease_receipt_fingerprint", "lease_receipt_mismatch"),
        ("acknowledgement_receipt_fingerprint", "acknowledgement_receipt_mismatch"),
    ):
        raw = _input(tmp_path).model_dump(mode="python")
        raw["adapter_receipt"][field]["value"] = "c" * 64
        blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
        assert blocked.blockers == (blocker,)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["adapter_receipt"]["queue_subject_fingerprint"]["value"] = "d" * 64
    blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
    assert blocked.blockers == ("linkage_mismatch",)

    for field, blocker in (
        ("reservation_before_effect", "reservation_before_effect_missing"),
        ("replay_detected", "replay_detected"),
        ("corruption_detected", "corrupt_adapter_evidence"),
        ("ambiguity_detected", "ambiguous_state"),
    ):
        raw = _input(tmp_path).model_dump(mode="python")
        raw["adapter_receipt"][field] = field != "reservation_before_effect"
        blocked = evaluate_controlled_worker_queue_claim_lease_acknowledgement(raw)
        assert blocked.blockers == (blocker,)


def test_contract_has_no_persistence_route_or_production_effect_surfaces() -> None:
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
        ".consume(",
        ".delete(",
        ".dispatch(",
        ".start_worker(",
        ".execute(",
        ".invoke_agent(",
    ):
        assert call not in source
