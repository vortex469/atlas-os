from __future__ import annotations

import ast
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.operator_controlled_delivery_enablement.contract import (
    OperatorControlledDeliveryEnablementConfigurationV1,
    OperatorControlledDeliveryEnablementCreateV1,
    OperatorControlledDeliveryEnablementEvidenceV1,
)
from app.operator_controlled_delivery_enablement.service import (
    OperatorControlledDeliveryEnablementService,
    create_operator_controlled_delivery_enablement_service,
)
from app.operator_controlled_delivery_enablement.store import (
    OperatorControlledDeliveryEnablementStore,
)
from app.operator_controlled_delivery_enablement.test_contract import (
    ENABLED_AT,
    ENABLEMENT_ID,
    OPERATOR,
    _create,
    _evidence,
)


class Clock:
    def __init__(self, value: str = ENABLED_AT) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return datetime.fromisoformat(self.value.replace("Z", "+00:00")).astimezone(
            UTC
        )


class Reader:
    def __init__(self, evidence: OperatorControlledDeliveryEnablementEvidenceV1) -> None:
        self.evidence = evidence
        self.calls = 0

    def resolve(
        self, *, operator_id: str,
        create: OperatorControlledDeliveryEnablementCreateV1,
    ):
        self.calls += 1
        assert create.preflight_id == self.evidence.preflight.preflight_id
        return self.evidence


def _service(
    tmp_path: Path,
    *,
    enabled: bool = True,
    at: str = ENABLED_AT,
    database: Path | None = None,
):
    evidence = _evidence(tmp_path, at=at)
    reader = Reader(evidence)
    clock = Clock(at)
    service = create_operator_controlled_delivery_enablement_service(
        configuration=OperatorControlledDeliveryEnablementConfigurationV1(
            enabled=enabled
        ),
        evidence_reader=reader,
        store=OperatorControlledDeliveryEnablementStore(
            database or tmp_path / "enablement.sqlite3"
        ),
        clock=clock,
        id_factory=lambda: ENABLEMENT_ID,
    )
    return service, reader, clock, evidence


def test_valid_creation_owned_list_get_and_restart(tmp_path: Path) -> None:
    database = tmp_path / "durable.sqlite3"
    service, reader, _, evidence = _service(tmp_path, database=database)
    created = service.create(
        _create(evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="enable-one", correlation_id="correlation-1",
    )
    assert created.disposition == "created" and created.record
    assert created.status and created.status.lifecycle == "enabled"
    assert created.audit_evidence and not created.audit_evidence.delivery_sent
    assert not any((created.default_enabled, created.agent_contacted,
                    created.credentials_loaded, created.delivery_activated,
                    created.delivery_sent, created.delivery_authorized,
                    created.execution_attempted, created.mutation_attempted,
                    created.replay_allowed))
    reader.evidence = evidence.model_copy(update={"resolved_at": ENABLED_AT})
    fetched = service.get(
        authenticated_operator_id=OPERATOR, enablement_id=ENABLEMENT_ID,
        correlation_id="correlation-2",
    )
    assert fetched.record == created.record
    assert service.list(
        authenticated_operator_id=OPERATOR, correlation_id="correlation-3"
    )[0].record == created.record
    restarted, restarted_reader, _, _ = _service(
        tmp_path, database=database
    )
    restarted_reader.evidence = evidence
    assert restarted.get(
        authenticated_operator_id=OPERATOR, enablement_id=ENABLEMENT_ID,
        correlation_id="correlation-4",
    ).record == created.record


def test_default_off_and_exact_confirmation_are_redacted(tmp_path: Path) -> None:
    service, reader, _, evidence = _service(tmp_path, enabled=False)
    outcome = service.create(
        _create(evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="disabled", correlation_id="disabled-1",
    )
    assert outcome.disposition == "rejected"
    assert outcome.error and outcome.error.error_code == "not_current"
    assert reader.calls == 0
    bad = _create(evidence).model_copy(update={"confirmation": "Enable it"})
    mismatch = service.create(
        bad, authenticated_operator_id=OPERATOR,
        idempotency_key="confirmation", correlation_id="confirmation-1",
    )
    assert mismatch.error and mismatch.error.error_code == "confirmation_mismatch"


def test_linkage_owner_auth_and_fingerprint_fail_closed(tmp_path: Path) -> None:
    service, reader, _, evidence = _service(tmp_path)
    cases = []
    cases.append(evidence.model_copy(update={"authenticated_operator_id": "operator-b"}))
    cases.append(evidence.model_copy(update={"authentication_verified": False}))
    changed_link = evidence.linkage.model_copy(
        update={"preflight_id": "00000000-0000-4000-8000-000000000a99"}
    )
    cases.append(evidence.model_copy(update={"linkage": changed_link}))
    for index, bad in enumerate(cases):
        reader.evidence = bad
        result = service.create(
            _create(evidence), authenticated_operator_id=OPERATOR,
            idempotency_key=f"bad-{index}", correlation_id=f"bad-{index}",
        )
        assert result.error and result.error.redacted
        assert result.record is None
    reader.evidence = evidence
    changed = _create(evidence).model_copy(
        update={"preflight_fingerprint": evidence.preflight.preflight_fingerprint.model_copy(
            update={"value": "0" * 64}
        )}
    )
    fingerprint = service.create(
        changed, authenticated_operator_id=OPERATOR,
        idempotency_key="bad-fp", correlation_id="bad-fp",
    )
    assert fingerprint.error and fingerprint.error.redacted


def test_expired_evidence_rejected_and_expired_read_is_terminal(tmp_path: Path) -> None:
    service, _, clock, evidence = _service(tmp_path)
    created = service.create(
        _create(evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="fresh", correlation_id="fresh-1",
    )
    assert created.record
    clock.value = created.record.expires_at
    expired = service.get(
        authenticated_operator_id=OPERATOR, enablement_id=ENABLEMENT_ID,
        correlation_id="expired-read",
    )
    assert expired.status and expired.status.lifecycle == "expired"
    stale_service, _, _, stale_evidence = _service(
        tmp_path / "stale", at="2026-08-27T12:00:42Z"
    )
    rejected = stale_service.create(
        _create(stale_evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="stale", correlation_id="stale-1",
    )
    assert rejected.error and rejected.error.error_code == "not_current"


def test_exact_retry_conflict_no_replay_or_reread(tmp_path: Path) -> None:
    service, reader, _, evidence = _service(tmp_path)
    create = _create(evidence)
    first = service.create(
        create, authenticated_operator_id=OPERATOR,
        idempotency_key="stable", correlation_id="retry-1",
    )
    retry = service.create(
        create, authenticated_operator_id=OPERATOR,
        idempotency_key="stable", correlation_id="retry-2",
    )
    assert retry.disposition == "exact_replay" and retry.record == first.record
    assert reader.calls == 1
    conflict = service.create(
        create, authenticated_operator_id=OPERATOR,
        idempotency_key="changed", correlation_id="retry-3",
    )
    assert conflict.error and conflict.error.error_code == "replay_conflict"
    assert not conflict.replay_allowed


def test_quota_size_corruption_and_foreign_reads_fail_closed(
    tmp_path: Path, monkeypatch,
) -> None:
    import app.operator_controlled_delivery_enablement.store as store_module

    service, _, _, evidence = _service(tmp_path)
    created = service.create(
        _create(evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="stored", correlation_id="stored-1",
    )
    assert created.record
    foreign = service.get(
        authenticated_operator_id="operator-b", enablement_id=ENABLEMENT_ID,
        correlation_id="foreign-1",
    )
    assert foreign.error and foreign.error.error_code == "not_found"
    monkeypatch.setattr(store_module, "MAX_RECORDS_PER_OPERATOR", 0)
    quota_service, _, _, quota_evidence = _service(
        tmp_path / "quota", database=tmp_path / "quota.sqlite3"
    )
    quota = quota_service.create(
        _create(quota_evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="quota", correlation_id="quota-1",
    )
    assert quota.error and quota.error.error_code == "quota_exceeded"
    monkeypatch.setattr(store_module, "MAX_RECORDS_PER_OPERATOR", 16)
    monkeypatch.setattr(store_module, "MAX_RECORD_BYTES", 1)
    size_service, _, _, size_evidence = _service(
        tmp_path / "size", database=tmp_path / "size.sqlite3"
    )
    oversized = size_service.create(
        _create(size_evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="size", correlation_id="size-1",
    )
    assert oversized.disposition == "unavailable"
    monkeypatch.setattr(store_module, "MAX_RECORD_BYTES", 96 * 1024)
    with sqlite3.connect(tmp_path / "enablement.sqlite3") as connection:
        connection.execute(
            "UPDATE operator_delivery_enablements SET record_json = ?", ("{}",)
        )
    corrupted = service.get(
        authenticated_operator_id=OPERATOR, enablement_id=ENABLEMENT_ID,
        correlation_id="corrupt-1",
    )
    assert corrupted.disposition == "unavailable"
    assert corrupted.error and corrupted.error.model_dump() == {
        "schema": "operator-controlled-delivery-enablement-error-v1",
        "error_code": "unavailable", "correlation_id": "corrupt-1",
        "preflight_id": None, "preflight_fingerprint": None, "redacted": True,
    }


def test_no_forbidden_dependencies_calls_consumers_or_authority() -> None:
    package = Path(__file__).parent
    forbidden = {"httpx", "requests", "socket", "ssl", "urllib", "subprocess",
                 "docker", "podman"}
    for path in package.glob("*.py"):
        if path.name.startswith("test_"):
            continue
        tree = ast.parse(path.read_text())
        imports = {alias.name.split(".")[0] for node in ast.walk(tree)
                   if isinstance(node, (ast.Import, ast.ImportFrom))
                   for alias in node.names}
        calls = {getattr(node.func, "id", "") for node in ast.walk(tree)
                 if isinstance(node, ast.Call)}
        assert imports.isdisjoint(forbidden), path
        assert calls.isdisjoint({"open", "exec", "eval", "system", "run", "Popen"}), path
    marker = "create_operator_controlled_delivery_enablement_service"
    consumers = [path for path in package.parent.rglob("*.py")
                 if package not in path.parents and not path.name.startswith("test_")
                 and marker in path.read_text()]
    assert consumers == []
    for name in ("activate", "send", "deliver", "execute", "dispatch", "install"):
        assert not hasattr(OperatorControlledDeliveryEnablementService, name)
