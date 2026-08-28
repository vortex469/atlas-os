from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.agent_intake_simulation import (
    AgentInstallationIntakeSimulationCreateV1,
    AgentIntakeSimulationService,
    AgentIntakeSimulationStore,
    IntakeSimulationNotFoundError,
    IntakeSimulationUnavailableError,
    dispatch_envelope_fingerprint,
)

OPERATOR = "operator-a"


def fp(character: str) -> dict[str, str]:
    return {
        "algorithm": "sha256",
        "canonicalization": "atlas-jcs-nfc-v1",
        "value": character * 64,
    }


def create_raw(index: int = 1) -> dict[str, object]:
    identifier = f"{index:012x}"
    envelope: dict[str, object] = {
        "schema": "installation-dispatch-envelope-v1",
        "dispatch_envelope_id": f"00000000-0000-4000-8000-{identifier}",
        "prepared_at": "2026-08-28T12:00:00Z",
        "valid_until": "2026-08-28T12:01:00Z",
        "operation": "install-container",
        "mode": "handoff-only",
        "recipient": {
            "service": "atlas-agent",
            "intake_contract": "agent-installation-dispatch-intake-v1",
        },
        "linkage": {
            "candidate_record_id": "00000000-0000-4000-8000-000000000201",
            "candidate_envelope_fingerprint": fp("1"),
            "admission_fingerprint": fp("2"),
            "candidate_record_fingerprint": fp("3"),
            "approval_intent_id": "00000000-0000-4000-8000-000000000211",
            "approval_intent_fingerprint": fp("4"),
            "agent_request_id": "00000000-0000-4000-8000-000000000221",
            "agent_request_fingerprint": fp("5"),
            "agent_validation_fingerprint": fp("6"),
            "agent_evidence_fingerprint": fp("7"),
            "destination_fingerprint": "8" * 64,
            "source_plan_fingerprint": fp("9"),
            "artifact_policy_fingerprint": fp("a"),
            "execution_request_id": "00000000-0000-4000-8000-000000000231",
            "execution_request_fingerprint": fp("b"),
        },
        "statement": "core_prepared_non_executing_agent_handoff",
        "delivery_authorized": False,
        "agent_admission_authorized": False,
        "execution_authorized": False,
        "mutation_authorized": False,
        "replay_allowed": False,
    }
    envelope["dispatch_envelope_fingerprint"] = dispatch_envelope_fingerprint(
        operator_id=OPERATOR, envelope=envelope
    ).model_dump(mode="json")
    return {
        "schema": "agent-installation-intake-simulation-create-v1",
        "simulation_request_id": f"10000000-0000-4000-8000-{identifier}",
        "envelope": envelope,
    }


def service(path: Path, *, now: datetime | None = None) -> AgentIntakeSimulationService:
    current = now or datetime(2026, 8, 28, 12, 0, 10, tzinfo=UTC)
    return AgentIntakeSimulationService(
        store=AgentIntakeSimulationStore(path, clock=lambda: current), enabled=True
    )


def simulate(
    target: AgentIntakeSimulationService, raw: dict[str, object], key: str = "key-1"
):
    return target.simulate(
        json.dumps(raw),
        operator_id=OPERATOR,
        idempotency_key=key,
        correlation_id="correlation-1",
    )


def test_preserve_exact_retry_restart_owned_read_and_passive_expiry(tmp_path: Path) -> None:
    database = tmp_path / "simulation.sqlite3"
    first = simulate(service(database), create_raw())
    assert first.disposition == "simulated"
    assert first.validation is not None

    restarted = service(database, now=datetime(2026, 8, 28, 12, 0, 50, tzinfo=UTC))
    retry = simulate(restarted, create_raw())
    assert retry.disposition == "exact_replay"
    assert retry.validation == first.validation
    record_id = first.validation.record.intake_record_id
    assert (
        restarted.get(operator_id=OPERATOR, intake_record_id=record_id)
        == first.validation.record
    )
    assert restarted.lifecycle(operator_id=OPERATOR, intake_record_id=record_id) == "expired"
    with pytest.raises(IntakeSimulationNotFoundError):
        restarted.get(operator_id="operator-b", intake_record_id=record_id)


def test_idempotency_conflict_and_envelope_no_replay(tmp_path: Path) -> None:
    target = service(tmp_path / "simulation.sqlite3")
    assert simulate(target, create_raw()).disposition == "simulated"
    assert simulate(target, create_raw(2)).error.error_code == "replay_conflict"  # type: ignore[union-attr]
    same_envelope = create_raw()
    same_envelope["simulation_request_id"] = "20000000-0000-4000-8000-000000000001"
    assert simulate(target, same_envelope, "key-2").error.error_code == "replay_conflict"  # type: ignore[union-attr]


def test_default_disabled_stale_and_tampered_linkage_are_closed(tmp_path: Path) -> None:
    store = AgentIntakeSimulationStore(tmp_path / "simulation.sqlite3")
    disabled = AgentIntakeSimulationService(store=store)
    assert simulate(disabled, create_raw()).disposition == "unavailable"

    stale = service(
        tmp_path / "stale.sqlite3",
        now=datetime(2026, 8, 28, 12, 1, 0, tzinfo=UTC),
    )
    assert simulate(stale, create_raw()).error.error_code == "not_current"  # type: ignore[union-attr]
    tampered = deepcopy(create_raw())
    tampered["envelope"]["linkage"]["execution_request_fingerprint"] = fp("c")  # type: ignore[index]
    result = simulate(service(tmp_path / "tampered.sqlite3"), tampered)
    assert result.disposition == "rejected"
    assert result.error is not None and result.error.redacted is True
    assert result.validation is None


def test_quota_is_per_operator_and_has_no_eviction(tmp_path: Path) -> None:
    target = service(tmp_path / "simulation.sqlite3")
    for index in range(1, 17):
        assert simulate(target, create_raw(index), f"key-{index}").disposition == "simulated"
    result = simulate(target, create_raw(17), "key-17")
    assert result.error is not None and result.error.error_code == "quota_exceeded"


def test_corrupted_record_and_reservation_fail_closed_after_restart(tmp_path: Path) -> None:
    database = tmp_path / "simulation.sqlite3"
    accepted = simulate(service(database), create_raw())
    assert accepted.validation is not None
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE agent_intake_simulations SET record_json=?",
            ('{"corrupt":true}',),
        )
    restarted = service(database)
    with pytest.raises(IntakeSimulationUnavailableError):
        restarted.get(
            operator_id=OPERATOR,
            intake_record_id=accepted.validation.record.intake_record_id,
        )
    assert simulate(restarted, create_raw()).disposition == "unavailable"


def test_service_has_no_production_consumer_or_effect_adapter() -> None:
    package = Path("services/atlas-agent/app/agent_intake_simulation")
    source = "\n".join(path.read_text() for path in package.glob("*.py"))
    for forbidden in (
        "subprocess",
        "docker",
        "podman",
        "httpx",
        "requests",
        "core_client",
        "candidate_planning",
        "workflow",
        "worker",
        "provider",
        "repository",
    ):
        assert f"import {forbidden}" not in source
        assert f"from {forbidden}" not in source
    create = AgentInstallationIntakeSimulationCreateV1.model_validate(create_raw())
    assert create.envelope.execution_authorized is False
