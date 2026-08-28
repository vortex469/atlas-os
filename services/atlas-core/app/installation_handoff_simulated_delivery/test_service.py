from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.installation_handoff_simulated_delivery.contract import (
    AgentInstallationHandoffSimulatedAcknowledgementV1,
    acknowledgement_fingerprint,
    build_simulated_delivery,
)
from app.installation_handoff_simulated_delivery.service import (
    InstallationHandoffSimulatedDeliveryService,
)
from app.installation_handoff_simulated_delivery.store import (
    InstallationHandoffSimulatedDeliveryStore,
    SimulatedHandoffUnavailableError,
)
from app.installation_handoff_simulated_delivery.test_contract import OPERATOR, delivery

ACK_ID = "00000000-0000-4000-8000-000000000603"
INTAKE_ID = "00000000-0000-4000-8000-000000000604"


def clock(second: int = 2):
    return lambda: datetime(2026, 8, 27, 12, 0, second, tzinfo=UTC)


def acknowledgement(value, *, acknowledgement_id: str = ACK_ID):
    raw = {
        "schema": "agent-installation-handoff-simulated-acknowledgement-v1",
        "acknowledgement_id": acknowledgement_id,
        "acknowledged_at": "2026-08-27T12:00:03Z",
        "valid_until": "2026-08-27T12:00:33Z",
        "status": "simulated_acknowledged",
        "provenance": "agent_simulated_not_received",
        "source": {
            "simulated_delivery_id": value.simulated_delivery_id,
            "simulated_delivery_fingerprint": value.simulated_delivery_fingerprint.model_dump(
                mode="json"
            ),
            "dispatch_envelope_id": value.envelope.dispatch_envelope_id,
            "dispatch_envelope_fingerprint": value.envelope.dispatch_envelope_fingerprint.model_dump(
                mode="json"
            ),
        },
        "intake": {
            "simulation_request_id": value.simulation_request_id,
            "intake_record_id": INTAKE_ID,
            "intake_record_fingerprint": {
                "algorithm": "sha256",
                "canonicalization": "atlas-jcs-nfc-v1",
                "value": "a" * 64,
            },
        },
        "statement": "agent_acknowledged_simulated_handoff_without_live_receipt",
        "delivery_received": False,
        "live_admission_granted": False,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["acknowledgement_fingerprint"] = acknowledgement_fingerprint(
        operator_id=OPERATOR, acknowledgement=raw
    ).model_dump(mode="json")
    return AgentInstallationHandoffSimulatedAcknowledgementV1.model_validate(raw)


class FakeAgent:
    def __init__(self, value) -> None:
        self.value = value
        self.calls = 0

    def simulate(self, delivery, *, operator_id, correlation_id):
        assert operator_id == OPERATOR
        assert correlation_id == "corr-1"
        assert delivery.simulated_delivery_id == self.value.source.simulated_delivery_id
        self.calls += 1
        return self.value


def service(tmp_path: Path, value, *, enabled: bool = True):
    observations = iter((clock(2)(), clock(3)()))
    store = InstallationHandoffSimulatedDeliveryStore(
        tmp_path / "delivery.sqlite3", clock=lambda: next(observations, clock(3)())
    )
    agent = FakeAgent(acknowledgement(value))
    return (
        InstallationHandoffSimulatedDeliveryService(
            store=store, agent_port=agent, enabled=enabled
        ),
        store,
        agent,
    )


def test_simulate_preserve_exact_retry_and_restart_read(tmp_path: Path) -> None:
    value = delivery(tmp_path)
    coordinator, _store, agent = service(tmp_path, value)
    first = coordinator.simulate(
        value,
        operator_id=OPERATOR,
        idempotency_key="delivery-key",
        correlation_id="corr-1",
    )
    replay = coordinator.simulate(
        value,
        operator_id=OPERATOR,
        idempotency_key="delivery-key",
        correlation_id="corr-1",
    )
    assert first.disposition == "simulated"
    assert replay.disposition == "exact_replay"
    assert replay.record == first.record
    assert replay.acknowledgement == first.acknowledgement
    assert agent.calls == 1

    restarted = InstallationHandoffSimulatedDeliveryStore(
        tmp_path / "delivery.sqlite3",
        clock=lambda: datetime(2026, 8, 27, 12, 1, 2, tzinfo=UTC),
    )
    assert restarted.get_attempt(
        operator_id=OPERATOR, simulated_delivery_id=value.simulated_delivery_id
    ) == first.record
    assert restarted.get_acknowledgement(
        operator_id=OPERATOR, simulated_delivery_id=value.simulated_delivery_id
    ) == first.acknowledgement
    assert restarted.lifecycle(
        operator_id=OPERATOR, simulated_delivery_id=value.simulated_delivery_id
    ) == "expired_acknowledged"


def test_default_disabled_and_conflicts_are_closed(tmp_path: Path) -> None:
    value = delivery(tmp_path)
    disabled, _store, agent = service(tmp_path, value, enabled=False)
    result = disabled.simulate(
        value,
        operator_id=OPERATOR,
        idempotency_key="delivery-key",
        correlation_id="corr-1",
    )
    assert result.disposition == "unavailable"
    assert result.error and result.error.redacted is True
    assert agent.calls == 0

    coordinator, _store, agent = service(tmp_path, value)
    assert coordinator.simulate(
        value,
        operator_id=OPERATOR,
        idempotency_key="delivery-key",
        correlation_id="corr-1",
    ).disposition == "simulated"
    changed = build_simulated_delivery(
        operator_id=OPERATOR,
        simulated_delivery_id="00000000-0000-4000-8000-000000000611",
        simulation_request_id=value.simulation_request_id,
        dispatched_at=value.dispatched_at,
        envelope=value.envelope,
    )
    conflict = coordinator.simulate(
        changed,
        operator_id=OPERATOR,
        idempotency_key="delivery-key",
        correlation_id="corr-1",
    )
    assert conflict.error and conflict.error.error_code == "replay_conflict"
    assert agent.calls == 1


def test_ownership_no_replay_and_corruption_fail_closed(tmp_path: Path) -> None:
    value = delivery(tmp_path)
    coordinator, store, _agent = service(tmp_path, value)
    mismatch = coordinator.simulate(
        value,
        operator_id="operator-b",
        idempotency_key="delivery-key",
        correlation_id="corr-1",
    )
    assert mismatch.error and mismatch.error.error_code == "ownership_mismatch"

    assert coordinator.simulate(
        value,
        operator_id=OPERATOR,
        idempotency_key="delivery-key",
        correlation_id="corr-1",
    ).disposition == "simulated"
    with sqlite3.connect(store.database_path) as connection:
        connection.execute(
            "UPDATE simulated_handoff_attempts SET record_json='{}'"
        )
    with pytest.raises(SimulatedHandoffUnavailableError):
        store.get_attempt(
            operator_id=OPERATOR, simulated_delivery_id=value.simulated_delivery_id
        )
