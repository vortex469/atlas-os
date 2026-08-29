"""P2 tests for the explicitly constructed dormant no-send client."""

from __future__ import annotations

import ast
import builtins
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.dormant_agent_intake_delivery_wiring import (
    CoreAgentIntakeDeliveryCreateV1,
    CoreAgentIntakeDeliveryEvidenceContextV1,
    DormantAgentIntakeDeliveryPreparationStore,
    DormantDeliveryStoreError,
    create_dormant_agent_intake_delivery_client,
)
from app.dormant_agent_intake_delivery_wiring.test_contract import (
    ADMISSION_ID,
    DELIVERY_ATTEMPT_ID,
    INTAKE_RECORD_ID,
    INTAKE_REQUEST_ID,
    OPERATOR,
    PREPARATION_ID,
    SIMULATED_ACK_ID,
    SIMULATED_DELIVERY_ID,
    admitted_validation,
    configuration,
    fingerprint,
    preparation,
)


class EvidenceReader:
    def __init__(self, context: CoreAgentIntakeDeliveryEvidenceContextV1) -> None:
        self.context = context
        self.calls = 0

    def resolve(self, *, operator_id: str, create: CoreAgentIntakeDeliveryCreateV1):
        self.calls += 1
        return self.context


def context(tmp_path: Path, **updates: object) -> CoreAgentIntakeDeliveryEvidenceContextV1:
    expected = preparation(tmp_path)
    raw = {
        "operator_id": OPERATOR,
        "envelope": expected.request.envelope.model_dump(mode="json"),
        "simulation_request_id": expected.request.prior_evidence.intake_simulation.simulation_request_id,
        "source": expected.source.model_dump(mode="json"),
        "intake_record_observed_at": "2026-08-27T12:00:01Z",
        "simulated_acknowledged_at": "2026-08-27T12:00:01Z",
        "existing_admission_id": None,
        "existing_admission_fingerprint": None,
        "existing_acknowledgement_fingerprint": None,
        "default_enabled": False,
        "production_delivery_observed": False,
        "execution_authorized": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw.update(updates)
    return CoreAgentIntakeDeliveryEvidenceContextV1.model_validate(raw)


def create(tmp_path: Path) -> CoreAgentIntakeDeliveryCreateV1:
    value = context(tmp_path)
    return CoreAgentIntakeDeliveryCreateV1(
        dispatch_envelope_id=value.source.dispatch_envelope_id,
        intake_record_id=INTAKE_RECORD_ID,
        simulated_delivery_id=SIMULATED_DELIVERY_ID,
        simulated_acknowledgement_id=SIMULATED_ACK_ID,
    )


def client(tmp_path: Path, *, evidence: CoreAgentIntakeDeliveryEvidenceContextV1 | None = None):
    reader = EvidenceReader(evidence or context(tmp_path))
    identifiers = iter((INTAKE_REQUEST_ID, DELIVERY_ATTEMPT_ID, PREPARATION_ID))
    value = create_dormant_agent_intake_delivery_client(
        configuration=configuration(),
        evidence_reader=reader,
        preparation_store=DormantAgentIntakeDeliveryPreparationStore(
            tmp_path / "dormant-wiring.sqlite3"
        ),
        clock=lambda: datetime(2026, 8, 27, 12, 0, 2, tzinfo=UTC),
        id_factory=lambda: next(identifiers),
    )
    return value, reader


def preserve(value, create_value, *, operator: str = OPERATOR, key: str = "wiring-key"):
    return value.prepare(
        create_value,
        authenticated_operator_id=operator,
        idempotency_key=key,
        correlation_id="wiring-1",
    )


def test_valid_no_send_preparation_and_deterministic_audit(tmp_path: Path) -> None:
    value, reader = client(tmp_path)
    result = preserve(value, create(tmp_path))
    assert result.disposition == "prepared_dormant"
    assert result.preparation is not None and result.audit_evidence is not None
    assert result.preparation.status == "not_sent"
    assert result.preparation.request.sent_at == "2026-08-27T12:00:02Z"
    assert result.audit_evidence.status == "not_sent"
    assert result.audit_evidence.evidence_fingerprint
    assert reader.calls == 1
    assert not any(
        (
            result.network_attempted,
            result.agent_invoked,
            result.execution_attempted,
            result.mutation_attempted,
            result.preparation.network_attempted,
            result.audit_evidence.network_attempted,
            result.audit_evidence.delivery_authorized,
            result.audit_evidence.execution_authorized,
            result.audit_evidence.mutation_allowed,
        )
    )


def test_exact_retry_is_byte_identical_without_evidence_or_id_reread(tmp_path: Path) -> None:
    value, reader = client(tmp_path)
    first = preserve(value, create(tmp_path))
    second = preserve(value, create(tmp_path))
    assert first.preparation == second.preparation
    assert first.audit_evidence == second.audit_evidence
    assert second.disposition == "exact_replay"
    assert reader.calls == 1


def test_idempotency_and_one_envelope_no_replay_conflicts(tmp_path: Path) -> None:
    value, reader = client(tmp_path)
    create_value = create(tmp_path)
    assert preserve(value, create_value).preparation is not None
    changed = create_value.model_copy(
        update={
            "simulated_acknowledgement_id": "00000000-0000-4000-8000-000000000899"
        }
    )
    conflict = preserve(value, changed, key="other-key")
    assert conflict.disposition == "rejected"
    assert conflict.error is not None and conflict.error.error_code == "replay_conflict"
    assert conflict.error.redacted is True
    assert reader.calls == 1


def test_ownership_linkage_existing_admission_and_staleness_fail_closed(
    tmp_path: Path,
) -> None:
    value, _ = client(tmp_path)
    ownership = preserve(value, create(tmp_path), operator="operator-b")
    assert ownership.preparation is None
    assert ownership.error is not None and ownership.error.redacted

    mismatch_context = context(tmp_path)
    mismatch_create = create(tmp_path).model_copy(
        update={"intake_record_id": "00000000-0000-4000-8000-000000000898"}
    )
    mismatch_client, _ = client(tmp_path / "mismatch", evidence=mismatch_context)
    assert preserve(mismatch_client, mismatch_create).preparation is None

    existing = context(
        tmp_path,
        existing_admission_id=ADMISSION_ID,
        existing_admission_fingerprint=fingerprint("8"),
        existing_acknowledgement_fingerprint=fingerprint("9"),
    )
    existing_client, _ = client(tmp_path / "existing", evidence=existing)
    assert preserve(existing_client, create(tmp_path)).preparation is None

    stale_client = create_dormant_agent_intake_delivery_client(
        configuration=configuration(),
        evidence_reader=EvidenceReader(context(tmp_path)),
        preparation_store=DormantAgentIntakeDeliveryPreparationStore(
            tmp_path / "stale.sqlite3"
        ),
        clock=lambda: datetime(2026, 8, 27, 12, 2, 0, tzinfo=UTC),
        id_factory=lambda: INTAKE_REQUEST_ID,
    )
    stale = preserve(stale_client, create(tmp_path))
    assert stale.preparation is None and stale.error is not None


def test_configuration_is_disabled_and_secret_material_is_never_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value, _ = client(tmp_path)
    assert value.configuration.enabled is False
    assert value.configuration.production_transport_registered is False
    assert value.configuration.production_delivery_allowed is False
    assert value.configuration.authentication.credential_file.endswith("-token")
    create_value = create(tmp_path)

    def forbidden_open(*args: object, **kwargs: object):
        raise AssertionError("secret material must not be opened")

    monkeypatch.setattr(builtins, "open", forbidden_open)
    result = preserve(value, create_value)
    assert result.preparation is not None


def test_owned_readback_restart_and_corruption_fail_closed(tmp_path: Path) -> None:
    value, _ = client(tmp_path)
    result = preserve(value, create(tmp_path))
    assert result.preparation is not None
    assert value.get_preparation(
        authenticated_operator_id=OPERATOR,
        delivery_preparation_id=result.preparation.delivery_preparation_id,
    ) == result.preparation
    with pytest.raises(DormantDeliveryStoreError, match="unavailable"):
        value.get_preparation(
            authenticated_operator_id="operator-b",
            delivery_preparation_id=result.preparation.delivery_preparation_id,
        )
    with sqlite3.connect(tmp_path / "dormant-wiring.sqlite3") as connection:
        connection.execute(
            "UPDATE dormant_agent_intake_preparations SET preparation_json = ?",
            ("{}",),
        )
    with pytest.raises(DormantDeliveryStoreError, match="unavailable"):
        value.get_preparation(
            authenticated_operator_id=OPERATOR,
            delivery_preparation_id=result.preparation.delivery_preparation_id,
        )


def test_no_send_injected_response_validation_only(tmp_path: Path) -> None:
    prepared, validation = admitted_validation(tmp_path)
    value, _ = client(tmp_path / "response")
    assert value.validate_response(
        validation,
        preparation=prepared,
        authenticated_operator_id=OPERATOR,
    ) == validation
    for name in (
        "send",
        "deliver",
        "post",
        "request",
        "retry",
        "reconcile",
        "execute",
        "install",
        "deploy",
        "rollback",
        "dispatch",
        "start_workflow",
    ):
        assert not hasattr(value, name)


def test_bounds_and_redaction_fail_closed(tmp_path: Path) -> None:
    value, _ = client(tmp_path)
    bad = preserve(value, create(tmp_path), key=" ")
    assert bad.preparation is None and bad.error is not None
    assert bad.error.redacted is True
    dumped = bad.error.model_dump()
    assert "detail" not in dumped
    assert "credential" not in dumped
    assert "endpoint" not in dumped


def test_no_production_registration_or_consumer() -> None:
    app_root = Path(__file__).parents[1]
    package_root = Path(__file__).parent
    inspected = (
        app_root / "main.py",
        app_root / "api" / "v1" / "router.py",
        app_root / "config" / "settings.py",
        app_root / "container.py",
    )
    markers = (
        "dormant_agent_intake_delivery_wiring",
        "create_dormant_agent_intake_delivery_client",
        "DormantAgentIntakeDeliveryClient",
    )
    assert [
        f"{path.name}:{marker}"
        for path in inspected
        if path.exists()
        for marker in markers
        if marker in path.read_text(encoding="utf-8")
    ] == []
    assert package_root.exists()


def test_client_and_store_have_no_network_runtime_or_mutation_dependencies() -> None:
    root = Path(__file__).parent
    forbidden_modules = {
        "asyncio",
        "docker",
        "http",
        "httpx",
        "podman",
        "requests",
        "shlex",
        "socket",
        "ssl",
        "subprocess",
        "urllib",
    }
    forbidden_calls = {
        "create_connection",
        "getaddrinfo",
        "open",
        "Popen",
        "request",
        "run",
        "system",
    }
    violations: list[str] = []
    for path in (root / "client.py", root / "store.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
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
        violations.extend(
            f"{path.name}:import:{name}"
            for name in imports.intersection(forbidden_modules)
        )
        violations.extend(
            f"{path.name}:call:{getattr(node.func, 'attr', '')}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (
                getattr(node.func, "id", "") in forbidden_calls
                or getattr(node.func, "attr", "") in forbidden_calls
            )
        )
    assert violations == []
