from __future__ import annotations

from pathlib import Path

import pytest
from app.agent_intake_simulation import (
    AgentInstallationIntakeSimulationCreateV1,
    validate_simulated_intake,
)
from app.installation_handoff_simulated_delivery.models import (
    AgentInstallationHandoffSimulatedAcknowledgementV1,
    InstallationHandoffSimulatedDeliveryV1,
    acknowledgement_fingerprint,
    acknowledgement_lifecycle,
    build_acknowledgement,
    derived_intake_idempotency_key,
    simulated_delivery_fingerprint,
    validate_simulated_delivery,
)
from pydantic import ValidationError
from tests.agent_intake_simulation.test_agent_intake_simulation_models import (
    OPERATOR,
    create_dict,
)

DELIVERY_ID = "00000000-0000-4000-8000-000000000601"
ACK_ID = "00000000-0000-4000-8000-000000000603"


def values():
    create = AgentInstallationIntakeSimulationCreateV1.model_validate(create_dict())
    raw = {
        "schema": "installation-handoff-simulated-delivery-v1",
        "simulated_delivery_id": DELIVERY_ID,
        "simulation_request_id": create.simulation_request_id,
        "dispatched_at": "2026-08-28T12:00:05Z",
        "valid_until": create.envelope.valid_until,
        "operation": "install-container", "mode": "simulation-only", "sender": "atlas-core",
        "recipient": {"service": "atlas-agent", "intake_contract": "agent-installation-intake-simulation-v1"},
        "envelope": create.envelope.model_dump(mode="json"),
        "delivery_authorized": False, "live_admission_authorized": False,
        "execution_authorized": False, "worker_allowed": False,
        "mutation_allowed": False, "replay_allowed": False,
    }
    raw["simulated_delivery_fingerprint"] = simulated_delivery_fingerprint(
        operator_id=OPERATOR, delivery=raw
    ).model_dump(mode="json")
    delivery = InstallationHandoffSimulatedDeliveryV1.model_validate(raw)
    validation = validate_simulated_intake(
        create, operator_id=OPERATOR, observed_at="2026-08-28T12:00:10Z",
        intake_record_id="00000000-0000-4000-8000-000000000502",
    )
    acknowledgement = build_acknowledgement(
        operator_id=OPERATOR, delivery=delivery,
        intake_record=validation.record, acknowledgement_id=ACK_ID,
    )
    return delivery, acknowledgement


def test_valid_acknowledgement_is_closed_immutable_and_exactly_linked() -> None:
    delivery, acknowledgement = values()
    assert acknowledgement.acknowledged_at == "2026-08-28T12:00:10Z"
    assert acknowledgement.valid_until == "2026-08-28T12:00:40Z"
    assert acknowledgement.intake.simulation_request_id == delivery.simulation_request_id
    assert acknowledgement.acknowledgement_fingerprint == acknowledgement_fingerprint(
        operator_id=OPERATOR, acknowledgement=acknowledgement
    )
    assert acknowledgement_lifecycle(acknowledgement, now=acknowledgement.acknowledged_at) == "simulated_acknowledged"
    assert acknowledgement_lifecycle(acknowledgement, now=acknowledgement.valid_until) == "expired_acknowledged"
    with pytest.raises(ValidationError):
        acknowledgement.status = "received"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        AgentInstallationHandoffSimulatedAcknowledgementV1.model_validate(
            {**acknowledgement.model_dump(), "receipt": True}
        )


def test_ownership_staleness_no_replay_and_fixed_false_authority() -> None:
    delivery, acknowledgement = values()
    with pytest.raises(ValueError, match="ownership|fingerprint"):
        validate_simulated_delivery(
            delivery, operator_id="operator-b", observed_at=acknowledgement.acknowledged_at
        )
    with pytest.raises(ValueError, match="not current"):
        validate_simulated_delivery(
            delivery, operator_id=OPERATOR, observed_at=delivery.valid_until
        )
    assert derived_intake_idempotency_key(delivery) == "v026:" + delivery.simulated_delivery_fingerprint.value
    assert len(derived_intake_idempotency_key(delivery)) == 69
    for field in (
        "delivery_received", "live_admission_granted", "execution_authorized",
        "worker_allowed", "mutation_allowed", "replay_allowed",
    ):
        assert type(acknowledgement).model_json_schema()["properties"][field]["const"] is False


def test_models_have_no_forbidden_dependencies() -> None:
    source = Path(__file__).parents[2] / "app/installation_handoff_simulated_delivery/models.py"
    text = source.read_text()
    for forbidden in ("httpx", "requests", "subprocess", "socket", "docker", "podman", "workflow"):
        assert forbidden not in text
