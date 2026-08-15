"""Bounded sanitized operational support-bundle tests."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.workflow.recovery_diagnostic import project_recovery_diagnostic
from app.workflow.support_bundle import (
    MAX_AUDIT_REFERENCES,
    MAX_TEXT_LENGTH,
    MAX_TRANSITIONS,
    OperationalSupportBundle,
    build_operational_support_bundle,
)

NOW = datetime(2026, 8, 15, tzinfo=UTC)


def _lifecycle(**overrides):
    approval = SimpleNamespace(
        decision_status="approved",
        presentation_state="resolved",
        actionable=False,
        expires_at=NOW + timedelta(minutes=5),
    )
    values = {
        "applicable": True,
        "workflow_id": "workflow-1",
        "workflow_state": "completed",
        "agent_execution_record_present": True,
        "core_record_present": True,
        "request_digest_match": True,
        "candidate_id": "candidate-1",
        "planning_session_id": "planning-1",
        "effect_kind": "operational_action",
        "execution_intent": "restart-service",
        "target_label": "proxmox/qemu/110",
        "preparation_approval": approval,
        "action_approval": approval,
        "availability": "complete",
        "consistency_status": "consistent",
        "action_request_id": "request-1",
        "request_digest": "request-digest-v1:abc",
        "agent_execution_stage": "verified",
        "core_record_state": "verified",
        "transitions": tuple(
            SimpleNamespace(sequence=index, state=state, occurred_at=NOW)
            for index, state in enumerate(("claimed", "verified"), start=1)
        ),
        "transition_sequence_valid": True,
        "barrier_crossed": True,
        "barrier_crossing_count": 1,
        "provider_operation_captured": True,
        "provider_operation_capture_count": 1,
        "dispatch_status": "succeeded",
        "provider_operation_reference": "UPID:sanitized",
        "verification_status": "succeeded",
        "target_fingerprint": "fingerprint-1",
        "observed_target_fingerprint": "fingerprint-1",
        "observed_state": "running",
        "observed_health": "running",
        "agent_terminal": True,
        "terminal": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _bundle(lifecycle=None, *, events=()):
    lifecycle = lifecycle or _lifecycle()
    return build_operational_support_bundle(
        lifecycle=lifecycle,
        diagnostic=project_recovery_diagnostic(lifecycle),
        generated_at=NOW,
        agent_version="0.9-test",
        operational_execution_intents=frozenset({"restart-service"}),
        production_tuples=("restart-service/proxmox/qemu",),
        audit_event_types=events,
    )


def test_verified_workflow_bundle_is_typed_and_integrity_bound() -> None:
    bundle = _bundle(events=("authenticated_dispatch_submitted", "verification_succeeded"))

    assert bundle.metadata.schema_version == "atlas-operational-support-bundle-v1"
    assert bundle.lifecycle.terminal is True
    assert bundle.diagnostic.diagnostic_status == "healthy"
    assert bundle.integrity.digest.startswith("operational-support-bundle-digest-v1:")
    assert [item.event_type for item in bundle.audit_refs] == [
        "authenticated_dispatch_submitted",
        "verification_succeeded",
    ]


def test_pending_and_core_unavailable_bundles_remain_partial() -> None:
    pending = _lifecycle(
        workflow_state="verifying",
        agent_execution_stage="verification_pending",
        core_record_state="verifying",
        verification_status=None,
        observed_target_fingerprint=None,
        agent_terminal=False,
        terminal=False,
    )
    unavailable = _lifecycle(
        availability="unavailable",
        consistency_status="core_unavailable",
        core_record_present=False,
        request_digest_match=None,
        core_record_state=None,
        transitions=(),
        transition_sequence_valid=None,
        barrier_crossed=False,
        barrier_crossing_count=0,
        provider_operation_captured=False,
        provider_operation_capture_count=0,
        dispatch_status=None,
        provider_operation_reference=None,
        verification_status=None,
        observed_target_fingerprint=None,
        observed_state=None,
        observed_health=None,
        agent_terminal=False,
        terminal=False,
    )

    assert _bundle(pending).diagnostic.diagnostic_status == "recovery_in_progress"
    assert _bundle(unavailable).diagnostic.diagnostic_status == "unavailable"
    assert _bundle(unavailable).lifecycle.transitions == ()


def test_repository_bundle_is_typed_not_applicable() -> None:
    lifecycle = _lifecycle(
        applicable=False,
        effect_kind="repository_change",
        execution_intent=None,
        target_label=None,
        preparation_approval=None,
        action_approval=None,
        agent_execution_record_present=False,
        core_record_present=False,
        request_digest_match=None,
        action_request_id=None,
        request_digest=None,
        agent_execution_stage=None,
        core_record_state=None,
        transitions=(),
        transition_sequence_valid=None,
        barrier_crossed=False,
        barrier_crossing_count=0,
        provider_operation_captured=False,
        provider_operation_capture_count=0,
        dispatch_status=None,
        provider_operation_reference=None,
        verification_status=None,
        target_fingerprint=None,
        observed_target_fingerprint=None,
        observed_state=None,
        observed_health=None,
        agent_terminal=False,
        terminal=False,
    )

    bundle = _bundle(lifecycle)

    assert bundle.applicable is False
    assert bundle.diagnostic.controlled_reason == "not_applicable"


def test_canonical_digest_is_deterministic_and_content_sensitive() -> None:
    first = _bundle()
    second = _bundle()
    changed = _bundle(_lifecycle(observed_health="degraded"))

    assert first.integrity.digest == second.integrity.digest
    assert first.integrity.digest != changed.integrity.digest
    assert first.integrity.digest not in first.model_dump_json(exclude={"integrity"})


def test_bundle_applies_deterministic_bounds_and_records_truncation() -> None:
    lifecycle = _lifecycle(
        target_label="x" * (MAX_TEXT_LENGTH + 10),
        transitions=tuple(
            SimpleNamespace(sequence=index, state="claimed", occurred_at=NOW)
            for index in range(MAX_TRANSITIONS + 5)
        ),
    )
    events = ("verification_pending",) * (MAX_AUDIT_REFERENCES + 5)

    bundle = _bundle(lifecycle, events=events)

    assert len(bundle.workflow.target_label or "") == MAX_TEXT_LENGTH
    assert len(bundle.lifecycle.transitions) == MAX_TRANSITIONS
    assert len(bundle.audit_refs) == MAX_AUDIT_REFERENCES
    assert bundle.truncation.transitions_truncated is True
    assert bundle.truncation.audit_references_truncated is True
    assert "workflow.target_label" in bundle.truncation.text_fields_truncated
    assert len(bundle.model_dump_json().encode()) < 64 * 1024


def test_bundle_schema_excludes_secrets_native_payloads_and_arbitrary_events() -> None:
    bundle = _bundle(events=("secret native exception", "verification_succeeded"))
    fields = set(OperationalSupportBundle.model_fields)
    payload = bundle.model_dump_json().lower()
    forbidden = (
        "password", "credential", "authorization", "cookie", "csrf", "bearer",
        "api_token", "private_key", "verifier_hash", "vmgenid", "identity_token",
        "native_payload", "command", "environment", "docker_socket", "sandbox",
        "filesystem", "secret native exception",
    )

    assert fields == {
        "applicable", "metadata", "workflow", "approvals", "lifecycle",
        "diagnostic", "service_health", "capability_boundary", "audit_refs",
        "truncation", "integrity",
    }
    assert not any(value in payload for value in forbidden)
    assert [item.event_type for item in bundle.audit_refs] == ["verification_succeeded"]


def test_generator_has_no_filesystem_archive_or_network_boundary() -> None:
    source = __import__(
        "inspect"
    ).getsource(build_operational_support_bundle)

    assert all(
        value not in source
        for value in ("open(", "Path(", "tarfile", "zipfile", "http", "upload", "requests")
    )
