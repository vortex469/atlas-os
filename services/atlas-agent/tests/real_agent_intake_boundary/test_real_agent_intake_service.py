from __future__ import annotations

import sqlite3
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import app.real_agent_intake_boundary.store as store_module
import pytest
from app.real_agent_intake_boundary import (
    AgentInstallationIntakeAuthenticationContextV1,
    AgentInstallationIntakeEvidenceContextV1,
    AgentInstallationIntakeRequestV1,
    AgentRealIntakeEvidenceService,
    AgentRealIntakeEvidenceStore,
    request_fingerprint,
)
from app.real_agent_intake_boundary.models import dispatch_envelope_fingerprint
from app.real_agent_intake_boundary.store import RealIntakeStoreError
from pydantic import ValidationError
from tests.real_agent_intake_boundary.test_real_agent_intake_models import (
    OPERATOR,
    request_dict,
)

ADMISSION_ID = "00000000-0000-4000-8000-000000000703"


def clock() -> datetime:
    return datetime(2026, 8, 29, 12, 0, 25, tzinfo=UTC)


class EvidenceReader:
    def __init__(self) -> None:
        self.calls = 0
        self.operator_override: str | None = None
        self.linkage_override = None
        self.observed_at = "2026-08-29T12:00:10Z"
        self.acknowledged_at = "2026-08-29T12:00:12Z"

    def resolve(self, *, operator_id: str, prior_evidence):
        self.calls += 1
        request = AgentInstallationIntakeRequestV1.model_validate(request_dict())
        return AgentInstallationIntakeEvidenceContextV1(
            operator_id=self.operator_override or operator_id,
            linkage=self.linkage_override or request.envelope.linkage,
            prior_evidence=prior_evidence,
            intake_record_observed_at=self.observed_at,
            acknowledgement_acknowledged_at=self.acknowledged_at,
        )


def values(tmp_path: Path, *, enabled: bool = True):
    reader = EvidenceReader()
    store = AgentRealIntakeEvidenceStore(
        tmp_path / "real-intake.sqlite3",
        clock=clock,
        id_factory=lambda: uuid.UUID(ADMISSION_ID),
    )
    service = AgentRealIntakeEvidenceService(
        store=store, evidence_reader=reader, enabled=enabled
    )
    request = AgentInstallationIntakeRequestV1.model_validate(request_dict())
    auth = AgentInstallationIntakeAuthenticationContextV1()
    return service, store, reader, request, auth


def preserve(service, request, auth, *, key: str = "intake-key-1"):
    return service.preserve(
        request,
        authentication=auth,
        idempotency_key=key,
        correlation_id="real-intake-1",
    )


def test_valid_preserve_read_restart_and_passive_expiry(tmp_path: Path) -> None:
    service, store, _, request, auth = values(tmp_path)
    result = preserve(service, request, auth)
    assert result.outcome == "admitted_for_evidence_only"
    admission = result.admission
    assert admission is not None
    assert admission.received_at == "2026-08-29T12:00:25Z"
    assert admission.valid_until == request.expires_at
    assert admission.delivery_received is True
    assert admission.evidence_admission_granted is True
    assert not any(
        (
            admission.execution_admission_granted,
            admission.execution_authorized,
            admission.worker_allowed,
            admission.mutation_allowed,
            admission.replay_allowed,
        )
    )
    assert service.get(operator_id=OPERATOR, admission_id=admission.admission_id) == admission
    acknowledgement = service.get_acknowledgement(
        operator_id=OPERATOR, admission_id=admission.admission_id
    )
    assert acknowledgement.admission_fingerprint == admission.admission_fingerprint

    restarted_store = AgentRealIntakeEvidenceStore(store.database_path, clock=clock)
    assert restarted_store.get(operator_id=OPERATOR, admission_id=admission.admission_id) == admission
    assert restarted_store.lifecycle(operator_id=OPERATOR, admission_id=admission.admission_id) == "admitted"
    expired_store = AgentRealIntakeEvidenceStore(
        store.database_path,
        clock=lambda: datetime(2026, 8, 29, 12, 1, 0, tzinfo=UTC),
    )
    assert expired_store.lifecycle(operator_id=OPERATOR, admission_id=admission.admission_id) == "expired"
    assert expired_store.get(operator_id=OPERATOR, admission_id=admission.admission_id) == admission


def test_exact_idempotent_replay_skips_reader_clock_and_new_work(tmp_path: Path) -> None:
    service, store, reader, request, auth = values(tmp_path)
    first = preserve(service, request, auth)
    assert reader.calls == 1
    store._clock = lambda: (_ for _ in ()).throw(RuntimeError("must not run"))
    second = preserve(service, request, auth)
    assert second == first
    assert reader.calls == 1


def test_idempotency_conflict_and_one_envelope_no_replay(tmp_path: Path) -> None:
    service, _, _, request, auth = values(tmp_path)
    assert preserve(service, request, auth).admission is not None
    changed = deepcopy(request_dict())
    changed["delivery_attempt_id"] = "00000000-0000-4000-8000-000000000799"
    changed["request_fingerprint"] = request_fingerprint(changed).model_dump(mode="json")
    changed_request = AgentInstallationIntakeRequestV1.model_validate(changed)
    conflict = preserve(service, changed_request, auth)
    assert conflict.reason_code == "replay_conflict"
    second_key = preserve(service, changed_request, auth, key="different-key")
    assert second_key.reason_code == "replay_conflict"


def test_ownership_linkage_fingerprints_auth_and_staleness_fail_closed(
    tmp_path: Path,
) -> None:
    service, _, reader, request, auth = values(tmp_path)
    reader.operator_override = "operator-b"
    assert preserve(service, request, auth).reason_code == "ownership_mismatch"

    service, _, reader, request, auth = values(tmp_path / "linkage")
    altered = request.envelope.linkage.model_copy(
        update={"execution_request_id": "00000000-0000-4000-8000-000000000299"}
    )
    reader.linkage_override = altered
    assert preserve(service, request, auth).reason_code == "linkage_mismatch"

    bad_raw = request_dict()
    bad_raw["request_fingerprint"] = {
        "algorithm": "sha256",
        "canonicalization": "atlas-jcs-nfc-v1",
        "value": "0" * 64,
    }
    bad_request = AgentInstallationIntakeRequestV1.model_validate(bad_raw)
    assert preserve(service, bad_request, auth).reason_code == "request_mismatch"

    invalid_auth = {"authenticated_principal": "atlas-core", "permission": "admin"}
    unauthenticated = service.preserve(
        request,
        authentication=invalid_auth,  # type: ignore[arg-type]
        idempotency_key="auth-key",
        correlation_id="real-intake-1",
    )
    assert unauthenticated.reason_code == "unauthenticated"
    assert unauthenticated.intake_request_id is None

    service, _, reader, request, auth = values(tmp_path / "stale")
    reader.acknowledged_at = "2026-08-29T12:00:21Z"
    assert preserve(service, request, auth).reason_code == "not_current"


def test_default_disabled_and_closed_fixed_posture(tmp_path: Path) -> None:
    service, _, reader, request, auth = values(tmp_path, enabled=False)
    result = preserve(service, request, auth)
    assert result.reason_code == "unavailable"
    assert result.intake_request_id is None
    assert reader.calls == 0
    with pytest.raises(ValidationError):
        AgentInstallationIntakeAuthenticationContextV1.model_validate(
            {
                "authenticated_principal": "atlas-core/install-intake-v1",
                "permission": "installation_intake:create",
                "internal_https": False,
                "credential_authenticated": True,
            }
        )


def test_quota_size_and_corruption_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, store, _, request, auth = values(tmp_path)
    result = preserve(service, request, auth)
    admission = result.admission
    assert admission is not None
    with sqlite3.connect(store.database_path) as connection:
        connection.execute(
            "UPDATE agent_real_intake_admissions SET admission_json=? WHERE admission_id=?",
            ("{}", admission.admission_id),
        )
    with pytest.raises(RealIntakeStoreError, match="unavailable"):
        store.get(operator_id=OPERATOR, admission_id=admission.admission_id)

    monkeypatch.setattr(store_module, "MAX_RETAINED_RECORDS_PER_OPERATOR", 1)
    quota_service, _, _, quota_request, quota_auth = values(tmp_path / "quota")
    assert preserve(quota_service, quota_request, quota_auth).admission is not None
    changed = deepcopy(request_dict())
    changed["intake_request_id"] = "00000000-0000-4000-8000-000000000711"
    changed["delivery_attempt_id"] = "00000000-0000-4000-8000-000000000712"
    changed["envelope"]["dispatch_envelope_id"] = (  # type: ignore[index]
        "00000000-0000-4000-8000-000000000411"
    )
    changed["prior_evidence"]["intake_simulation"]["simulation_request_id"] = (  # type: ignore[index]
        "00000000-0000-4000-8000-000000000511"
    )
    changed["prior_evidence"]["intake_simulation"]["intake_record_id"] = (  # type: ignore[index]
        "00000000-0000-4000-8000-000000000512"
    )
    changed["prior_evidence"]["simulated_delivery"]["simulated_delivery_id"] = (  # type: ignore[index]
        "00000000-0000-4000-8000-000000000611"
    )
    changed["prior_evidence"]["simulated_delivery"]["acknowledgement_id"] = (  # type: ignore[index]
        "00000000-0000-4000-8000-000000000613"
    )
    changed["envelope"]["dispatch_envelope_fingerprint"] = (  # type: ignore[index]
        dispatch_envelope_fingerprint(operator_id=OPERATOR, envelope=changed["envelope"])
        .model_dump(mode="json")
    )
    changed["request_fingerprint"] = request_fingerprint(changed).model_dump(mode="json")
    second = AgentInstallationIntakeRequestV1.model_validate(changed)
    assert preserve(quota_service, second, quota_auth, key="quota-key-2").reason_code == (
        "quota_exceeded"
    )

    monkeypatch.setattr(store_module, "MAX_ADMISSION_BYTES", 1)
    size_service, _, _, size_request, size_auth = values(tmp_path / "size")
    assert preserve(size_service, size_request, size_auth).reason_code == "quota_exceeded"


def test_no_forbidden_consumers_or_capability_calls() -> None:
    app_root = Path(__file__).parents[2] / "app"
    package = app_root / "real_agent_intake_boundary"
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(package.glob("*.py"))
    )
    for forbidden in (
        "subprocess",
        "docker",
        "podman",
        "requests",
        "httpx",
        "socket",
        "create_subprocess",
        "Popen",
        "os.system",
    ):
        assert forbidden not in combined
    consumers = []
    markers = ("AgentRealIntakeEvidenceService", "AgentRealIntakeEvidenceStore")
    for path in app_root.rglob("*.py"):
        if package in path.parents:
            continue
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in markers):
            consumers.append(path.relative_to(app_root))
    assert consumers == []
