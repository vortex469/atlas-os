"""v0.56 closure: exact durable lineage, permanent replay denial and consumers."""

from datetime import datetime
from pathlib import Path
from typing import Literal, get_args, get_origin

import pytest
from pydantic import ValidationError

from app.worker_activation_runtime_plan.test_contract import (
    admission_facts,  # noqa: F401
    prior_facts,  # noqa: F401
)
from app.worker_activation_runtime_plan.test_contract import (
    facts as plan_facts,  # noqa: F401
)
from app.worker_activation_runtime_plan.test_service_store import create, setup
from app.worker_activation_runtime_plan_review import contract as c
from app.worker_activation_runtime_plan_review.readers import (
    WorkerActivationRuntimePlanReviewPrerequisiteStoreReader,
)
from app.worker_activation_runtime_plan_review.service import (
    WorkerActivationRuntimePlanReviewService,
)
from app.worker_activation_runtime_plan_review.store import (
    WorkerActivationRuntimePlanReviewStore,
)
from app.worker_activation_runtime_plan_review.test_service_store import counts

ROOT = Path(__file__).resolve().parents[4]
MARKERS = (
    "worker_activation_runtime_plan_review",
    "worker-activation-runtime-plan-review",
    "workerActivationRuntimePlanReview",
    "WorkerActivationRuntimePlanReview",
    "WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW",
)


def test_durable_v055_lineage_authority_and_restart_no_replay(tmp_path, request):
    predecessor_facts = request.getfixturevalue("plan_facts")
    prior, predecessor_store, _, clock = setup(tmp_path, predecessor_facts)
    prerequisite = create(prior, predecessor_facts).record
    before = predecessor_store.database_path.read_bytes()
    reader = WorkerActivationRuntimePlanReviewPrerequisiteStoreReader(
        store=type(predecessor_store)(predecessor_store.database_path), clock=clock
    )
    pair = reader.read_owned(
        operator_id=prerequisite.operator_id,
        candidate_record_id=prerequisite.candidate_record_id,
        runtime_plan_id=prerequisite.runtime_plan_id,
        valid_until=prerequisite.valid_until,
    )
    request = c.build_create(receipt=pair[0], receipt_status=pair[1])
    journal = WorkerActivationRuntimePlanReviewStore(tmp_path / "v056.sqlite")
    arguments = {
        "authenticated_operator_id": prerequisite.operator_id,
        "permission_verified": True,
        "candidate_record_id": prerequisite.candidate_record_id,
        "idempotency_key": "v056-release-closure",
        "correlation_id": "release-closure",
    }
    service = WorkerActivationRuntimePlanReviewService(
        prerequisite_reader=reader, store=journal, clock=clock
    )
    assert (
        service.create(request, **arguments).error_code
        == "installation_capability_unsupported"
    )
    assert counts(journal) == (0, 0, 0)
    service = WorkerActivationRuntimePlanReviewService(
        prerequisite_reader=reader, store=journal, clock=clock, enabled=True
    )
    result = service.create(request, **arguments)
    assert isinstance(result, c.WorkerActivationRuntimePlanReviewResultV1)
    record = result.record
    for field in (
        "runtime_plan_id",
        "runtime_admission_id",
        "prerequisite_id",
        "admission_id",
        "operator_id",
        "candidate_record_id",
        "valid_until",
    ):
        assert getattr(record, field) == getattr(prerequisite, field)
    assert record.runtime_plan_review_id not in {
        prerequisite.runtime_plan_id,
        prerequisite.runtime_admission_id,
        prerequisite.prerequisite_id,
        prerequisite.admission_id,
    }
    assert (
        request.runtime_plan_record_fingerprint
        == prerequisite.runtime_plan_record_fingerprint
    )
    assert request.status_fingerprint == pair[1].status_fingerprint
    assert (
        record.runtime_plan_review_record_fingerprint
        == c.runtime_plan_review_record_fingerprint(record)
    )
    assert (
        record.worker_activation_runtime_plan.model_dump_json()
        == prerequisite.model_dump_json()
    )
    assert (
        record.worker_activation_runtime_plan_status.model_dump_json()
        == pair[1].model_dump_json()
    )
    assert record.blockers == c.SUCCESS_BLOCKERS == c.v055.SUCCESS_BLOCKERS
    assert record.worker_activation_runtime_plan_review_recorded is True
    assert c.ClosedAuthorityV1().model_dump() == c.v055.ClosedAuthorityV1().model_dump()
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
    restarted = WorkerActivationRuntimePlanReviewService(
        prerequisite_reader=reader,
        store=WorkerActivationRuntimePlanReviewStore(journal.database_path),
        clock=lambda: datetime.fromisoformat(record.valid_until),
        enabled=True,
    )
    duplicate = restarted.create(request, **arguments)
    assert duplicate.exact_duplicate and duplicate.record == record
    assert duplicate.status.lifecycle == "expired"
    replay = restarted.create(
        request, **{**arguments, "idempotency_key": "another-v056-release-key"}
    )
    assert (
        replay.error_code == "permanent_subject_reserved" and replay.retryable is False
    )
    assert counts(journal) == (1, 1, 0)
    assert predecessor_store.database_path.read_bytes() == before


def test_exact_v056_production_consumers():
    expected = {
        "services/atlas-core/app/worker_activation_runtime_plan_review/contract.py",
        "services/atlas-core/app/worker_activation_runtime_plan_review/service.py",
        "services/atlas-core/app/worker_activation_runtime_plan_review/store.py",
        "services/atlas-core/app/worker_activation_runtime_plan_review/readers.py",
        "services/atlas-core/app/routes/worker_activation_runtime_plan_review.py",
        "services/atlas-core/app/api/v1/router.py",
        "services/atlas-core/app/operator_auth/models.py",
        "services/mission-control/src/api/workerActivationRuntimePlanReview.ts",
        "services/mission-control/src/types/workerActivationRuntimePlanReview.ts",
        "services/mission-control/src/features/installation/WorkerActivationRuntimePlanReview.tsx",
        "services/mission-control/src/features/installation/WorkerActivationRuntimePlan.tsx",
        "services/mission-control/src/hooks/useWorkerActivationRuntimePlanReview.ts",
    }
    found = set()
    for area in (
        "services/atlas-core/app",
        "services/atlas-agent/app",
        "services/atlas-execution-worker/atlas_execution_worker",
        "services/mission-control/src",
        "config",
        "deploy",
        "scripts",
    ):
        assert (ROOT / area).is_dir()
        for path in (ROOT / area).rglob("*"):
            if not path.is_file():
                continue
            if not (area == "scripts" and not path.suffix) and path.suffix not in {
                ".py",
                ".ts",
                ".tsx",
                ".json",
                ".yaml",
                ".yml",
                ".sh",
            }:
                continue
            if (
                path.name.startswith("test_")
                or ".test." in path.name
                or "test" in path.parts
            ):
                continue
            if any(marker in path.read_text() for marker in MARKERS):
                found.add(path.relative_to(ROOT).as_posix())
    # Root compose and example environment files are deployment surfaces too.
    for path in (*ROOT.glob("compose*.yaml"), ROOT / ".env.example"):
        if any(marker in path.read_text() for marker in MARKERS):
            found.add(path.relative_to(ROOT).as_posix())
    assert found == expected


def test_normative_contract_keeps_exact_authority_ceiling_and_blockers():
    source = (
        ROOT / "docs/architecture/worker-activation-runtime-plan-review-v1.md"
    ).read_text()
    prior = (
        ROOT / "docs/architecture/worker-activation-runtime-plan-v1.md"
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
    inventory = prior.split("The following released authority/material fields", 1)[1]
    inventory = inventory.split("```text\n", 1)[1].split("```", 1)[0]
    assert len(false_fields) == 67
    assert set(inventory.splitlines()) == false_fields
    assert c.ClosedAuthorityV1().model_dump() == c.v055.ClosedAuthorityV1().model_dump()
    blockers = source.split("Success retains exactly these seven ordered blockers:", 1)[
        1
    ]
    blockers = blockers.split("```text\n", 1)[1].split("```", 1)[0]
    assert tuple(blockers.splitlines()) == c.SUCCESS_BLOCKERS == c.v055.SUCCESS_BLOCKERS
    assert (
        "The only\nnewly true marker is `worker_activation_runtime_plan_review_recorded`."
        in source
    )
    assert "worker-activation-runtime-plan-v1.md#authority-ceiling" in source
