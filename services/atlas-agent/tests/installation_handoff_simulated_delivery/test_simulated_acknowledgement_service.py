from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.agent_intake_simulation import (
    AgentIntakeSimulationService,
    AgentIntakeSimulationStore,
)
from app.installation_handoff_simulated_delivery import (
    AgentSimulatedAcknowledgementService,
    AgentSimulatedAcknowledgementStore,
    InstallationHandoffSimulatedDeliveryV1,
    simulated_delivery_fingerprint,
)
from tests.installation_handoff_simulated_delivery.test_simulated_handoff_delivery_models import (
    OPERATOR,
    values,
)

NOW = datetime(2026, 8, 28, 12, 0, 10, tzinfo=UTC)


def adapter(
    root: Path,
    *,
    enabled: bool = True,
    index: int = 3,
) -> AgentSimulatedAcknowledgementService:
    intake = AgentIntakeSimulationService(
        store=AgentIntakeSimulationStore(
            root / "intake.sqlite3",
            clock=lambda: NOW,
            id_factory=lambda: uuid.UUID(f"00000000-0000-4000-8000-{index + 500:012x}"),
        ),
        enabled=True,
    )
    return AgentSimulatedAcknowledgementService(
        store=AgentSimulatedAcknowledgementStore(
            root / "ack.sqlite3",
            clock=lambda: NOW,
            id_factory=lambda: uuid.UUID(f"00000000-0000-4000-8000-{index + 600:012x}"),
        ),
        intake_service=intake,
        enabled=enabled,
    )


def changed(delivery: InstallationHandoffSimulatedDeliveryV1, **updates: object):
    raw = delivery.model_dump(mode="json")
    raw.update(updates)
    raw.pop("simulated_delivery_fingerprint", None)
    raw["simulated_delivery_fingerprint"] = simulated_delivery_fingerprint(
        operator_id=OPERATOR, delivery=raw
    ).model_dump(mode="json")
    return InstallationHandoffSimulatedDeliveryV1.model_validate(raw)


def test_preserve_read_exact_replay_restart_and_passive_expiry(tmp_path: Path) -> None:
    delivery, _ = values()
    first_service = adapter(tmp_path)
    first = first_service.simulate(
        delivery, operator_id=OPERATOR, correlation_id="correlation-1"
    )
    assert first.disposition == "simulated"
    assert first.acknowledgement is not None
    assert first.acknowledgement.acknowledged_at == "2026-08-28T12:00:10Z"
    assert (
        first_service.get(
            operator_id=OPERATOR, simulated_delivery_id=delivery.simulated_delivery_id
        )
        == first.acknowledgement
    )

    replay = first_service.simulate(
        delivery, operator_id=OPERATOR, correlation_id="correlation-2"
    )
    assert replay.disposition == "exact_replay"
    assert replay.acknowledgement == first.acknowledgement

    restarted = adapter(tmp_path)
    assert (
        restarted.get(
            operator_id=OPERATOR, simulated_delivery_id=delivery.simulated_delivery_id
        )
        == first.acknowledgement
    )
    restarted._store._clock = lambda: datetime(2026, 8, 28, 12, 0, 40, tzinfo=UTC)
    assert (
        restarted.lifecycle(
            operator_id=OPERATOR, simulated_delivery_id=delivery.simulated_delivery_id
        )
        == "expired_acknowledged"
    )
    with sqlite3.connect(tmp_path / "ack.sqlite3") as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM agent_simulated_acknowledgements"
            ).fetchone()[0]
            == 1
        )


def test_default_disabled_is_closed_and_fixed_false(tmp_path: Path) -> None:
    delivery, _ = values()
    result = adapter(tmp_path, enabled=False).simulate(
        delivery, operator_id=OPERATOR, correlation_id="correlation-1"
    )
    assert result.disposition == "unavailable"
    assert result.error is not None and result.error.redacted is True
    assert result.acknowledgement is None
    for field in (
        "delivery_received",
        "live_admission_attempted",
        "execution_attempted",
        "worker_invoked",
        "mutation_attempted",
    ):
        assert getattr(result, field) is False


def test_delivery_conflict_no_replay_ownership_and_staleness(tmp_path: Path) -> None:
    delivery, _ = values()
    service = adapter(tmp_path)
    assert (
        service.simulate(
            delivery, operator_id=OPERATOR, correlation_id="correlation-1"
        ).disposition
        == "simulated"
    )

    conflict = changed(
        delivery, simulation_request_id="00000000-0000-4000-8000-000000000699"
    )
    result = service.simulate(
        conflict, operator_id=OPERATOR, correlation_id="correlation-2"
    )
    assert result.error is not None and result.error.error_code == "replay_conflict"

    second_identity = changed(
        delivery, simulated_delivery_id="00000000-0000-4000-8000-000000000698"
    )
    result = service.simulate(
        second_identity, operator_id=OPERATOR, correlation_id="correlation-3"
    )
    assert result.error is not None and result.error.error_code == "replay_conflict"

    foreign = adapter(tmp_path / "foreign").simulate(
        delivery, operator_id="operator-b", correlation_id="correlation-4"
    )
    assert (
        foreign.error is not None and foreign.error.error_code == "ownership_mismatch"
    )

    stale_root = tmp_path / "stale"
    stale_service = adapter(stale_root)
    stale_service._intake_service._store._clock = lambda: datetime(
        2026, 8, 28, 12, 1, tzinfo=UTC
    )
    stale = stale_service.simulate(
        delivery, operator_id=OPERATOR, correlation_id="correlation-5"
    )
    assert stale.error is not None and stale.error.error_code == "not_current"


def test_quota_corruption_and_bounded_record_fail_closed(tmp_path: Path) -> None:
    delivery, _ = values()
    service = adapter(tmp_path)
    first = service.simulate(
        delivery, operator_id=OPERATOR, correlation_id="correlation-1"
    )
    assert first.acknowledgement is not None
    with sqlite3.connect(tmp_path / "ack.sqlite3") as connection:
        connection.execute(
            "UPDATE agent_simulated_acknowledgements SET acknowledgement_json=?",
            ("{" + "x" * (16 * 1024) + "}",),
        )
    corrupted = service.simulate(
        delivery, operator_id=OPERATOR, correlation_id="correlation-2"
    )
    assert corrupted.disposition == "unavailable"
    assert corrupted.error is not None and corrupted.error.error_code == "unavailable"

    quota_root = tmp_path / "quota"
    quota_service = adapter(quota_root)
    with sqlite3.connect(quota_root / "ack.sqlite3") as connection:
        acknowledgement = first.acknowledgement.model_dump(mode="json")
        for index in range(16):
            suffix = f"{index + 1000:012x}"
            acknowledgement["acknowledgement_id"] = f"00000000-0000-4000-8000-{suffix}"
            acknowledgement["source"]["simulated_delivery_id"] = (
                f"10000000-0000-4000-8000-{suffix}"
            )
            acknowledgement["source"]["simulated_delivery_fingerprint"]["value"] = (
                f"{index:064x}"
            )
            acknowledgement["acknowledgement_fingerprint"]["value"] = (
                f"{index + 20:064x}"
            )
            acknowledgement["intake"]["simulation_request_id"] = (
                f"20000000-0000-4000-8000-{suffix}"
            )
            acknowledgement["intake"]["intake_record_id"] = (
                f"30000000-0000-4000-8000-{suffix}"
            )
            acknowledgement["intake"]["intake_record_fingerprint"]["value"] = (
                f"{index + 40:064x}"
            )
            acknowledgement["source"]["dispatch_envelope_id"] = (
                f"40000000-0000-4000-8000-{suffix}"
            )
            acknowledgement["source"]["dispatch_envelope_fingerprint"]["value"] = (
                f"{index + 60:064x}"
            )
            connection.execute(
                "INSERT INTO agent_simulated_acknowledgements VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    acknowledgement["acknowledgement_id"],
                    OPERATOR,
                    acknowledgement["source"]["simulated_delivery_id"],
                    acknowledgement["source"]["simulated_delivery_fingerprint"][
                        "value"
                    ],
                    acknowledgement["acknowledgement_fingerprint"]["value"],
                    acknowledgement["intake"]["simulation_request_id"],
                    acknowledgement["intake"]["intake_record_id"],
                    acknowledgement["intake"]["intake_record_fingerprint"]["value"],
                    acknowledgement["source"]["dispatch_envelope_id"],
                    acknowledgement["source"]["dispatch_envelope_fingerprint"]["value"],
                    "{}",
                ),
            )
    full = quota_service.simulate(
        delivery, operator_id=OPERATOR, correlation_id="correlation-3"
    )
    assert full.error is not None and full.error.error_code == "quota_exceeded"


def test_adapter_has_no_forbidden_consumers_or_runtime_calls() -> None:
    root = Path(__file__).parents[2] / "app/installation_handoff_simulated_delivery"
    source = "\n".join(path.read_text() for path in root.glob("*.py"))
    for forbidden in (
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "docker",
        "podman",
        "workflow",
        "worker.dispatch",
        "provider",
        "repository",
        "atlas_core",
    ):
        assert forbidden not in source.lower()
