"""v0.54 closure: exact durable lineage, permanent replay denial and consumers."""

from datetime import datetime
from pathlib import Path
from typing import Literal, get_args, get_origin

import pytest
from pydantic import ValidationError

from app.worker_activation_runtime_admission import contract as c
from app.worker_activation_runtime_admission.readers import (
    WorkerActivationRuntimeAdmissionPrerequisiteStoreReader,
)
from app.worker_activation_runtime_admission.service import (
    WorkerActivationRuntimeAdmissionService,
)
from app.worker_activation_runtime_admission.store import (
    WorkerActivationRuntimeAdmissionStore,
)
from app.worker_activation_runtime_admission.test_service_store import counts
from app.worker_activation_runtime_prerequisite.test_contract import (
    facts as prior_facts,  # noqa: F401
)
from app.worker_activation_runtime_prerequisite.test_service_store import create, setup

ROOT = Path(__file__).resolve().parents[4]
MARKERS = (
    "worker_activation_runtime_admission",
    "worker-activation-runtime-admission",
    "workerActivationRuntimeAdmission",
    "WorkerActivationRuntimeAdmission",
    "WORKER_ACTIVATION_RUNTIME_ADMISSION",
)


def test_durable_v053_lineage_authority_and_restart_no_replay(tmp_path, request):
    predecessor_facts = request.getfixturevalue("prior_facts")
    prior, predecessor_store, _, clock = setup(tmp_path, predecessor_facts)
    prerequisite = create(prior, predecessor_facts).record
    before = predecessor_store.database_path.read_bytes()
    reader = WorkerActivationRuntimeAdmissionPrerequisiteStoreReader(
        store=type(predecessor_store)(predecessor_store.database_path), clock=clock
    )
    pair = reader.read_owned(
        operator_id=prerequisite.operator_id,
        candidate_record_id=prerequisite.candidate_record_id,
        prerequisite_id=prerequisite.prerequisite_id,
        valid_until=prerequisite.valid_until,
    )
    request = c.build_create(receipt=pair[0], receipt_status=pair[1])
    journal = WorkerActivationRuntimeAdmissionStore(tmp_path / "v054.sqlite")
    arguments = {
        "authenticated_operator_id": prerequisite.operator_id,
        "permission_verified": True,
        "candidate_record_id": prerequisite.candidate_record_id,
        "idempotency_key": "v054-release-closure",
        "correlation_id": "release-closure",
    }
    service = WorkerActivationRuntimeAdmissionService(
        prerequisite_reader=reader, store=journal, clock=clock
    )
    assert (
        service.create(request, **arguments).error_code
        == "installation_capability_unsupported"
    )
    assert counts(journal) == (0, 0, 0)
    service = WorkerActivationRuntimeAdmissionService(
        prerequisite_reader=reader, store=journal, clock=clock, enabled=True
    )
    result = service.create(request, **arguments)
    assert isinstance(result, c.WorkerActivationRuntimeAdmissionResultV1)
    record = result.record
    for field in (
        "prerequisite_id",
        "admission_id",
        "operator_id",
        "candidate_record_id",
        "valid_until",
    ):
        assert getattr(record, field) == getattr(prerequisite, field)
    assert record.runtime_admission_id not in {
        prerequisite.prerequisite_id,
        prerequisite.admission_id,
    }
    assert (
        request.prerequisite_record_fingerprint
        == prerequisite.prerequisite_record_fingerprint
    )
    assert request.status_fingerprint == pair[1].status_fingerprint
    assert (
        record.worker_activation_runtime_prerequisite.model_dump_json()
        == prerequisite.model_dump_json()
    )
    assert (
        record.worker_activation_runtime_prerequisite_status.model_dump_json()
        == pair[1].model_dump_json()
    )
    assert record.blockers == c.SUCCESS_BLOCKERS == c.v053.SUCCESS_BLOCKERS
    assert record.worker_activation_runtime_admission_recorded is True
    assert c.ClosedAuthorityV1().model_dump() == c.v053.ClosedAuthorityV1().model_dump()
    for model in (record, result.status, result):
        for name, field in type(model).model_fields.items():
            if (
                get_origin(field.annotation) is Literal
                and get_args(field.annotation)[0] is False
            ) or name.endswith("_material_present"):
                assert getattr(model, name) is False
                for invalid in (True, 0, 1, "false"):
                    with pytest.raises(ValidationError):
                        type(model).model_validate_json(
                            model.model_copy(update={name: invalid}).model_dump_json()
                        )

    def no_read(**kwargs):
        pytest.fail("restart duplicate and replay denial must not read prerequisites")

    reader.read_owned = no_read
    restarted = WorkerActivationRuntimeAdmissionService(
        prerequisite_reader=reader,
        store=WorkerActivationRuntimeAdmissionStore(journal.database_path),
        clock=lambda: datetime.fromisoformat(record.valid_until),
        enabled=True,
    )
    duplicate = restarted.create(request, **arguments)
    assert duplicate.exact_duplicate and duplicate.record == record
    assert duplicate.status.lifecycle == "expired"
    replay = restarted.create(
        request, **{**arguments, "idempotency_key": "another-v054-release-key"}
    )
    assert (
        replay.error_code == "permanent_subject_reserved" and replay.retryable is False
    )
    assert counts(journal) == (1, 1, 0)
    assert predecessor_store.database_path.read_bytes() == before


def test_exact_v054_production_consumers():
    expected = {
        # v0.55 P1/P2: exact reference-only contract and local evidence modules.
        "services/atlas-core/app/worker_activation_runtime_plan/contract.py",
        "services/atlas-core/app/worker_activation_runtime_plan/store.py",
        "services/atlas-core/app/worker_activation_runtime_plan/service.py",
        "services/atlas-core/app/worker_activation_runtime_plan/readers.py",
        "services/atlas-core/app/worker_activation_runtime_admission/contract.py",
        "services/atlas-core/app/worker_activation_runtime_admission/readers.py",
        "services/atlas-core/app/worker_activation_runtime_admission/service.py",
        "services/atlas-core/app/worker_activation_runtime_admission/store.py",
        "services/atlas-core/app/routes/worker_activation_runtime_admission.py",
        "services/atlas-core/app/routes/worker_activation_runtime_plan.py",
        "services/atlas-core/app/api/v1/router.py",
        "services/atlas-core/app/operator_auth/models.py",
        # v0.55 P4: exact GET-only reader, inherited types and nested evidence view.
        "services/mission-control/src/api/workerActivationRuntimePlan.ts",
        # v0.56: exact nested GET-only review evidence consumers.
        "services/mission-control/src/api/workerActivationRuntimePlanReview.ts",
        "services/mission-control/src/types/workerActivationRuntimePlan.ts",
        "services/mission-control/src/features/installation/WorkerActivationRuntimePlan.tsx",
        "services/mission-control/src/api/workerActivationRuntimeAdmission.ts",
        "services/mission-control/src/types/workerActivationRuntimeAdmission.ts",
        "services/mission-control/src/features/installation/WorkerActivationRuntimeAdmission.tsx",
        "services/mission-control/src/features/installation/WorkerActivationRuntimePrerequisite.tsx",
    }
    found = set()
    for area in (
        "services/atlas-core/app",
        "services/atlas-agent/app",
        "services/atlas-execution-worker/atlas_execution_worker",
        "services/mission-control/src",
    ):
        assert (ROOT / area).is_dir()
        for path in (ROOT / area).rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx", ".json", ".yaml", ".yml"}:
                continue
            if (
                path.name.startswith("test_")
                or ".test." in path.name
                or "test" in path.parts
            ):
                continue
            if any(marker in path.read_text() for marker in MARKERS):
                found.add(path.relative_to(ROOT).as_posix())
    assert found == expected


def test_normative_contract_keeps_exact_authority_ceiling_and_blockers():
    source = (
        ROOT / "docs/architecture/worker-activation-runtime-admission-v1.md"
    ).read_text()
    false_fields = {
        name
        for name, field in c.ClosedAuthorityV1.model_fields.items()
        if (
            get_origin(field.annotation) is Literal
            and get_args(field.annotation)[0] is False
        )
        or name.endswith("_material_present")
    }
    inventory = source.split("The following released authority/material fields", 1)[1]
    inventory = inventory.split("```text\n", 1)[1].split("```", 1)[0]
    assert set(inventory.splitlines()) == false_fields
    blockers = source.split("Success retains exactly these seven ordered blockers:", 1)[
        1
    ]
    blockers = blockers.split("```text\n", 1)[1].split("```", 1)[0]
    assert tuple(blockers.splitlines()) == c.SUCCESS_BLOCKERS
    assert (
        "Only `worker_activation_runtime_admission_recorded` may newly become true."
        in source
    )
