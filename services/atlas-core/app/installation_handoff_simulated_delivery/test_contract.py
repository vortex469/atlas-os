from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_dispatch_handoff.test_contract import built
from app.installation_handoff_simulated_delivery.contract import (
    InstallationHandoffSimulatedDeliveryErrorV1,
    InstallationHandoffSimulatedDeliveryIdempotencyV1,
    StrictContractError,
    build_delivery_record,
    build_simulated_delivery,
    delivery_lifecycle,
    delivery_record_fingerprint,
    derived_agent_idempotency_key,
    parse_delivery_json,
    simulated_delivery_fingerprint,
    validate_simulated_delivery,
)

OPERATOR = "operator-a"
DELIVERY_ID = "00000000-0000-4000-8000-000000000601"
SIMULATION_ID = "00000000-0000-4000-8000-000000000602"


def delivery(tmp_path: Path):
    envelope, _ = built(tmp_path)
    return build_simulated_delivery(
        operator_id=OPERATOR,
        simulated_delivery_id=DELIVERY_ID,
        simulation_request_id=SIMULATION_ID,
        dispatched_at="2026-08-27T12:00:02Z",
        envelope=envelope,
    )


def test_delivery_and_record_are_closed_immutable_and_deterministic(tmp_path: Path) -> None:
    value = delivery(tmp_path)
    assert value.simulated_delivery_fingerprint == simulated_delivery_fingerprint(
        operator_id=OPERATOR, delivery=value
    )
    assert parse_delivery_json(json.dumps(value.model_dump(mode="json"))) == value
    with pytest.raises(ValidationError):
        value.mode = "live"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        type(value).model_validate({**value.model_dump(), "endpoint": "x"})
    payload = json.dumps(value.model_dump(mode="json"))
    with pytest.raises(StrictContractError):
        parse_delivery_json(payload[:-1] + ',"schema":"duplicate"}')

    record = build_delivery_record(operator_id=OPERATOR, delivery=value)
    assert record.delivery_record_fingerprint == delivery_record_fingerprint(
        operator_id=OPERATOR, record=record
    )
    assert delivery_lifecycle(record, now=record.dispatched_at) == "pending_acknowledgement"
    assert delivery_lifecycle(record, now=record.valid_until) == "expired_unacknowledged"


def test_ownership_freshness_linkage_and_false_authority(tmp_path: Path) -> None:
    value = delivery(tmp_path)
    with pytest.raises(ValueError, match="ownership|fingerprint"):
        validate_simulated_delivery(value, operator_id="operator-b", now=value.dispatched_at)
    with pytest.raises(ValueError, match="precedes"):
        validate_simulated_delivery(
            value, operator_id=OPERATOR, now="2026-08-27T12:00:01Z"
        )
    with pytest.raises(ValueError, match="not current"):
        validate_simulated_delivery(value, operator_id=OPERATOR, now=value.valid_until)
    raw = value.model_dump(mode="json")
    del raw["envelope"]["linkage"]["approval_intent_fingerprint"]
    with pytest.raises(ValidationError):
        type(value).model_validate(raw)
    for field in (
        "delivery_authorized", "live_admission_authorized", "execution_authorized",
        "worker_allowed", "mutation_allowed", "replay_allowed",
    ):
        assert type(value).model_json_schema()["properties"][field]["const"] is False


def test_redacted_error_no_replay_and_derived_key(tmp_path: Path) -> None:
    value = delivery(tmp_path)
    error = InstallationHandoffSimulatedDeliveryErrorV1(
        error_code="linkage_mismatch", correlation_id="delivery-1"
    )
    assert error.redacted is True and "detail" not in error.model_dump()
    reservation = InstallationHandoffSimulatedDeliveryIdempotencyV1(
        operator_id=OPERATOR,
        key="request-key",
        simulated_delivery_id=value.simulated_delivery_id,
        simulated_delivery_fingerprint=value.simulated_delivery_fingerprint,
        simulation_request_id=value.simulation_request_id,
        dispatch_envelope_id=value.envelope.dispatch_envelope_id,
        dispatch_envelope_fingerprint=value.envelope.dispatch_envelope_fingerprint,
    )
    assert reservation.replay_allowed is False
    assert derived_agent_idempotency_key(value) == (
        "v026:" + value.simulated_delivery_fingerprint.value
    )
    assert len(derived_agent_idempotency_key(value)) == 69


def test_contract_has_no_forbidden_imports_or_calls() -> None:
    path = Path(__file__).with_name("contract.py")
    tree = ast.parse(path.read_text())
    forbidden = {"httpx", "requests", "subprocess", "socket", "docker", "podman"}
    imports = {
        node.names[0].name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
    }
    assert imports.isdisjoint(forbidden)
    assert not any(isinstance(node, ast.Call) and getattr(node.func, "id", "") in {"open", "exec"} for node in ast.walk(tree))
