"""P1 tests for the frozen dormant delivery wiring contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.dormant_agent_intake_delivery_wiring.contract import (
    AgentInstallationIntakeAdmissionV1,
    AgentInstallationIntakeResultV1,
    CoreAgentIntakeDeliveryAuditEvidenceV1,
    CoreAgentIntakeDeliveryCreateV1,
    CoreAgentIntakeDeliveryIdempotencyV1,
    CoreAgentIntakeDeliveryPreparationResultV1,
    CoreAgentIntakeDeliveryPreparationV1,
    CoreAgentIntakeDeliveryRedactedErrorV1,
    CoreAgentIntakeDeliveryResponseValidationV1,
    DormantAgentIntakeAuthenticationReferenceV1,
    DormantAgentIntakeDeliveryConfigurationV1,
    DormantAgentIntakeEndpointV1,
    StrictContractError,
    acknowledgement_fingerprint,
    admission_fingerprint,
    audit_evidence_fingerprint,
    endpoint_fingerprint,
    parse_delivery_create_json,
    parse_delivery_response_json,
    preparation_fingerprint,
    preparation_lifecycle,
    request_fingerprint,
    response_validation_fingerprint,
    validate_delivery_preparation,
    validate_delivery_response,
)
from app.installation_dispatch_handoff.contract import FingerprintV1
from app.installation_dispatch_handoff.test_contract import built

OPERATOR = "operator-a"
PREPARATION_ID = "00000000-0000-4000-8000-000000000801"
INTAKE_REQUEST_ID = "00000000-0000-4000-8000-000000000802"
DELIVERY_ATTEMPT_ID = "00000000-0000-4000-8000-000000000803"
SIMULATION_REQUEST_ID = "00000000-0000-4000-8000-000000000804"
INTAKE_RECORD_ID = "00000000-0000-4000-8000-000000000805"
SIMULATED_DELIVERY_ID = "00000000-0000-4000-8000-000000000806"
SIMULATED_ACK_ID = "00000000-0000-4000-8000-000000000807"
ADMISSION_ID = "00000000-0000-4000-8000-000000000808"
PREPARED_AT = "2026-08-27T12:00:02Z"
RECEIVED_AT = "2026-08-27T12:00:03Z"


def fingerprint(character: str) -> FingerprintV1:
    return FingerprintV1(
        algorithm="sha256",
        canonicalization="atlas-jcs-nfc-v1",
        value=character * 64,
    )


def configuration() -> DormantAgentIntakeDeliveryConfigurationV1:
    return DormantAgentIntakeDeliveryConfigurationV1(
        endpoint=DormantAgentIntakeEndpointV1(
            host="atlas-agent.internal",
            port=8443,
            tls_server_name="atlas-agent.internal",
            ca_bundle_file="/run/atlas/agent-intake-ca.pem",
        ),
        authentication=DormantAgentIntakeAuthenticationReferenceV1(
            credential_file="/run/secrets/atlas-agent-intake-token"
        ),
    )


def preparation(tmp_path: Path, *, operator_id: str = OPERATOR):
    envelope, _ = built(tmp_path)
    prior_evidence = {
        "intake_simulation": {
            "simulation_request_id": SIMULATION_REQUEST_ID,
            "intake_record_id": INTAKE_RECORD_ID,
            "intake_record_fingerprint": fingerprint("1").model_dump(mode="json"),
        },
        "simulated_delivery": {
            "simulated_delivery_id": SIMULATED_DELIVERY_ID,
            "simulated_delivery_fingerprint": fingerprint("2").model_dump(mode="json"),
            "delivery_record_fingerprint": fingerprint("3").model_dump(mode="json"),
            "acknowledgement_id": SIMULATED_ACK_ID,
            "acknowledgement_fingerprint": fingerprint("4").model_dump(mode="json"),
        },
    }
    request_raw = {
        "schema": "agent-installation-intake-request-v1",
        "intake_request_id": INTAKE_REQUEST_ID,
        "delivery_attempt_id": DELIVERY_ATTEMPT_ID,
        "sent_at": PREPARED_AT,
        "expires_at": envelope.valid_until,
        "operation": "install-container",
        "mode": "intake-evidence-only",
        "sender": "atlas-core",
        "recipient": {
            "service": "atlas-agent",
            "intake_contract": "agent-installation-intake-v1",
        },
        "operator_assertion": {"operator_id": operator_id, "asserted_by": "atlas-core"},
        "envelope": envelope.model_dump(mode="json"),
        "prior_evidence": prior_evidence,
        "delivery_authorized": True,
        "evidence_admission_requested": True,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    request_raw["request_fingerprint"] = request_fingerprint(request_raw).model_dump(
        mode="json"
    )
    source = {
        "dispatch_envelope_id": envelope.dispatch_envelope_id,
        "dispatch_envelope_fingerprint": envelope.dispatch_envelope_fingerprint.model_dump(
            mode="json"
        ),
        "intake_record_id": INTAKE_RECORD_ID,
        "intake_record_fingerprint": fingerprint("1").model_dump(mode="json"),
        "intake_simulation_evidence_fingerprint": fingerprint("5").model_dump(
            mode="json"
        ),
        "simulated_delivery_id": SIMULATED_DELIVERY_ID,
        "simulated_delivery_fingerprint": fingerprint("2").model_dump(mode="json"),
        "delivery_record_fingerprint": fingerprint("3").model_dump(mode="json"),
        "simulated_delivery_evidence_fingerprint": fingerprint("6").model_dump(
            mode="json"
        ),
        "simulated_acknowledgement_id": SIMULATED_ACK_ID,
        "simulated_acknowledgement_fingerprint": fingerprint("4").model_dump(
            mode="json"
        ),
        "simulated_acknowledgement_evidence_fingerprint": fingerprint("7").model_dump(
            mode="json"
        ),
    }
    raw = {
        "schema": "core-agent-intake-delivery-preparation-v1",
        "delivery_preparation_id": PREPARATION_ID,
        "prepared_at": PREPARED_AT,
        "valid_until": envelope.valid_until,
        "endpoint_fingerprint": endpoint_fingerprint(configuration().endpoint).model_dump(
            mode="json"
        ),
        "request": request_raw,
        "source": source,
        "lifecycle_at_preparation": "prepared_dormant",
        "status": "not_sent",
        "statement": "core_prepared_agent_intake_delivery_wiring_only",
        "default_enabled": False,
        "network_attempted": False,
        "delivery_authorized": False,
        "delivery_received": False,
        "evidence_admission_granted": False,
        "execution_admission_granted": False,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["preparation_fingerprint"] = preparation_fingerprint(
        operator_id=operator_id, preparation=raw
    ).model_dump(mode="json")
    return CoreAgentIntakeDeliveryPreparationV1.model_validate(raw)


def admitted_validation(tmp_path: Path):
    prepared = preparation(tmp_path)
    request = prepared.request
    admission_raw = {
        "schema": "agent-installation-intake-admission-v1",
        "admission_id": ADMISSION_ID,
        "intake_request_id": request.intake_request_id,
        "delivery_attempt_id": request.delivery_attempt_id,
        "received_at": RECEIVED_AT,
        "valid_until": request.expires_at,
        "operation": "install-container",
        "mode": "intake-evidence-only",
        "authenticated_sender": "atlas-core/install-intake-v1",
        "source": {
            "request_fingerprint": request.request_fingerprint.model_dump(mode="json"),
            "dispatch_envelope_id": request.envelope.dispatch_envelope_id,
            "dispatch_envelope_fingerprint": request.envelope.dispatch_envelope_fingerprint.model_dump(
                mode="json"
            ),
        },
        "linkage": request.envelope.linkage.model_dump(mode="json"),
        "prior_evidence": request.prior_evidence.model_dump(mode="json"),
        "status": "admitted_for_evidence_only",
        "reason_codes": [],
        "statement": "agent_accepted_authenticated_handoff_for_intake_evidence_only",
        "delivery_received": True,
        "evidence_admission_granted": True,
        "execution_admission_granted": False,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    admission_raw["admission_fingerprint"] = admission_fingerprint(
        operator_id=OPERATOR, admission=admission_raw
    ).model_dump(mode="json")
    admission = AgentInstallationIntakeAdmissionV1.model_validate(admission_raw)
    result = AgentInstallationIntakeResultV1(
        intake_request_id=request.intake_request_id,
        outcome="admitted_for_evidence_only",
        admission=admission,
        reason_code=None,
    )
    acknowledgement_raw = {
        "schema": "agent-installation-intake-acknowledgement-v1",
        "admission_id": admission.admission_id,
        "admission_fingerprint": admission.admission_fingerprint.model_dump(mode="json"),
        "intake_request_id": admission.intake_request_id,
        "received_at": admission.received_at,
        "valid_until": admission.valid_until,
        "status": "admitted_for_evidence_only",
        "provenance": "authenticated_core_intake_evidence_only",
        "execution_admission_granted": False,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    ack = acknowledgement_fingerprint(acknowledgement_raw)
    raw = {
        "schema": "core-agent-intake-delivery-response-validation-v1",
        "delivery_preparation_id": prepared.delivery_preparation_id,
        "intake_request_id": request.intake_request_id,
        "delivery_attempt_id": request.delivery_attempt_id,
        "validated_at": RECEIVED_AT,
        "outcome": "valid_admission_evidence",
        "agent_result": result.model_dump(mode="json"),
        "admission_fingerprint": admission.admission_fingerprint.model_dump(mode="json"),
        "acknowledgement_fingerprint": ack.model_dump(mode="json"),
        "reason_code": None,
        "source_was_injected": True,
        "production_delivery_observed": False,
        "execution_admission_granted": False,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["validation_fingerprint"] = response_validation_fingerprint(
        operator_id=OPERATOR, validation=raw
    ).model_dump(mode="json")
    return prepared, CoreAgentIntakeDeliveryResponseValidationV1.model_validate(raw)


def test_closed_immutable_models_and_duplicate_unknown_rejection(tmp_path: Path) -> None:
    value = preparation(tmp_path)
    with pytest.raises(ValidationError):
        value.status = "sent"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        CoreAgentIntakeDeliveryPreparationV1.model_validate(
            {**value.model_dump(mode="json"), "transport": "httpx"}
        )
    create = CoreAgentIntakeDeliveryCreateV1(
        dispatch_envelope_id=value.source.dispatch_envelope_id,
        intake_record_id=INTAKE_RECORD_ID,
        simulated_delivery_id=SIMULATED_DELIVERY_ID,
        simulated_acknowledgement_id=SIMULATED_ACK_ID,
    )
    payload = json.dumps(create.model_dump(mode="json"))
    assert parse_delivery_create_json(payload) == create
    with pytest.raises(StrictContractError):
        parse_delivery_create_json(payload[:-1] + ',"schema":"duplicate"}')
    with pytest.raises(StrictContractError):
        parse_delivery_create_json(payload[:-1] + ',"command":"install"}')


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("host", "127.0.0.1"),
        ("host", "Atlas-Agent.internal"),
        ("host", "localhost"),
        ("path", "/api/v1/internal/execute"),
        ("follow_redirects", True),
    ),
)
def test_invalid_endpoint_shapes_fail(field: str, value: object) -> None:
    raw = configuration().endpoint.model_dump(mode="json")
    raw[field] = value
    if field == "host":
        raw["tls_server_name"] = value
    with pytest.raises(ValidationError):
        DormantAgentIntakeEndpointV1.model_validate(raw)


def test_invalid_authentication_reference_shapes_fail() -> None:
    raw = configuration().authentication.model_dump(mode="json")
    for field, value in (
        ("credential_file", "relative/token"),
        ("credential_file", "/run/../secret"),
        ("required_file_mode", "0644"),
        ("principal", "atlas-core/worker-v1"),
    ):
        with pytest.raises(ValidationError):
            DormantAgentIntakeAuthenticationReferenceV1.model_validate(
                {**raw, field: value}
            )
    endpoint_raw = configuration().endpoint.model_dump(mode="json")
    endpoint_raw["tls_server_name"] = "other-agent.internal"
    with pytest.raises(ValidationError, match="server name"):
        DormantAgentIntakeEndpointV1.model_validate(endpoint_raw)


def test_valid_model_binds_all_released_fingerprints_and_is_inert(tmp_path: Path) -> None:
    value = preparation(tmp_path)
    assert value.request.envelope.linkage.candidate_record_fingerprint
    assert value.request.envelope.linkage.approval_intent_fingerprint
    assert value.request.envelope.linkage.agent_validation_fingerprint
    assert value.request.envelope.linkage.agent_evidence_fingerprint
    assert value.request.envelope.linkage.execution_request_fingerprint
    assert value.source.intake_simulation_evidence_fingerprint
    assert value.source.simulated_delivery_evidence_fingerprint
    assert value.source.simulated_acknowledgement_evidence_fingerprint
    assert validate_delivery_preparation(
        value,
        operator_id=OPERATOR,
        configuration=configuration(),
        validated_at=PREPARED_AT,
    ) == "disabled"
    assert preparation_lifecycle(value, now=PREPARED_AT) == "prepared_dormant"
    assert not any(
        (
            value.default_enabled,
            value.network_attempted,
            value.delivery_authorized,
            value.delivery_received,
            value.evidence_admission_granted,
            value.execution_admission_granted,
            value.execution_authorized,
            value.worker_allowed,
            value.mutation_allowed,
            value.replay_allowed,
        )
    )


def test_missing_changed_fingerprints_and_linkage_fail(tmp_path: Path) -> None:
    value = preparation(tmp_path)
    raw = value.model_dump(mode="json")
    del raw["source"]["intake_simulation_evidence_fingerprint"]
    with pytest.raises(ValidationError):
        CoreAgentIntakeDeliveryPreparationV1.model_validate(raw)
    raw = value.model_dump(mode="json")
    raw["source"]["intake_record_fingerprint"] = fingerprint("9").model_dump(
        mode="json"
    )
    with pytest.raises(ValidationError, match="prior evidence"):
        CoreAgentIntakeDeliveryPreparationV1.model_validate(raw)
    raw = value.model_dump(mode="json")
    del raw["request"]["envelope"]["linkage"]["approval_intent_fingerprint"]
    with pytest.raises(ValidationError):
        CoreAgentIntakeDeliveryPreparationV1.model_validate(raw)


def test_ownership_freshness_expiry_and_endpoint_fail_closed(tmp_path: Path) -> None:
    value = preparation(tmp_path)
    with pytest.raises(ValueError, match="ownership|fingerprint"):
        validate_delivery_preparation(
            value,
            operator_id="operator-b",
            configuration=configuration(),
            validated_at=PREPARED_AT,
        )
    with pytest.raises(ValueError, match="precedes"):
        validate_delivery_preparation(
            value,
            operator_id=OPERATOR,
            configuration=configuration(),
            validated_at="2026-08-27T12:00:01Z",
        )
    assert preparation_lifecycle(value, now=value.valid_until) == "expired"
    changed = configuration().model_copy(
        update={
            "endpoint": configuration().endpoint.model_copy(
                update={
                    "host": "other-agent.internal",
                    "tls_server_name": "other-agent.internal",
                }
            )
        }
    )
    with pytest.raises(ValueError, match="endpoint fingerprint"):
        validate_delivery_preparation(
            value,
            operator_id=OPERATOR,
            configuration=changed,
            validated_at=PREPARED_AT,
        )


def test_response_binds_v027_admission_and_acknowledgement(tmp_path: Path) -> None:
    prepared, validation = admitted_validation(tmp_path)
    assert validate_delivery_response(
        validation, preparation=prepared, operator_id=OPERATOR
    ) == validation
    assert validation.admission_fingerprint
    assert validation.acknowledgement_fingerprint
    assert validation.production_delivery_observed is False
    payload = validation.agent_result.model_dump_json()  # type: ignore[union-attr]
    assert parse_delivery_response_json(payload) == validation.agent_result
    with pytest.raises(StrictContractError):
        parse_delivery_response_json(payload[:-1] + ',"command":"run"}')

    raw = validation.model_dump(mode="json")
    raw["admission_fingerprint"] = fingerprint("0").model_dump(mode="json")
    raw["validation_fingerprint"] = response_validation_fingerprint(
        operator_id=OPERATOR, validation=raw
    ).model_dump(mode="json")
    changed = CoreAgentIntakeDeliveryResponseValidationV1.model_validate(raw)
    with pytest.raises(ValueError, match="acknowledgement evidence"):
        validate_delivery_response(changed, preparation=prepared, operator_id=OPERATOR)


def test_default_disabled_fixed_false_redaction_idempotency_and_result(
    tmp_path: Path,
) -> None:
    value = preparation(tmp_path)
    config_schema = DormantAgentIntakeDeliveryConfigurationV1.model_json_schema()
    for field in (
        "enabled",
        "agent_route_registered",
        "production_transport_registered",
        "production_delivery_allowed",
        "execution_authorized",
        "worker_allowed",
        "mutation_allowed",
        "replay_allowed",
    ):
        assert config_schema["properties"][field]["const"] is False
    error = CoreAgentIntakeDeliveryRedactedErrorV1(
        error_code="unavailable", correlation_id="wiring-1"
    )
    assert error.redacted is True
    assert "detail" not in error.model_dump()
    with pytest.raises(ValidationError):
        CoreAgentIntakeDeliveryRedactedErrorV1.model_validate(
            {**error.model_dump(mode="json"), "detail": "/run/secrets/token"}
        )
    reservation = CoreAgentIntakeDeliveryIdempotencyV1(
        operator_id=OPERATOR,
        key="wiring-key",
        dispatch_envelope_id=value.source.dispatch_envelope_id,
        dispatch_envelope_fingerprint=value.source.dispatch_envelope_fingerprint,
        delivery_preparation_id=value.delivery_preparation_id,
        preparation_fingerprint=value.preparation_fingerprint,
        intake_request_id=value.request.intake_request_id,
        request_fingerprint=value.request.request_fingerprint,
        delivery_attempt_id=value.request.delivery_attempt_id,
        source=value.source,
    )
    assert reservation.reservation_permanent and reservation.exact_retry_only
    assert reservation.replay_allowed is False
    result = CoreAgentIntakeDeliveryPreparationResultV1(
        disposition="prepared_dormant", preparation=value, error=None
    )
    assert result.network_attempted is False and result.agent_invoked is False


def test_audit_and_fingerprints_are_deterministic(tmp_path: Path) -> None:
    value = preparation(tmp_path)
    assert endpoint_fingerprint(configuration().endpoint) == endpoint_fingerprint(
        configuration().endpoint
    )
    assert preparation_fingerprint(
        operator_id=OPERATOR, preparation=value
    ) == preparation_fingerprint(operator_id=OPERATOR, preparation=value)
    assert preparation_fingerprint(
        operator_id=OPERATOR, preparation=value
    ) != preparation_fingerprint(operator_id="operator-b", preparation=value)
    audit_raw = {
        "schema": "core-agent-intake-delivery-audit-evidence-v1",
        "delivery_preparation_id": value.delivery_preparation_id,
        "preparation_fingerprint": value.preparation_fingerprint.model_dump(mode="json"),
        "intake_request_id": value.request.intake_request_id,
        "request_fingerprint": value.request.request_fingerprint.model_dump(mode="json"),
        "delivery_attempt_id": value.request.delivery_attempt_id,
        "dispatch_envelope_id": value.source.dispatch_envelope_id,
        "dispatch_envelope_fingerprint": value.source.dispatch_envelope_fingerprint.model_dump(
            mode="json"
        ),
        "prepared_at": value.prepared_at,
        "valid_until": value.valid_until,
        "validated_at": PREPARED_AT,
        "lifecycle": "disabled",
        "status": "not_sent",
        "provenance": "core_dormant_agent_intake_delivery_wiring_only",
        "default_enabled": False,
        "network_attempted": False,
        "delivery_authorized": False,
        "delivery_received": False,
        "evidence_admission_granted": False,
        "execution_admission_granted": False,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    audit_raw["evidence_fingerprint"] = audit_evidence_fingerprint(audit_raw).model_dump(
        mode="json"
    )
    audit = CoreAgentIntakeDeliveryAuditEvidenceV1.model_validate(audit_raw)
    assert audit.evidence_fingerprint == audit_evidence_fingerprint(audit)


def test_contract_has_no_forbidden_imports_or_effect_calls() -> None:
    path = Path(__file__).with_name("contract.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_modules = {
        "asyncio",
        "docker",
        "httpx",
        "os",
        "podman",
        "requests",
        "shlex",
        "socket",
        "ssl",
        "subprocess",
        "urllib",
    }
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imports.isdisjoint(forbidden_modules)
    forbidden_calls = {"open", "exec", "eval", "system", "run", "Popen"}
    assert not any(
        isinstance(node, ast.Call)
        and (
            getattr(node.func, "id", "") in forbidden_calls
            or getattr(node.func, "attr", "") in forbidden_calls
        )
        for node in ast.walk(tree)
    )
