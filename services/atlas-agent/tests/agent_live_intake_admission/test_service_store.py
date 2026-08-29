from __future__ import annotations

import ast
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.agent_live_intake_admission import store as store_module
from app.agent_live_intake_admission.contract import (
    AgentLiveIntakeAuthenticationContextV1,
    AgentLiveIntakeAuthenticationReferenceV1,
    AgentLiveIntakeEnvelopeV1,
    AgentLiveIntakeLinkageV1,
    AgentLiveIntakeSourceV1,
    envelope_fingerprint,
    idempotency_key_fingerprint,
)
from app.agent_live_intake_admission.service import AgentLiveIntakeAdmissionService
from app.agent_live_intake_admission.store import (
    AgentLiveIntakeAdmissionStore,
    AgentLiveIntakeUnavailableError,
)

from .test_contract import OPERATOR, envelope, fp

NOW = datetime(2026, 8, 29, 12, 0, 25, tzinfo=UTC)
IDS = (
    uuid.UUID("00000000-0000-4000-8000-000000003201"),
    uuid.UUID("00000000-0000-4000-8000-000000003202"),
)


class Reader:
    def __init__(self, *, changed: bool = False, fail: bool = False) -> None:
        self.changed = changed
        self.fail = fail

    def resolve(
        self, *, operator_id: str, linkage: AgentLiveIntakeLinkageV1
    ) -> AgentLiveIntakeLinkageV1:
        assert operator_id == OPERATOR
        if self.fail:
            raise RuntimeError("secret internal reader failure at /provider/path")
        if not self.changed:
            return linkage
        raw = linkage.model_dump(mode="json")
        raw["enablement_id"] = "00000000-0000-4000-8000-000000003099"
        return AgentLiveIntakeLinkageV1.model_validate(raw)


def authentication(*, host: str = "atlas-agent.internal"):
    return AgentLiveIntakeAuthenticationContextV1(
        source=AgentLiveIntakeSourceV1(host=host),
        credential_reference=AgentLiveIntakeAuthenticationReferenceV1(
            credential_file="/run/secrets/atlas-agent-intake-token"
        ),
    )


def service(tmp_path: Path, *, enabled: bool = True, reader: Reader | None = None, now=NOW):
    ids = iter(IDS)
    store = AgentLiveIntakeAdmissionStore(
        tmp_path / "intake.sqlite3", clock=lambda: now, id_factory=lambda: next(ids)
    )
    env = envelope()
    return (
        AgentLiveIntakeAdmissionService(
            store=store,
            evidence_reader=reader or Reader(),
            expected_source=AgentLiveIntakeSourceV1(host="atlas-agent.internal"),
            endpoint_fingerprint=env.endpoint_fingerprint,
            enabled=enabled,
        ),
        store,
        env,
    )


def test_valid_admission_default_off_and_complete_evidence(tmp_path: Path) -> None:
    disabled, _, env = service(tmp_path, enabled=False)
    assert disabled.admit(env, authentication=authentication(), idempotency_key="send-once", correlation_id="intake-1").reason_code == "unavailable"
    live, store, env = service(tmp_path)
    result = live.admit(env, authentication=authentication(), idempotency_key="send-once", correlation_id="intake-1")
    assert result.outcome == "admitted_for_evidence_only"
    assert result.admission is not None and result.acknowledgement is not None
    record = live.get(operator_id=OPERATOR, admission_id=result.admission.admission_id)
    audit = live.get_audit(operator_id=OPERATOR, admission_id=result.admission.admission_id)
    assert record.admission == result.admission
    assert record.acknowledgement == result.acknowledgement
    assert audit.admission_fingerprint == result.admission.admission_fingerprint
    assert store.status(operator_id=OPERATOR, admission_id=result.admission.admission_id).lifecycle == "admitted_for_evidence_only"
    assert not any((record.execution_authorized, record.installation_allowed, record.worker_allowed, record.workflow_allowed, record.deployment_allowed, record.mutation_allowed, record.replay_allowed))


def test_idempotent_retry_conflict_and_permanent_no_replay(tmp_path: Path) -> None:
    live, _, env = service(tmp_path)
    first = live.admit(env, authentication=authentication(), idempotency_key="send-once", correlation_id="intake-1")
    retry = live.admit(env, authentication=authentication(), idempotency_key="send-once", correlation_id="different-correlation")
    assert retry == first
    raw = env.model_dump(mode="json")
    raw["idempotency_key_fingerprint"] = idempotency_key_fingerprint(OPERATOR, "changed").model_dump(mode="json")
    raw["envelope_fingerprint"] = envelope_fingerprint(raw).model_dump(mode="json")
    changed = AgentLiveIntakeEnvelopeV1.model_validate(raw)
    conflict = live.admit(changed, authentication=authentication(), idempotency_key="send-once", correlation_id="intake-2")
    assert conflict.reason_code == "replay_conflict"
    second_key = live.admit(env, authentication=authentication(), idempotency_key="another-key", correlation_id="intake-3")
    assert second_key.reason_code == "replay_conflict"


def test_stale_linkage_authentication_and_endpoint_fail_closed(tmp_path: Path) -> None:
    stale, _, env = service(tmp_path, now=datetime(2026, 8, 29, 12, 0, 50, tzinfo=UTC))
    assert stale.admit(env, authentication=authentication(), idempotency_key="send-once", correlation_id="intake-1").reason_code == "not_current"
    mismatched, _, env = service(tmp_path / "linkage", reader=Reader(changed=True))
    assert mismatched.admit(env, authentication=authentication(), idempotency_key="send-once", correlation_id="intake-1").reason_code == "linkage_mismatch"
    live, _, env = service(tmp_path / "auth")
    rejected = live.admit(env, authentication=authentication(host="other-agent.internal"), idempotency_key="send-once", correlation_id="intake-1")
    assert rejected.reason_code == "unauthenticated" and rejected.send_attempt_id is None
    wrong_endpoint, store, env = service(tmp_path / "endpoint")
    wrong_endpoint._endpoint_fingerprint = type(env.endpoint_fingerprint).model_validate(fp("f"))
    rejected = wrong_endpoint.admit(env, authentication=authentication(), idempotency_key="send-once", correlation_id="intake-1")
    assert rejected.reason_code == "fingerprint_mismatch"
    assert store.replay(operator_id=OPERATOR, idempotency_key="send-once", envelope=env) is None


def test_restart_readback_foreign_absence_and_corruption(tmp_path: Path) -> None:
    live, store, env = service(tmp_path)
    result = live.admit(env, authentication=authentication(), idempotency_key="send-once", correlation_id="intake-1")
    admission_id = result.admission.admission_id  # type: ignore[union-attr]
    restarted = AgentLiveIntakeAdmissionStore(store.database_path, clock=lambda: NOW)
    assert restarted.get(operator_id=OPERATOR, admission_id=admission_id).admission.admission_id == admission_id
    with pytest.raises(AgentLiveIntakeUnavailableError):
        restarted.get(operator_id="operator-b", admission_id=admission_id)
    with sqlite3.connect(store.database_path) as connection:
        connection.execute("UPDATE agent_live_intake_admissions SET record_json='{}'")
    with pytest.raises(AgentLiveIntakeUnavailableError):
        restarted.get(operator_id=OPERATOR, admission_id=admission_id)


def test_quota_size_bounds_and_redacted_dependency_errors(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(store_module, "MAX_RETAINED_RECORDS_PER_OPERATOR", 0)
    live, _, env = service(tmp_path / "quota")
    assert live.admit(env, authentication=authentication(), idempotency_key="send-once", correlation_id="intake-1").reason_code == "quota_exceeded"
    assert live.admit(env, authentication=authentication(), idempotency_key="send-once", correlation_id="intake-2").reason_code == "unavailable"
    monkeypatch.setattr(store_module, "MAX_RETAINED_RECORDS_PER_OPERATOR", 16)
    monkeypatch.setattr(store_module, "MAX_RECORD_BYTES", 1)
    live, _, env = service(tmp_path / "size")
    assert live.admit(env, authentication=authentication(), idempotency_key="send-once", correlation_id="intake-1").reason_code == "quota_exceeded"
    failed, _, env = service(tmp_path / "redacted", reader=Reader(fail=True))
    result = failed.admit(env, authentication=authentication(), idempotency_key="send-once", correlation_id="intake-1")
    assert result.reason_code == "unavailable"
    assert "secret" not in result.model_dump_json() and "/provider/path" not in result.model_dump_json()
    error = failed.redacted_error(code="internal-secret", correlation_id="intake-1")
    assert error.error_code == "unavailable" and error.redacted and not error.retryable


def test_store_service_are_isolated_from_network_runtime_and_mutation() -> None:
    package = Path("services/atlas-agent/app/agent_live_intake_admission")
    forbidden_imports = {"socket", "requests", "httpx", "urllib", "subprocess", "docker", "podman"}
    forbidden_calls = {"open", "exec", "eval", "system", "run", "Popen"}
    for path in (package / "service.py", package / "store.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        assert imports.isdisjoint(forbidden_imports)
        assert calls.isdisjoint(forbidden_calls)
        source = path.read_text(encoding="utf-8").lower()
        assert all(marker not in source for marker in ("provider mutation", "repository mutation", "in-guest mutation", "start_workflow"))
