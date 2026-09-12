from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import Literal, get_args, get_origin

import pytest
from pydantic import ValidationError

from app.worker_activation_runtime_interface_prerequisite import contract as c
from app.worker_activation_runtime_plan_review import contract as v056
from app.worker_activation_runtime_plan_review.test_contract import (
    admission_facts,  # noqa: F401
    plan_facts,  # noqa: F401
    prior_facts,  # noqa: F401
)
from app.worker_activation_runtime_plan_review.test_contract import (
    facts as review_facts,  # noqa: F401
)

RECEIPT = "worker_activation_runtime_plan_review"
STATUS = RECEIPT + "_status"


@pytest.fixture(scope="module")
def facts(request):
    predecessor = request.getfixturevalue("review_facts")
    prior = v056.build_runtime_plan_review(
        predecessor, idempotency_key="v057-prerequisite-key"
    )
    status = v056.derive_status(prior, evaluated_at=prior.recorded_at)
    return c.WorkerActivationRuntimeInterfacePrerequisiteValidationInputV1(
        subject_previously_reserved=False,
        idempotency_key_previously_reserved=False,
        operator_id=prior.operator_id,
        candidate_record_id=prior.candidate_record_id,
        authority=c.WorkerActivationRuntimeInterfacePrerequisiteAuthorityContextV1(
            authenticated_operator_id=prior.operator_id,
            permission=c.PERMISSION,
            permission_verified=True,
            request_received_at=prior.recorded_at,
        ),
        create=c.build_create(receipt=prior, receipt_status=status),
        **{RECEIPT: prior, STATUS: status},
    )


def refused(raw):
    result = c.evaluate_worker_activation_runtime_interface_prerequisite(raw)
    assert not result.worker_activation_runtime_interface_prerequisite_recorded
    assert result.recognized_v056_review_count == 0
    assert result.earliest_expiry is None
    assert result.operator_id == "blocked-evaluation"
    assert result.evaluation_fingerprint == c.evaluation_fingerprint(result)
    return result


def test_success_is_deterministic_immutable_and_preserves_complete_lineage(facts):
    raw = facts.model_dump(mode="python")
    before = copy.deepcopy(raw)
    first = c.evaluate_worker_activation_runtime_interface_prerequisite(raw)
    assert first == c.evaluate_worker_activation_runtime_interface_prerequisite(facts)
    assert raw == before
    assert first.worker_activation_runtime_interface_prerequisite_recorded is True
    assert first.recognized_v056_review_count == 1
    assert first.blockers == v056.SUCCESS_BLOCKERS
    record = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v057-idempotency-key"
    )
    assert record == c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v057-idempotency-key"
    )
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
        c.WorkerActivationRuntimeInterfacePrerequisiteV1.model_validate_json(
            record.model_dump_json()
        )
        == record
    )
    status = c.derive_status(record, evaluated_at=record.recorded_at)
    result = c.WorkerActivationRuntimeInterfacePrerequisiteResultV1(
        record=record, status=status
    )
    assert result.record == record
    expired = c.derive_status(record, evaluated_at=record.valid_until)
    assert expired.lifecycle == "expired"
    assert expired.worker_activation_runtime_interface_prerequisite_recorded
    assert (
        c.WorkerActivationRuntimeInterfacePrerequisiteResultV1(
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
        ("create", "runtime_plan_review_id", "00000000-0000-5000-8000-000000000000"),
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
    for field, definition in v056.ClosedAuthorityV1.model_fields.items():
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
        ("create", "runtime_plan_review_record_fingerprint"),
        ("create", "status_fingerprint"),
        (RECEIPT, "runtime_plan_review_record_fingerprint"),
        (RECEIPT, "subject_fingerprint"),
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
            c.build_runtime_interface_prerequisite(
                facts.model_copy(update={RECEIPT: forged}),
                idempotency_key="v057-idempotency-key",
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
    nested = hostile[RECEIPT]["worker_activation_runtime_plan"][
        "worker_activation_runtime_admission"
    ]["worker_activation_runtime_prerequisite"][
        "controlled_worker_queue_claim_lease_acknowledgement"
    ]
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
        fp = v056.runtime_plan_review_record_fingerprint(raw[RECEIPT]).model_dump(
            mode="python"
        )
        raw[RECEIPT]["runtime_plan_review_record_fingerprint"] = fp
        raw["create"]["runtime_plan_review_record_fingerprint"] = fp
        raw[STATUS]["runtime_plan_review_record_fingerprint"] = fp
        sfp = v056.status_fingerprint(raw[STATUS]).model_dump(mode="python")
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
        fp = v056.status_fingerprint(raw[STATUS]).model_dump(mode="python")
        raw[STATUS]["status_fingerprint"] = fp
        raw["create"]["status_fingerprint"] = fp
        refused(raw)


def test_request_is_closed_bounded_and_strict_json(facts):
    text = facts.create.model_dump_json()
    assert c.parse_create_json(text) == facts.create
    for invalid in (
        {},
        [],
        None,
        123,
        b"\xff",
        "{" + " " * c.MAX_CREATE_BYTES + "}",
        text.replace(
            '"runtime_plan_review_id":',
            '"runtime_plan_review_id":"bad","runtime_plan_review_id":',
        ),
        text.replace("-create-v1", "-create-v1-e\u0301"),
        '{"secret":' + "[" * 1000 + "0" + "]" * 1000 + "}",
    ):
        with pytest.raises(c.StrictContractError, match=c.SAFE_MESSAGE):
            c.parse_create_json(invalid)
    raw = facts.model_dump(mode="python")
    raw["oversized"] = "x" * c.MAX_MODEL_BYTES
    refused(raw)


def test_direct_create_json_validation_enforces_wire_bounds_and_utf8(facts):
    text = facts.create.model_dump_json()
    model = c.WorkerActivationRuntimeInterfacePrerequisiteCreateV1
    for valid in (text, text.encode("utf-8"), bytearray(text, "utf-8")):
        assert model.model_validate_json(valid) == facts.create
    # Whitespace counts even when the decoded model is small and otherwise valid.
    for invalid in (
        text + " " * c.MAX_CREATE_BYTES,
        text.encode("utf-16"),
        text.encode("utf-32"),
    ):
        with pytest.raises(ValueError):
            model.model_validate_json(invalid)


def test_json_wire_limit_counts_utf8_bytes(monkeypatch):
    text = '{"operator_id":"é"}'
    monkeypatch.setattr(c.ContractModel, "_json_byte_limit", len(text))
    with pytest.raises(ValueError, match="contract envelope exceeds bound"):
        c.WorkerActivationRuntimeInterfacePrerequisiteCollectionV1.model_validate_json(
            text
        )


def test_versioned_domains_and_permanent_subject(facts):
    record = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v057-idempotency-key"
    )
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
    other_key = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="another-idempotency-key"
    )
    assert other_key.subject_fingerprint == record.subject_fingerprint
    assert (
        other_key.runtime_interface_prerequisite_id
        == record.runtime_interface_prerequisite_id
    )
    assert (
        other_key.runtime_interface_prerequisite_record_fingerprint
        != record.runtime_interface_prerequisite_record_fingerprint
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
        c.subject_fingerprint(
            **kwargs, runtime_plan_review_id=facts.create.runtime_plan_review_id
        )
        == record.subject_fingerprint
    )


def test_rehashed_evaluation_and_evidence_cannot_change_authority_or_shape(facts):
    evaluation = c.evaluate_worker_activation_runtime_interface_prerequisite(facts)
    for changes in (
        {"recognized_v056_review_count": 2},
        {"blockers": ()},
        {"worker_start_allowed": True},
        {"worker_activation_runtime_interface_prerequisite_recorded": False},
        {"earliest_expiry": "2099-01-01T00:00:00Z"},
    ):
        raw = evaluation.model_dump(mode="python")
        raw.update(changes)
        raw["evaluation_fingerprint"] = c.evaluation_fingerprint(raw)
        with pytest.raises(ValidationError):
            c.WorkerActivationRuntimeInterfacePrerequisiteEvaluationV1.model_validate(
                raw
            )
    record = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v057-idempotency-key"
    )
    for changes in (
        {"valid_until": "2099-01-01T00:00:00Z"},
        {"blockers": ()},
        {"runtime_plan_review_id": "00000000-0000-5000-8000-000000000000"},
    ):
        raw = record.model_dump(mode="python")
        raw.update(changes)
        raw["runtime_interface_prerequisite_record_fingerprint"] = (
            c.runtime_interface_prerequisite_record_fingerprint(raw)
        )
        with pytest.raises(ValidationError):
            c.WorkerActivationRuntimeInterfacePrerequisiteV1.model_validate(raw)


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
        "app.worker_activation_runtime_plan_review",
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
    markers = (
        "worker_activation_runtime_interface_prerequisite",
        "worker-activation-runtime-interface-prerequisite",
        "WorkerActivationRuntimeInterfacePrerequisite",
        "workerActivationRuntimeInterfacePrerequisite",
        "WORKER_ACTIVATION_RUNTIME_INTERFACE_PREREQUISITE",
    )
    for service in (
        "atlas-core",
        "atlas-agent",
        "atlas-execution-worker",
        "mission-control",
    ):
        for source in (root / "services" / service).rglob("*"):
            if source.suffix not in {".py", ".ts", ".tsx", ".json", ".yaml", ".yml"}:
                continue
            if source == path or source.name.startswith("test_"):
                continue
            if ".test." in source.name or "test" in source.parts:
                continue
            if any(marker in source.read_text() for marker in markers):
                consumers.add(source.relative_to(root).as_posix())
    assert consumers == {
        "services/mission-control/src/api/workerActivationRuntimeInterfacePrerequisite.ts",
        "services/mission-control/src/types/workerActivationRuntimeInterfacePrerequisite.ts",
        "services/mission-control/src/hooks/useWorkerActivationRuntimeInterfacePrerequisite.ts",
        "services/mission-control/src/features/installation/WorkerActivationRuntimeInterfacePrerequisite.tsx",
        "services/mission-control/src/features/installation/WorkerActivationRuntimePlanReview.tsx",
        "services/atlas-core/app/api/v1/router.py",
        "services/atlas-core/app/operator_auth/models.py",
        "services/atlas-core/app/routes/worker_activation_runtime_interface_prerequisite.py",
        "services/atlas-core/app/worker_activation_runtime_interface_prerequisite/readers.py",
        "services/atlas-core/app/worker_activation_runtime_interface_prerequisite/service.py",
        "services/atlas-core/app/worker_activation_runtime_interface_prerequisite/store.py",
    }


def test_all_envelopes_close_authority_and_validate_fingerprints(facts):
    record = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v057-idempotency-key"
    )
    status = c.derive_status(record, evaluated_at=record.recorded_at)
    collection = c._signed(
        c.WorkerActivationRuntimeInterfacePrerequisiteCollectionV1,
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
        c.WorkerActivationRuntimeInterfacePrerequisiteSubjectReservationV1,
        {
            "operator_id": record.operator_id,
            "candidate_record_id": record.candidate_record_id,
            "runtime_plan_review_id": record.runtime_plan_review_id,
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
        c.WorkerActivationRuntimeInterfacePrerequisiteAuditEvidenceV1,
        {
            "operator_id": record.operator_id,
            "candidate_record_id": record.candidate_record_id,
            "occurred_at": record.recorded_at,
            "outcome": "recorded",
            "subject_fingerprint": record.subject_fingerprint,
            "correlation_fingerprint": c.fingerprint("correlation", "test"),
            "runtime_interface_prerequisite_record_fingerprint": record.runtime_interface_prerequisite_record_fingerprint,
            "worker_activation_runtime_plan_recorded": True,
            "worker_activation_runtime_plan_review_recorded": True,
            "worker_activation_runtime_interface_prerequisite_recorded": True,
        },
        "audit_fingerprint",
        c.audit_fingerprint,
    )
    error = c.WorkerActivationRuntimeInterfacePrerequisiteRedactedErrorV1(
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
        c.WorkerActivationRuntimeInterfacePrerequisiteResultV1(
            record=record, status=status
        ),
        c.evaluate_worker_activation_runtime_interface_prerequisite(facts),
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
        c.evaluate_worker_activation_runtime_interface_prerequisite(
            raw
        ).recognized_v056_review_count
        == 1
    )
    raw["authority"]["request_received_at"] = receipt.valid_until
    refused(raw)
    current = v056.derive_status(receipt, evaluated_at=receipt.valid_until)
    raw[STATUS] = current.model_dump(mode="python")
    raw["create"]["status_fingerprint"] = current.status_fingerprint
    refused(raw)
    with pytest.raises(ValidationError):
        c.WorkerActivationRuntimeInterfacePrerequisiteValidationInputV1.model_validate(
            raw
        )
    stable = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v057-idempotency-key"
    )
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
        c.WorkerActivationRuntimeInterfacePrerequisiteCreateV1.model_validate(minimal)


@pytest.mark.parametrize(
    "field",
    [
        "subject_previously_reserved",
        "idempotency_key_previously_reserved",
    ],
)
@pytest.mark.parametrize("value", [True, None, 0, 1, "false", "missing"])
def test_replayed_or_unknown_reservation_facts_fail_closed(facts, field, value):
    raw = facts.model_dump(mode="python")
    if value == "missing":
        del raw[field]
    else:
        raw[field] = value
    refused(raw)
    with pytest.raises(ValidationError):
        c.build_runtime_interface_prerequisite(
            type(facts).model_construct(**raw), idempotency_key="v057-hostile-replay"
        )


def test_frozen_versioned_hash_and_uuid_vectors():
    import hashlib
    import json
    import uuid

    vectors = json.loads(
        Path(__file__).with_name("fingerprint_vectors.json").read_text()
    )
    for domain in (
        "subject",
        "request",
        "record",
        "status",
        "collection",
        "idempotency-key",
        "reservation",
        "audit",
        "evaluation",
        "correlation",
    ):
        actual = c.fingerprint(domain, {})
        assert actual.value == vectors[domain]
        assert actual.algorithm == "sha256"
        assert actual.canonicalization == "atlas-jcs-nfc-v1"
        assert (
            actual.value
            == hashlib.sha256(
                f"atlas:worker-activation-runtime-interface-prerequisite-{domain}:v1".encode()
                + b"\0{}"
            ).hexdigest()
        )
    subject = c.subject_fingerprint(
        operator_id="operator-a",
        candidate_record_id="00000000-0000-4000-8000-000000000000",
        runtime_plan_review_id="00000000-0000-5000-8000-000000000000",
    )

    # Independently implement the documented ASCII vector canonicalization and
    # UUID5 seed; do not use any Core hashing or UUID helper for expected values.
    def independent_hash(domain, value):
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(domain.encode() + b"\0" + encoded).hexdigest()

    prefix = "atlas:worker-activation-runtime-interface-prerequisite"
    expected_subject = independent_hash(
        prefix + "-subject:v1",
        {
            "operator_id": "operator-a",
            "candidate_record_id": "00000000-0000-4000-8000-000000000000",
            "runtime_plan_review_id": "00000000-0000-5000-8000-000000000000",
        },
    )
    assert expected_subject == vectors["subject_vector"]
    domain = prefix + "-id:v1"
    seed = independent_hash(
        domain,
        {
            "algorithm": "sha256",
            "canonicalization": "atlas-jcs-nfc-v1",
            "value": expected_subject,
        },
    )
    assert (
        str(
            uuid.uuid5(
                uuid.UUID("7bdf38b6-89a9-5d12-a0c1-33db5f733183"), f"{domain}:{seed}"
            )
        )
        == vectors["runtime_interface_prerequisite_id"]
    )
    assert subject.value == vectors["subject_vector"]
    assert (
        c.derived_runtime_interface_prerequisite_id(subject)
        == vectors["runtime_interface_prerequisite_id"]
    )


def test_distinct_identities_and_canonical_recursive_evidence(facts):
    record = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v057-exact-lineage"
    )
    prior = getattr(facts, RECEIPT)
    assert record.runtime_plan_review_id == prior.runtime_plan_review_id
    assert record.admission_id == prior.admission_id
    assert (
        len(
            {
                record.runtime_interface_prerequisite_id,
                record.runtime_plan_review_id,
                record.admission_id,
            }
        )
        == 3
    )
    assert c.canonical_json(getattr(record, RECEIPT)) == c.canonical_json(prior)
    assert c.canonical_json(getattr(record, STATUS)) == c.canonical_json(
        getattr(facts, STATUS)
    )
    for field in (
        "runtime_interface_prerequisite_id",
        "runtime_plan_review_id",
        "admission_id",
    ):
        raw = record.model_dump(mode="python")
        raw[field] = "00000000-0000-5000-8000-000000000000"
        raw["runtime_interface_prerequisite_record_fingerprint"] = (
            c.runtime_interface_prerequisite_record_fingerprint(raw)
        )
        with pytest.raises(ValidationError):
            c.WorkerActivationRuntimeInterfacePrerequisiteV1.model_validate(raw)


def test_recursive_hash_and_owner_corruption(facts):
    raw = facts.model_dump(mode="python")
    paths = []

    def walk(node, path):
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if key in ("operator_id", "candidate_record_id") or key.endswith(
                "_fingerprint"
            ):
                paths.append((*path, key))
            else:
                walk(value, (*path, key))

    walk(raw[RECEIPT], (RECEIPT,))
    assert len(paths) > 100
    for path in paths:
        hostile = copy.deepcopy(raw)
        node = hostile
        for key in path[:-1]:
            node = node[key]
        field = path[-1]
        if field.endswith("_fingerprint"):
            node[field]["value"] = "f" * 64
        elif field == "operator_id":
            node[field] = "foreign-owner"
        else:
            node[field] = "ffffffff-ffff-4fff-8fff-ffffffffffff"
        refused(hostile)


def test_missing_verification_and_forged_top_level_models_fail_closed(facts):
    raw = facts.model_dump(mode="python")
    del raw["authority"]["permission_verified"]
    refused(raw)
    for changes in (
        {"unknown": "secret"},
        {"home_assistant": True},
        {"authority": {}},
        {"worker_start_allowed": True},
    ):
        forged = facts.model_copy(update=changes)
        refused(forged)
        with pytest.raises(ValidationError):
            c.build_runtime_interface_prerequisite(
                forged, idempotency_key="v057-forged-input"
            )


def test_rehashed_status_identity_is_derived_from_exact_subject(facts):
    record = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v057-status-identity-key"
    )
    status = c.derive_status(record, evaluated_at=record.recorded_at)
    raw = status.model_dump(mode="python")
    raw["runtime_interface_prerequisite_id"] = record.runtime_plan_review_id
    raw["status_fingerprint"] = c.status_fingerprint(raw)
    with pytest.raises(ValidationError):
        c.WorkerActivationRuntimeInterfacePrerequisiteStatusV1.model_validate(raw)


def test_plan_pins_all_four_ids_and_exact_expiry(facts):
    record = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v057-pinned-identity"
    )
    prior = getattr(facts, RECEIPT)
    assert record.prerequisite_id == prior.prerequisite_id
    assert (
        len(
            {
                record.runtime_interface_prerequisite_id,
                record.runtime_plan_review_id,
                record.prerequisite_id,
                record.admission_id,
            }
        )
        == 4
    )
    status = c.derive_status(record, evaluated_at=record.recorded_at)
    assert status.prerequisite_id == prior.prerequisite_id
    # Correct outer hashes cannot authorize altered expiry or inherited identity.
    from datetime import timedelta

    later = c.v056.v055.v054.v053.v052._instant(record.valid_until) + timedelta(
        seconds=1
    )
    for field, value in (
        ("valid_until", record.recorded_at),
        ("valid_until", later.strftime("%Y-%m-%dT%H:%M:%SZ")),
        ("prerequisite_id", record.admission_id),
    ):
        raw = record.model_dump(mode="python")
        raw[field] = value
        raw["runtime_interface_prerequisite_record_fingerprint"] = (
            c.runtime_interface_prerequisite_record_fingerprint(raw)
        )
        with pytest.raises(ValidationError):
            c.WorkerActivationRuntimeInterfacePrerequisiteV1.model_validate(raw)


def test_normative_false_inventory_is_exact():
    source = (
        Path(c.__file__).resolve().parents[4]
        / "docs/architecture/worker-activation-runtime-plan-v1.md"
    ).read_text()
    inventory = (
        source.split("fields remain strictly false:\n\n```text\n", 1)[1]
        .split("```", 1)[0]
        .splitlines()
    )
    assert len(inventory) == 67
    assert {
        name: (field.annotation, field.default)
        for name, field in c.ClosedAuthorityV1.model_fields.items()
    } == {
        name: (field.annotation, field.default)
        for name, field in v056.ClosedAuthorityV1.model_fields.items()
    }
    for name in inventory:
        assert c.ClosedAuthorityV1().model_dump()[name] is False
        for value in (True, 0, 1, "false", None):
            with pytest.raises(ValidationError):
                c.ClosedAuthorityV1.model_validate({name: value})


def test_review_inventory_are_exact_and_never_caller_claims(facts):
    evaluation = c.evaluate_worker_activation_runtime_interface_prerequisite(facts)
    record = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v057-inventory-key"
    )
    status = c.derive_status(record, evaluated_at=record.recorded_at)
    expected = c.SUCCESS_INVENTORY
    assert c.SUCCESS_INVENTORY == expected
    assert refused({}).inventory == ()
    for model, field, sign in (
        (evaluation, "evaluation_fingerprint", c.evaluation_fingerprint),
        (
            record,
            "runtime_interface_prerequisite_record_fingerprint",
            c.runtime_interface_prerequisite_record_fingerprint,
        ),
        (status, "status_fingerprint", c.status_fingerprint),
    ):
        assert (
            model.profile
            == "core_owned_reference_only_runtime_interface_prerequisite_v1"
        )
        assert model.inventory == expected
        for changes in (
            {"inventory": ()},
            {"inventory": tuple(reversed(expected))},
            {"inventory": expected + (expected[0],)},
            {"inventory": ("runtime_ready",)},
            {"profile": "design_approved"},
        ):
            raw = model.model_dump(mode="python")
            raw.update(changes)
            raw[field] = sign(raw)
            with pytest.raises(ValidationError):
                type(model).model_validate(raw)
    for field, value in (
        ("inventory", expected),
        ("profile", c.PROFILE),
        ("design", {}),
    ):
        raw = facts.model_dump(mode="python")
        raw["create"][field] = value
        refused(raw)


def test_all_five_ids_and_recursive_bytes_remain_exact(facts):
    record = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v057-five-ids-key"
    )
    prior = getattr(facts, RECEIPT)
    fields = (
        "runtime_plan_review_id",
        "runtime_admission_id",
        "prerequisite_id",
        "admission_id",
    )
    assert (
        len(
            {
                record.runtime_interface_prerequisite_id,
                *(getattr(record, f) for f in fields),
            }
        )
        == 5
    )
    assert all(getattr(record, f) == getattr(prior, f) for f in fields)
    assert (
        record.worker_activation_runtime_plan_review.model_dump_json()
        == prior.model_dump_json()
    )
    assert (
        record.worker_activation_runtime_plan_review_status.model_dump_json()
        == getattr(facts, STATUS).model_dump_json()
    )
    raw = record.model_dump(mode="python")
    raw["runtime_admission_id"] = record.admission_id
    raw["runtime_interface_prerequisite_record_fingerprint"] = (
        c.runtime_interface_prerequisite_record_fingerprint(raw)
    )
    with pytest.raises(ValidationError):
        type(record).model_validate(raw)


def test_predecessor_status_is_exact_even_when_independently_valid(facts):
    # Status validators cannot know the record's inherited IDs. Pair equality must.
    raw = facts.model_dump(mode="python")
    raw[STATUS]["prerequisite_id"] = raw[STATUS]["admission_id"]
    raw[STATUS]["status_fingerprint"] = v056.status_fingerprint(raw[STATUS])
    v056.WorkerActivationRuntimePlanReviewStatusV1.model_validate(raw[STATUS])
    raw["create"]["status_fingerprint"] = raw[STATUS]["status_fingerprint"]
    refused(raw)


def test_fixed_inventory_matches_normative_mapping_and_is_deeply_immutable(facts):
    source = (
        Path(c.__file__).resolve().parents[4]
        / "docs/architecture/worker-activation-runtime-interface-prerequisite-v1.md"
    ).read_text()
    import re

    rows = [
        tuple(re.findall(r"`([^`]+)`", line))
        for line in source.splitlines()
        if line.startswith("| `") and line.count("`") == 6
    ][1:]
    assert len(rows) == 7
    assert tuple(row[0] for row in rows) == c.SUCCESS_BLOCKERS
    assert tuple(
        (entry.blocker, entry.owner, entry.required_proof)
        for entry in c.SUCCESS_INVENTORY
    ) == tuple(rows)
    for index, entry in enumerate(c.SUCCESS_INVENTORY):
        with pytest.raises(ValidationError):
            entry.owner = "worker_authority"
        for field in ("owner", "required_proof"):
            raw = entry.model_dump()
            raw[field] = getattr(c.SUCCESS_INVENTORY[(index + 1) % 7], field)
            with pytest.raises(ValidationError):
                c.InventoryEntryV1.model_validate(raw)
        for extra in ("satisfied", "approved", "endpoint"):
            with pytest.raises(ValidationError):
                c.InventoryEntryV1.model_validate({**entry.model_dump(), extra: True})
    raw = facts.model_dump(mode="python")
    raw["create"]["inventory"] = c.SUCCESS_INVENTORY
    assert refused(raw).inventory == ()


def test_full_envelope_bounds_and_all_six_identities(facts, monkeypatch):
    record = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v057-size-and-identity"
    )
    status = c.derive_status(record, evaluated_at=record.recorded_at)
    result = c.WorkerActivationRuntimeInterfacePrerequisiteResultV1(
        record=record, status=status
    )
    collection = c._signed(
        c.WorkerActivationRuntimeInterfacePrerequisiteCollectionV1,
        {
            "operator_id": record.operator_id,
            "candidate_record_id": record.candidate_record_id,
            "items": (record,),
            "count": 1,
        },
        "collection_fingerprint",
        c.collection_fingerprint,
    )
    ids = (
        "runtime_plan_review_id",
        "runtime_plan_id",
        "runtime_admission_id",
        "prerequisite_id",
        "admission_id",
    )
    assert (
        len(
            {
                record.runtime_interface_prerequisite_id,
                *(getattr(record, field) for field in ids),
            }
        )
        == 6
    )
    for field in ids:
        assert getattr(record, field) == getattr(getattr(facts, RECEIPT), field)
        assert getattr(status, field) == getattr(record, field)
        raw = record.model_dump(mode="python")
        raw[field] = record.runtime_interface_prerequisite_id
        raw["runtime_interface_prerequisite_record_fingerprint"] = (
            c.runtime_interface_prerequisite_record_fingerprint(raw)
        )
        with pytest.raises(ValidationError):
            type(record).model_validate(raw)
    for model in (record, result, collection):
        size = len(c.canonical_json(model))
        assert size < 192 * 1024
        with monkeypatch.context() as patch:
            patch.setattr(c, "MAX_MODEL_BYTES", size - 1)
            with pytest.raises(
                ValidationError, match="contract envelope exceeds bound"
            ):
                type(model).model_validate(model)
    raw = collection.model_dump(mode="python")
    raw.update(items=(record,) * 16, count=16)
    assert len(c.canonical_json(raw)) > c.MAX_MODEL_BYTES
    with pytest.raises(ValidationError, match="contract envelope exceeds bound"):
        type(collection).model_validate(raw)


def test_predecessor_findings_and_constructed_inventory_cannot_be_forged(facts):
    raw = facts.model_dump(mode="python")
    raw[RECEIPT]["findings"] = ()
    fp = v056.runtime_plan_review_record_fingerprint(raw[RECEIPT])
    raw[RECEIPT]["runtime_plan_review_record_fingerprint"] = fp
    raw["create"]["runtime_plan_review_record_fingerprint"] = fp
    raw[STATUS]["runtime_plan_review_record_fingerprint"] = fp
    sfp = v056.status_fingerprint(raw[STATUS])
    raw[STATUS]["status_fingerprint"] = sfp
    raw["create"]["status_fingerprint"] = sfp
    refused(raw)
    record = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v057-constructed-inventory"
    )
    bad = c.SUCCESS_INVENTORY[0].model_copy(update={"approved": True})
    forged = record.model_copy(update={"inventory": (bad, *c.SUCCESS_INVENTORY[1:])})
    with pytest.raises(ValidationError):
        type(record).model_validate(forged)


def test_mission_control_inventory_matches_authoritative_core():
    import json

    root = Path(__file__).resolve().parents[4]
    source = (
        root
        / "services/mission-control/src/api/workerActivationRuntimeInterfacePrerequisite.ts"
    ).read_text()
    inventory = json.loads(source.split("const INVENTORY = ", 1)[1].split(";", 1)[0])
    assert inventory == [entry.model_dump(mode="json") for entry in c.SUCCESS_INVENTORY]


def test_mission_control_golden_is_complete_authoritative_core_evidence():
    import json

    root = Path(__file__).resolve().parents[4]
    # Generated with build_runtime_interface_prerequisite, derive_status and the
    # signed collection builder. Keep real recursive fingerprints in UI tests.
    golden = json.loads(
        (
            root
            / "services/mission-control/src/test/workerActivationRuntimeInterfacePrerequisite.core.json"
        ).read_text()
    )
    result = c.WorkerActivationRuntimeInterfacePrerequisiteResultV1.model_validate(
        golden["result"]
    )
    collection = c.WorkerActivationRuntimeInterfacePrerequisiteCollectionV1.model_validate(
        {**golden["collection"], "items": [golden["result"]["record"]]}
    )
    assert collection.items == (result.record,)
