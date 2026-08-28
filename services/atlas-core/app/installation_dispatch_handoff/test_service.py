from __future__ import annotations

import ast
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.installation_dispatch_handoff.contract import (
    InstallationDispatchHandoffCreateV1,
)
from app.installation_dispatch_handoff.service import (
    InstallationDispatchHandoffService,
)
from app.installation_dispatch_handoff.store import (
    InstallationDispatchHandoffStore,
    InstallationDispatchNotCurrentError,
    InstallationDispatchNotFoundError,
    InstallationDispatchQuotaError,
    InstallationDispatchRecordLimitError,
    InstallationDispatchReplayConflictError,
    InstallationDispatchUnavailableError,
)
from app.installation_dispatch_handoff.test_contract import upstream

NOW = datetime(2026, 8, 27, 12, 0, 1, tzinfo=UTC)


class Reader:
    def __init__(self, values, *, owner_attribute: str):
        self.values = values
        self.owner_attribute = owner_attribute

    def get(self, **keywords):
        owner = keywords.get("owner_id", keywords.get("operator_id"))
        identity = next(
            value
            for key, value in keywords.items()
            if key.endswith("_id") and key not in {"owner_id", "operator_id"}
        )
        value = self.values[identity]
        if getattr(value, self.owner_attribute, owner) != owner:
            raise KeyError
        return value


def setup(tmp_path: Path, *, enabled: bool = True, current=None):
    candidate, intent, request, create = upstream(tmp_path / "chain")
    current = current or [NOW]
    store = InstallationDispatchHandoffStore(
        tmp_path / "handoffs.sqlite",
        execution_requests=Reader(
            {request.execution_request_id: request}, owner_attribute="missing"
        ),
        candidates=Reader(
            {candidate.candidate_record_id: candidate}, owner_attribute="owner_id"
        ),
        approvals=Reader(
            {intent.approval_intent_id: intent}, owner_attribute="operator_id"
        ),
        clock=lambda: current[0],
        id_factory=lambda: uuid.UUID("00000000-0000-4000-8000-000000000401"),
    )
    return (
        InstallationDispatchHandoffService(store=store, enabled=enabled),
        store,
        candidate,
        intent,
        request,
        create,
        current,
    )


def test_create_replay_passive_expiry_and_restart_read(tmp_path: Path) -> None:
    service, store, _candidate, _intent, _request, create, current = setup(tmp_path)
    envelope = service.prepare(
        operator_id="operator-a", idempotency_key="handoff", create=create
    )
    assert envelope.mode == "handoff-only"
    assert not any(
        (
            envelope.delivery_authorized,
            envelope.agent_admission_authorized,
            envelope.execution_authorized,
            envelope.mutation_authorized,
            envelope.replay_allowed,
        )
    )
    current[0] = NOW + timedelta(days=1)
    assert service.prepare(
        operator_id="operator-a", idempotency_key="handoff", create=create
    ) == envelope
    assert service.state(
        operator_id="operator-a", dispatch_envelope_id=envelope.dispatch_envelope_id
    ) == "expired"
    reopened = InstallationDispatchHandoffStore(
        store.database_path,
        execution_requests=Reader({}, owner_attribute="missing"),
        candidates=Reader({}, owner_attribute="owner_id"),
        approvals=Reader({}, owner_attribute="operator_id"),
    )
    assert reopened.get(
        owner_id="operator-a", dispatch_envelope_id=envelope.dispatch_envelope_id
    ) == envelope


def test_default_disabled_conflict_no_replay_and_ownership(tmp_path: Path) -> None:
    disabled, *_values = setup(tmp_path / "disabled", enabled=False)
    create = _values[4]
    with pytest.raises(InstallationDispatchUnavailableError, match="^unavailable$"):
        disabled.prepare(
            operator_id="operator-a", idempotency_key="disabled", create=create
        )

    service, _store, _candidate, _intent, request, create, _current = setup(
        tmp_path / "live"
    )
    envelope = service.prepare(
        operator_id="operator-a", idempotency_key="first", create=create
    )
    with pytest.raises(InstallationDispatchReplayConflictError):
        service.prepare(
            operator_id="operator-a", idempotency_key="second", create=create
        )
    changed = InstallationDispatchHandoffCreateV1(
        execution_request_id="00000000-0000-4000-8000-000000000402"
    )
    with pytest.raises(InstallationDispatchReplayConflictError):
        service.prepare(
            operator_id="operator-a", idempotency_key="first", create=changed
        )
    with pytest.raises(InstallationDispatchNotFoundError):
        service.get(
            operator_id="operator-b",
            dispatch_envelope_id=envelope.dispatch_envelope_id,
        )
    assert service.list_for_operator(operator_id="operator-b") == ()
    assert envelope.linkage.execution_request_fingerprint == (
        request.execution_request_fingerprint
    )


def test_stale_quota_size_and_corruption_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale, *_values = setup(
        tmp_path / "stale", current=[NOW + timedelta(days=1)]
    )
    with pytest.raises(InstallationDispatchNotCurrentError):
        stale.prepare(
            operator_id="operator-a", idempotency_key="stale", create=_values[4]
        )

    service, store, *_values = setup(tmp_path / "bounds")
    monkeypatch.setattr(
        "app.installation_dispatch_handoff.store.MAX_RETAINED_ENVELOPES_PER_OPERATOR",
        0,
    )
    with pytest.raises(InstallationDispatchQuotaError, match="^quota_exceeded$"):
        service.prepare(
            operator_id="operator-a", idempotency_key="quota", create=_values[3]
        )
    monkeypatch.setattr(
        "app.installation_dispatch_handoff.store.MAX_RETAINED_ENVELOPES_PER_OPERATOR",
        16,
    )
    monkeypatch.setattr("app.installation_dispatch_handoff.store.MAX_ENVELOPE_BYTES", 1)
    with pytest.raises(InstallationDispatchRecordLimitError):
        service.prepare(
            operator_id="operator-a", idempotency_key="size", create=_values[3]
        )
    monkeypatch.setattr(
        "app.installation_dispatch_handoff.store.MAX_ENVELOPE_BYTES", 32 * 1024
    )
    envelope = service.prepare(
        operator_id="operator-a", idempotency_key="valid", create=_values[3]
    )
    with sqlite3.connect(store.database_path) as connection:
        connection.execute(
            "UPDATE installation_dispatch_handoffs SET envelope_json='{}' "
            "WHERE dispatch_envelope_id=?",
            (envelope.dispatch_envelope_id,),
        )
    with pytest.raises(InstallationDispatchUnavailableError):
        service.get(
            operator_id="operator-a",
            dispatch_envelope_id=envelope.dispatch_envelope_id,
        )


def test_no_delivery_invocation_execution_or_external_mutation_surface() -> None:
    forbidden_imports = {
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "operational_dispatch",
        "provider_intents",
        "repository",
        "execution_worker",
    }
    package = Path(__file__).parent
    for filename in ("store.py", "service.py"):
        tree = ast.parse((package / filename).read_text())
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert not imports & forbidden_imports
        source = (package / filename).read_text()
        assert "UPDATE installation_dispatch_handoffs" not in source
        assert "DELETE FROM installation_dispatch_handoffs" not in source
    for forbidden in ("deliver", "dispatch", "execute", "invoke", "consume"):
        assert not hasattr(InstallationDispatchHandoffService, forbidden)
