from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import Literal, get_args, get_origin

import pytest
from pydantic import ValidationError

from app.controlled_worker_queue_claim_lease_acknowledgement import contract as v052
from app.controlled_worker_queue_claim_lease_acknowledgement.test_contract import (
    _input as v052_input,
)
from app.worker_activation_runtime_prerequisite import contract as c

RECEIPT = "controlled_worker_queue_claim_lease_acknowledgement"
STATUS = RECEIPT + "_status"


@pytest.fixture(scope="module")
def facts(tmp_path_factory):
    prior = v052.build_receipt(v052_input(tmp_path_factory.mktemp("v053")))
    status = v052.derive_status(prior, evaluated_at=prior.recorded_at)
    return c.WorkerActivationRuntimePrerequisiteValidationInputV1(
        operator_id=prior.operator_id,
        candidate_record_id=prior.candidate_record_id,
        authority=c.WorkerActivationRuntimePrerequisiteAuthorityContextV1(
            authenticated_operator_id=prior.operator_id,
            permission=c.PERMISSION,
            request_received_at=prior.recorded_at,
        ),
        create=c.build_create(receipt=prior, receipt_status=status),
        **{RECEIPT: prior, STATUS: status},
    )


def refused(raw):
    result = c.evaluate_worker_activation_runtime_prerequisite(raw)
    assert not result.worker_activation_runtime_prerequisite_recorded
    assert result.recognized_v052_receipt_count == 0
    assert result.earliest_expiry is None
    assert result.operator_id == "blocked-evaluation"
    assert result.evaluation_fingerprint == c.evaluation_fingerprint(result)
    return result


def test_success_is_deterministic_immutable_and_preserves_complete_lineage(facts):
    raw = facts.model_dump(mode="python")
    before = copy.deepcopy(raw)
    first = c.evaluate_worker_activation_runtime_prerequisite(raw)
    assert first == c.evaluate_worker_activation_runtime_prerequisite(facts)
    assert raw == before
    assert first.worker_activation_runtime_prerequisite_recorded is True
    assert first.recognized_v052_receipt_count == 1
    assert first.blockers == v052.SUCCESS_BLOCKERS
    record = c.build_prerequisite(facts, idempotency_key="v053-idempotency-key")
    assert record == c.build_prerequisite(facts, idempotency_key="v053-idempotency-key")
    assert (
        getattr(record, RECEIPT).model_dump_json()
        == getattr(facts, RECEIPT).model_dump_json()
    )
    assert getattr(record, STATUS) == getattr(facts, STATUS)
    assert record.valid_until == facts.create.valid_until
    assert (
        record.idempotency_key_fingerprint
        != getattr(facts, RECEIPT).idempotency_key_fingerprint
    )
    for model in (facts, first, record, getattr(record, RECEIPT)):
        with pytest.raises(ValidationError):
            model.operator_id = "foreign"
    assert (
        c.WorkerActivationRuntimePrerequisiteV1.model_validate_json(
            record.model_dump_json()
        )
        == record
    )
    status = c.derive_status(record, evaluated_at=record.recorded_at)
    result = c.WorkerActivationRuntimePrerequisiteResultV1(record=record, status=status)
    assert result.record == record
    expired = c.derive_status(record, evaluated_at=record.valid_until)
    assert expired.lifecycle == "expired"
    assert expired.worker_activation_runtime_prerequisite_recorded
    assert (
        c.WorkerActivationRuntimePrerequisiteResultV1(
            record=record, status=expired, exact_duplicate=True
        ).status
        == expired
    )
    with pytest.raises(ValidationError):
        c.derive_status(record, evaluated_at="2026-08-27T12:00:00Z")


@pytest.mark.parametrize("raw", [{}, None, [], "secret", {RECEIPT: None}])
def test_missing_or_invalid_envelope_is_redacted(raw):
    assert "secret" not in refused(raw).model_dump_json()


@pytest.mark.parametrize(
    "section,field,value",
    [
        (None, "operator_id", "foreign-owner"),
        (None, "candidate_record_id", "00000000-0000-4000-8000-000000000000"),
        (None, "home_assistant", True),
        (None, "ambiguous_prerequisite_count", 1),
        (None, "boundary_enabled", True),
        (None, "unknown", "secret-do-not-echo"),
        ("authority", "permission", "unapproved"),
        ("authority", "permission_verified", False),
        ("authority", "authenticated_operator_id", "foreign-owner"),
        ("authority", "request_received_at", "2026-08-27T12:00:43Z"),
        ("authority", "request_received_at", "2026-08-27T12:01:30Z"),
        ("authority", "request_received_at", "not-a-clock-secret-do-not-echo"),
        ("create", "admission_id", "00000000-0000-5000-8000-000000000000"),
        ("create", "valid_until", "2099-01-01T00:00:00Z"),
        ("create", "adapter", "secret-do-not-echo"),
        ("create", "worker_identity", "secret-do-not-echo"),
        ("create", "queue_selector", "secret-do-not-echo"),
        ("create", "claim_token", "secret-do-not-echo"),
        ("create", "endpoint", "secret-do-not-echo"),
    ],
)
def test_hostile_request_and_authority(facts, section, field, value):
    raw = facts.model_dump(mode="python")
    (raw if section is None else raw[section])[field] = value
    assert "secret-do-not-echo" not in refused(raw).model_dump_json()


@pytest.mark.parametrize("section", ["create", "authority", RECEIPT, STATUS])
@pytest.mark.parametrize("value", [True, 0, 1, "false", None])
def test_false_authority_cannot_be_coerced(facts, section, value):
    raw = facts.model_dump(mode="python")
    raw[section]["worker_start_allowed"] = value
    refused(raw)


def test_every_inherited_false_authority_is_retained_and_strict(facts):
    for field, definition in v052.ClosedAuthorityV1.model_fields.items():
        if (
            get_origin(definition.annotation) is Literal
            and get_args(definition.annotation)[0] is False
        ):
            assert field in c.ClosedAuthorityV1.model_fields
            for value in (True, 0):
                raw = facts.model_dump(mode="python")
                raw["create"][field] = value
                refused(raw)
    for section in ("create", "authority", RECEIPT, STATUS):
        for field in ("evidence_only", "reference_only"):
            raw = facts.model_dump(mode="python")
            raw[section][field] = 1
            refused(raw)
        raw = facts.model_dump(mode="python")
        raw[section]["payload_bytes"] = False
        refused(raw)
        raw = facts.model_dump(mode="python")
        raw[section]["credential_material_present"] = True
        refused(raw)


@pytest.mark.parametrize(
    "section,field",
    [
        ("create", "receipt_record_fingerprint"),
        ("create", "status_fingerprint"),
        (RECEIPT, "receipt_record_fingerprint"),
        (RECEIPT, "subject_fingerprint"),
        (RECEIPT, "v051_admission_record_fingerprint"),
        (RECEIPT, "v050_prerequisite_status_fingerprint"),
        (RECEIPT, "v049_admission_record_fingerprint"),
        (RECEIPT, "inherited_limits_fingerprint"),
        (RECEIPT, "worker_subject_fingerprint"),
        (STATUS, "status_fingerprint"),
    ],
)
def test_exact_fingerprints_and_metadata(facts, section, field):
    for key, value in (
        ("value", "a" * 64),
        ("algorithm", "sha1"),
        ("canonicalization", "foreign"),
        ("unknown", "secret"),
    ):
        raw = facts.model_dump(mode="python")
        raw[section][field][key] = value
        refused(raw)


def test_forged_model_instances_and_nested_lineage_are_reparsed(facts):
    receipt = getattr(facts, RECEIPT)
    for changes in (
        {"worker_start_allowed": True},
        {"worker_start_allowed": 0},
        {"unexpected": "secret"},
    ):
        forged = receipt.model_copy(update=changes)
        refused(facts.model_copy(update={RECEIPT: forged}))
        with pytest.raises(ValidationError):
            c.build_prerequisite(
                facts.model_copy(update={RECEIPT: forged}),
                idempotency_key="v053-idempotency-key",
            )
    raw = facts.model_dump(mode="python")
    # Walk the actual embedded chain and attack every inherited model independently.
    paths = []

    def walk(value, path):
        if isinstance(value, dict):
            if "schema" in value:
                paths.append(path)
            for key, item in value.items():
                walk(item, (*path, key))

    walk(raw[RECEIPT], (RECEIPT,))
    assert len(paths) > 40
    for path in paths:
        hostile = copy.deepcopy(raw)
        node = hostile
        for key in path:
            node = node[key]
        node["unknown_lineage_field"] = "secret"
        refused(hostile)
    # Deep marker coercion cannot disappear through JSON serialization.
    hostile = copy.deepcopy(raw)
    nested = hostile[RECEIPT][RECEIPT + "_admission"]
    nested["worker_start_allowed"] = 0
    refused(hostile)
    nested["worker_start_allowed"] = False
    nested["inherited_limits_fingerprint"]["value"] = "f" * 64
    refused(hostile)


def test_recomputed_outer_fingerprints_do_not_authorize_corrupt_facts(facts):
    for field, value in (
        ("worker_start_allowed", True),
        ("worker_start_allowed", 0),
        ("credential_material_present", True),
        ("blockers", ()),
        ("controlled_queue_claim_recorded", False),
    ):
        raw = facts.model_dump(mode="python")
        raw[RECEIPT][field] = value
        fp = v052.receipt_record_fingerprint(raw[RECEIPT]).model_dump(mode="python")
        raw[RECEIPT]["receipt_record_fingerprint"] = fp
        raw["create"]["receipt_record_fingerprint"] = fp
        raw[STATUS]["receipt_record_fingerprint"] = fp
        sfp = v052.status_fingerprint(raw[STATUS]).model_dump(mode="python")
        raw[STATUS]["status_fingerprint"] = sfp
        raw["create"]["status_fingerprint"] = sfp
        refused(raw)


def test_stable_status_does_not_renew_expiry_and_status_drift_is_rejected(facts):
    receipt = getattr(facts, RECEIPT)
    raw = facts.model_dump(mode="python")
    raw["authority"]["request_received_at"] = receipt.valid_until
    refused(raw)
    for changes in (
        {"valid_until": "2099-01-01T00:00:00Z"},
        {"evaluated_at": "2099-01-01T00:00:00Z"},
        {"evaluated_at": "2026-08-27T12:00:00Z"},
        {"lifecycle": "expired"},
        {"blockers": ()},
        {"controlled_queue_acknowledgement_recorded": 1},
    ):
        raw = facts.model_dump(mode="python")
        raw[STATUS].update(changes)
        fp = v052.status_fingerprint(raw[STATUS]).model_dump(mode="python")
        raw[STATUS]["status_fingerprint"] = fp
        raw["create"]["status_fingerprint"] = fp
        refused(raw)


def test_request_is_closed_bounded_and_strict_json(facts):
    text = facts.create.model_dump_json()
    assert c.parse_create_json(text) == facts.create
    for invalid in (
        b"\xff",
        "{" + " " * c.MAX_CREATE_BYTES + "}",
        text.replace('"admission_id":', '"admission_id":"bad","admission_id":'),
        text.replace("-create-v1", "-create-v1-e\u0301"),
        '{"secret":' + "[" * 1000 + "0" + "]" * 1000 + "}",
    ):
        with pytest.raises(c.StrictContractError, match=c.SAFE_MESSAGE):
            c.parse_create_json(invalid)
    raw = facts.model_dump(mode="python")
    raw["oversized"] = "x" * c.MAX_MODEL_BYTES
    refused(raw)


def test_versioned_domains_and_permanent_subject(facts):
    record = c.build_prerequisite(facts, idempotency_key="v053-idempotency-key")
    assert (
        len(
            {
                c.fingerprint(domain, {}).value
                for domain in (
                    "record",
                    "status",
                    "request",
                    "subject",
                    "reservation",
                    "audit",
                )
            }
        )
        == 6
    )
    other_key = c.build_prerequisite(facts, idempotency_key="another-idempotency-key")
    assert other_key.subject_fingerprint == record.subject_fingerprint
    assert other_key.prerequisite_id == record.prerequisite_id
    assert (
        other_key.prerequisite_record_fingerprint
        != record.prerequisite_record_fingerprint
    )
    changed = facts.create.model_copy(update={"valid_until": "2099-01-01T00:00:00Z"})
    kwargs = {
        "operator_id": facts.operator_id,
        "candidate_record_id": facts.candidate_record_id,
    }
    assert c.request_fingerprint(**kwargs, create=changed) != c.request_fingerprint(
        **kwargs, create=facts.create
    )
    assert (
        c.subject_fingerprint(**kwargs, admission_id=facts.create.admission_id)
        == record.subject_fingerprint
    )


def test_rehashed_evaluation_and_evidence_cannot_change_authority_or_shape(facts):
    evaluation = c.evaluate_worker_activation_runtime_prerequisite(facts)
    for changes in (
        {"recognized_v052_receipt_count": 2},
        {"blockers": ()},
        {"worker_start_allowed": True},
        {"worker_activation_runtime_prerequisite_recorded": False},
        {"earliest_expiry": "2099-01-01T00:00:00Z"},
    ):
        raw = evaluation.model_dump(mode="python")
        raw.update(changes)
        raw["evaluation_fingerprint"] = c.evaluation_fingerprint(raw)
        with pytest.raises(ValidationError):
            c.WorkerActivationRuntimePrerequisiteEvaluationV1.model_validate(raw)
    record = c.build_prerequisite(facts, idempotency_key="v053-idempotency-key")
    for changes in (
        {"valid_until": "2099-01-01T00:00:00Z"},
        {"blockers": ()},
        {"admission_id": "00000000-0000-5000-8000-000000000000"},
    ):
        raw = record.model_dump(mode="python")
        raw.update(changes)
        raw["prerequisite_record_fingerprint"] = c.prerequisite_record_fingerprint(raw)
        with pytest.raises(ValidationError):
            c.WorkerActivationRuntimePrerequisiteV1.model_validate(raw)


def test_no_io_or_production_consumers():
    path = Path(c.__file__).resolve()
    tree = ast.parse(path.read_text())
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert imports == {
        "__future__",
        "datetime",
        "typing",
        "pydantic",
        "app.controlled_worker_queue_claim_lease_acknowledgement",
        "app.execution_permission_grant.contract",
        "app.installation_execution_admission.contract",
        "app.installation_plan.contract",
        "app.installation_targets.contract",
    }
    assert {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    } == {
        "json",
        "unicodedata",
    }
    forbidden = {
        "open",
        "exec",
        "eval",
        "__import__",
        "now",
        "utcnow",
        "read_text",
        "write_text",
        "connect",
        "send",
        "poll",
        "start",
        "execute",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            assert (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else ""
            ) not in forbidden
    root = path.parents[4]
    consumers = set()
    for service in ("atlas-core", "atlas-agent", "atlas-execution-worker"):
        for source in (root / "services" / service).rglob("*.py"):
            if source.parent == path.parent or source.name.startswith("test_"):
                continue
            if "worker_activation_runtime_prerequisite" in source.read_text():
                consumers.add(source.relative_to(root).as_posix())
    # Exact v0.54 evidence modules/API plus v0.53 API/permissions.
    assert consumers == {
        "services/atlas-core/app/worker_activation_runtime_admission/contract.py",
        "services/atlas-core/app/worker_activation_runtime_admission/readers.py",
        "services/atlas-core/app/worker_activation_runtime_admission/service.py",
        "services/atlas-core/app/worker_activation_runtime_admission/store.py",
        "services/atlas-core/app/routes/worker_activation_runtime_prerequisite.py",
        "services/atlas-core/app/routes/worker_activation_runtime_admission.py",
        "services/atlas-core/app/api/v1/router.py",
        "services/atlas-core/app/operator_auth/models.py",
    }


def test_all_envelopes_close_authority_and_validate_fingerprints(facts):
    record = c.build_prerequisite(facts, idempotency_key="v053-idempotency-key")
    status = c.derive_status(record, evaluated_at=record.recorded_at)
    collection = c._signed(
        c.WorkerActivationRuntimePrerequisiteCollectionV1,
        {
            "operator_id": record.operator_id,
            "candidate_record_id": record.candidate_record_id,
            "items": (record,),
            "count": 1,
        },
        "collection_fingerprint",
        c.collection_fingerprint,
    )
    reservation = c._signed(
        c.WorkerActivationRuntimePrerequisiteSubjectReservationV1,
        {
            "operator_id": record.operator_id,
            "candidate_record_id": record.candidate_record_id,
            "admission_id": record.admission_id,
            "reserved_at": record.recorded_at,
            "subject_fingerprint": record.subject_fingerprint,
            "idempotency_key_fingerprint": record.idempotency_key_fingerprint,
            "request_fingerprint": c.request_fingerprint(
                operator_id=record.operator_id,
                candidate_record_id=record.candidate_record_id,
                create=facts.create,
            ),
        },
        "reservation_fingerprint",
        c.reservation_fingerprint,
    )
    audit = c._signed(
        c.WorkerActivationRuntimePrerequisiteAuditEvidenceV1,
        {
            "operator_id": record.operator_id,
            "candidate_record_id": record.candidate_record_id,
            "occurred_at": record.recorded_at,
            "outcome": "recorded",
            "subject_fingerprint": record.subject_fingerprint,
            "correlation_fingerprint": c.fingerprint("correlation", "test"),
            "prerequisite_record_fingerprint": record.prerequisite_record_fingerprint,
            "worker_activation_runtime_prerequisite_recorded": True,
        },
        "audit_fingerprint",
        c.audit_fingerprint,
    )
    error = c.WorkerActivationRuntimePrerequisiteRedactedErrorV1(
        error_code="invalid_request",
        correlation_fingerprint=c.fingerprint("correlation", "test"),
    )
    envelopes = (
        record,
        status,
        collection,
        reservation,
        audit,
        error,
        c.WorkerActivationRuntimePrerequisiteResultV1(record=record, status=status),
        c.evaluate_worker_activation_runtime_prerequisite(facts),
        facts.create,
        facts.authority,
    )
    for model in envelopes:
        assert type(model).model_validate_json(model.model_dump_json()) == model
        raw = model.model_dump(mode="python")
        raw["extra"] = "secret"
        with pytest.raises(ValidationError):
            type(model).model_validate(raw)
        for field, definition in c.ClosedAuthorityV1.model_fields.items():
            if definition.default is False and not field.endswith("_material_present"):
                for value in (True, 0, "false"):
                    raw = model.model_dump(mode="python")
                    raw[field] = value
                    with pytest.raises(ValidationError):
                        type(model).model_validate(raw)
        text = model.model_dump_json().replace(
            '"schema":', '"schema":"duplicate","schema":', 1
        )
        with pytest.raises(ValueError):
            type(model).model_validate_json(text)
    for model, field, function, changes in (
        (
            collection,
            "collection_fingerprint",
            c.collection_fingerprint,
            {"items": (record, record), "count": 2},
        ),
        (
            reservation,
            "reservation_fingerprint",
            c.reservation_fingerprint,
            {"operator_id": "foreign"},
        ),
        (audit, "audit_fingerprint", c.audit_fingerprint, {"outcome": "indeterminate"}),
        (
            status,
            "status_fingerprint",
            c.status_fingerprint,
            {"valid_until": "2099-01-01T00:00:00Z"},
        ),
    ):
        raw = model.model_dump(mode="python")
        raw.update(changes)
        raw[field] = function(raw)
        with pytest.raises(ValidationError):
            type(model).model_validate(raw)


def test_stable_status_cannot_extend_earliest_inherited_expiry(facts):
    receipt = getattr(facts, RECEIPT)
    # This real complete lineage leaves only one second of inherited eligibility.
    assert receipt.valid_until == "2026-08-27T12:00:45Z"
    raw = facts.model_dump(mode="python")
    assert (
        c.evaluate_worker_activation_runtime_prerequisite(
            raw
        ).recognized_v052_receipt_count
        == 1
    )
    raw["authority"]["request_received_at"] = receipt.valid_until
    refused(raw)
    current = v052.derive_status(receipt, evaluated_at=receipt.valid_until)
    raw[STATUS] = current.model_dump(mode="python")
    raw["create"]["status_fingerprint"] = current.status_fingerprint
    refused(raw)
    with pytest.raises(ValidationError):
        c.WorkerActivationRuntimePrerequisiteValidationInputV1.model_validate(raw)
    stable = c.build_prerequisite(facts, idempotency_key="v053-idempotency-key")
    assert stable.valid_until == receipt.valid_until
    assert (
        c.derive_status(stable, evaluated_at=receipt.valid_until).lifecycle == "expired"
    )


def test_cycles_and_malformed_owner_clock_fail_closed_without_exception(facts):
    raw = facts.model_dump(mode="python")
    raw["cycle"] = raw
    refused(raw)
    for value in (None, {}, [], True, 3):
        raw = facts.model_dump(mode="python")
        raw["operator_id"] = value
        refused(raw)
        raw = facts.model_dump(mode="python")
        raw["authority"]["request_received_at"] = value
        refused(raw)


def test_serialized_bound_includes_expanded_defaults(facts, monkeypatch):
    minimal = facts.create.model_dump(mode="python", exclude_defaults=True)
    size_without_defaults = len(c.canonical_json(minimal))
    assert size_without_defaults < len(c.canonical_json(facts.create))
    monkeypatch.setattr(c, "MAX_MODEL_BYTES", size_without_defaults + 1)
    with pytest.raises(ValidationError, match="contract envelope exceeds bound"):
        c.WorkerActivationRuntimePrerequisiteCreateV1.model_validate(minimal)
