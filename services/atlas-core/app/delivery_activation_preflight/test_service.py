from __future__ import annotations

import ast
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.delivery_activation_preflight.contract import (
    DeliveryActivationPreflightConfigurationV1,
    DeliveryActivationPreflightCreateV1,
    DeliveryActivationPreflightEvidenceV1,
)
from app.delivery_activation_preflight.service import (
    DeliveryActivationPreflightService,
    create_delivery_activation_preflight_service,
)
from app.delivery_activation_preflight.store import DeliveryActivationPreflightStore
from app.delivery_activation_preflight.test_contract import (
    EVALUATED_AT,
    OPERATOR,
    PREFLIGHT_ID,
    _create,
    _evidence,
)


class Clock:
    def __init__(self, value: str = EVALUATED_AT) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return datetime.fromisoformat(self.value.replace("Z", "+00:00")).astimezone(UTC)


class Reader:
    def __init__(self, evidence: DeliveryActivationPreflightEvidenceV1) -> None:
        self.evidence = evidence
        self.calls = 0

    def resolve(self, *, operator_id: str, create: DeliveryActivationPreflightCreateV1):
        self.calls += 1
        assert create.delivery_preparation_id == self.evidence.preparation.delivery_preparation_id
        return self.evidence


def _service(
    tmp_path: Path,
    *,
    enabled: bool = True,
    at: str = EVALUATED_AT,
    database: Path | None = None,
):
    evidence = _evidence(tmp_path, at=at)
    reader = Reader(evidence)
    clock = Clock(at)
    service = create_delivery_activation_preflight_service(
        configuration=DeliveryActivationPreflightConfigurationV1(enabled=enabled),
        evidence_reader=reader,
        store=DeliveryActivationPreflightStore(database or tmp_path / "preflight.sqlite3"),
        clock=clock,
        id_factory=lambda: PREFLIGHT_ID,
    )
    return service, reader, clock, evidence


def test_valid_creation_owned_readback_and_fixed_false(tmp_path: Path) -> None:
    service, reader, _, evidence = _service(tmp_path)
    created = service.create(
        _create(evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="preflight-one", correlation_id="correlation-1",
    )
    assert created.disposition == "created"
    assert created.result and created.result.decision == "eligible_for_later_activation"
    assert created.status and created.status.lifecycle == "eligible"
    assert created.audit_evidence and not created.audit_evidence.delivery_activated
    assert not any((created.agent_contacted, created.credentials_loaded,
                    created.delivery_activated, created.delivery_authorized,
                    created.execution_attempted, created.mutation_attempted,
                    created.replay_allowed))
    reader.evidence = reader.evidence.model_copy(update={"resolved_at": EVALUATED_AT})
    fetched = service.get(
        authenticated_operator_id=OPERATOR, preflight_id=PREFLIGHT_ID,
        correlation_id="correlation-2",
    )
    assert fetched.result == created.result
    assert DeliveryActivationPreflightStore(
        tmp_path / "preflight.sqlite3"
    ).list_owned(operator_id=OPERATOR) == (created.result,)


def test_default_disabled_creates_terminal_nonactivating_evidence(tmp_path: Path) -> None:
    service, _, _, evidence = _service(tmp_path, enabled=False)
    outcome = service.create(
        _create(evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="disabled", correlation_id="disabled-1",
    )
    assert outcome.disposition == "created"
    assert outcome.result and outcome.result.reason_codes == ("preflight_feature_disabled",)
    assert outcome.status and outcome.status.lifecycle == "ineligible"
    assert outcome.result.expires_at == outcome.result.evaluated_at


def test_invalid_linkage_ownership_auth_and_fingerprint_are_redacted(tmp_path: Path) -> None:
    service, reader, _, evidence = _service(tmp_path)
    bad = evidence.model_dump(mode="json")
    bad["linkage"]["delivery_attempt_id"] = "00000000-0000-4000-8000-000000000999"
    reader.evidence = DeliveryActivationPreflightEvidenceV1.model_construct(**bad)
    rejected = service.create(
        _create(evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="bad-link", correlation_id="bad-1",
    )
    assert rejected.error and rejected.error.redacted
    assert rejected.error.error_code in {"linkage_mismatch", "unavailable"}
    assert "detail" not in rejected.error.model_dump()

    reader.evidence = evidence.model_copy(update={"authenticated_operator_id": "operator-b"})
    owner = service.create(
        _create(evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="bad-owner", correlation_id="bad-2",
    )
    assert owner.error and owner.error.redacted
    reader.evidence = evidence
    cross_owner = service.create(
        _create(evidence), authenticated_operator_id="operator-b",
        idempotency_key="cross-owner", correlation_id="bad-owner-2",
    )
    assert cross_owner.error and cross_owner.error.redacted
    reader.evidence = evidence.model_copy(update={"authentication_verified": False})
    auth = service.create(
        _create(evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="bad-auth", correlation_id="bad-3",
    )
    assert auth.error and auth.error.redacted

    changed = _create(evidence).model_dump(mode="json")
    changed["preparation_fingerprint"]["value"] = "0" * 64
    fingerprint = service.create(
        DeliveryActivationPreflightCreateV1.model_validate(changed),
        authenticated_operator_id=OPERATOR,
        idempotency_key="bad-fp", correlation_id="bad-4",
    )
    assert fingerprint.error and fingerprint.error.redacted


@pytest.mark.parametrize("at", ["2026-08-27T12:00:33Z", "2026-08-27T12:01:01Z"])
def test_stale_and_expired_inputs_are_terminal(tmp_path: Path, at: str) -> None:
    service, _, _, evidence = _service(tmp_path, at=at)
    outcome = service.create(
        _create(evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="stale", correlation_id="stale-1",
    )
    assert outcome.result and outcome.result.reason_codes == ("expired",)
    assert outcome.status and outcome.status.lifecycle == "ineligible"


def test_exact_retry_conflict_no_reread_and_restart(tmp_path: Path) -> None:
    database = tmp_path / "durable.sqlite3"
    service, reader, _, evidence = _service(tmp_path, database=database)
    create = _create(evidence)
    first = service.create(
        create, authenticated_operator_id=OPERATOR,
        idempotency_key="stable", correlation_id="retry-1",
    )
    retry = service.create(
        create, authenticated_operator_id=OPERATOR,
        idempotency_key="stable", correlation_id="retry-2",
    )
    assert retry.disposition == "exact_replay" and retry.result == first.result
    assert reader.calls == 1
    conflict = service.create(
        create, authenticated_operator_id=OPERATOR,
        idempotency_key="changed", correlation_id="retry-3",
    )
    assert conflict.error and conflict.error.error_code == "replay_conflict"

    restarted, restarted_reader, _, _ = _service(tmp_path, database=database)
    restarted_reader.evidence = evidence
    replay = restarted.create(
        create, authenticated_operator_id=OPERATOR,
        idempotency_key="stable", correlation_id="retry-4",
    )
    assert replay.result == first.result and restarted_reader.calls == 0


def test_quota_size_and_corruption_fail_closed(tmp_path: Path, monkeypatch) -> None:
    import app.delivery_activation_preflight.store as store_module

    service, _, _, evidence = _service(tmp_path)
    created = service.create(
        _create(evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="quota-1", correlation_id="quota-1",
    )
    assert created.result
    monkeypatch.setattr(store_module, "MAX_RECORDS_PER_OPERATOR", 0)
    database = tmp_path / "quota-empty.sqlite3"
    quota_service, _, _, quota_evidence = _service(tmp_path, database=database)
    quota = quota_service.create(
        _create(quota_evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="quota-2", correlation_id="quota-2",
    )
    assert quota.error and quota.error.error_code == "quota_exceeded"

    monkeypatch.setattr(store_module, "MAX_RECORDS_PER_OPERATOR", 16)
    monkeypatch.setattr(store_module, "MAX_RESULT_BYTES", 1)
    size_service, _, _, size_evidence = _service(
        tmp_path, database=tmp_path / "size.sqlite3"
    )
    oversized = size_service.create(
        _create(size_evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="size-1", correlation_id="size-1",
    )
    assert oversized.disposition == "unavailable"
    assert oversized.error and oversized.error.redacted

    monkeypatch.setattr(store_module, "MAX_RESULT_BYTES", 96 * 1024)
    with sqlite3.connect(tmp_path / "preflight.sqlite3") as connection:
        connection.execute(
            "UPDATE delivery_activation_preflights SET result_json = ?",
            ("{}",),
        )
    corrupted = service.get(
        authenticated_operator_id=OPERATOR, preflight_id=PREFLIGHT_ID,
        correlation_id="corrupt-1",
    )
    assert corrupted.disposition == "unavailable"
    assert corrupted.error and corrupted.error.model_dump() == {
        "schema": "delivery-activation-preflight-error-v1",
        "error_code": "unavailable", "correlation_id": "corrupt-1",
        "delivery_preparation_id": None, "preparation_fingerprint": None,
        "redacted": True,
    }


def test_no_forbidden_dependencies_calls_or_production_construction() -> None:
    package = Path(__file__).parent
    forbidden = {
        "httpx", "requests", "socket", "ssl", "urllib", "subprocess",
        "docker", "podman",
    }
    forbidden_calls = {"open", "exec", "eval", "system", "run", "Popen"}
    for path in package.glob("*.py"):
        if path.name.startswith("test_"):
            continue
        tree = ast.parse(path.read_text())
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        calls = {
            getattr(node.func, "id", "")
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        assert imports.isdisjoint(forbidden), path
        assert calls.isdisjoint(forbidden_calls), path

    app_root = package.parent
    marker = "create_delivery_activation_preflight_service"
    consumers = [
        path
        for path in app_root.rglob("*.py")
        if package not in path.parents
        and not path.name.startswith("test_")
        and marker in path.read_text()
    ]
    assert consumers == []
    assert not hasattr(DeliveryActivationPreflightService, "activate")
    assert not hasattr(DeliveryActivationPreflightService, "send")
