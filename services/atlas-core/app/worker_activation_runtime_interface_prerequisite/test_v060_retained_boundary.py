"""v0.60 retains the integrated v0.59 contract; no definition is authorized."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.worker_activation_runtime_interface_prerequisite import contract as c
from app.worker_activation_runtime_interface_prerequisite.test_v059_release_closure import (
    ROOT,
    golden,  # noqa: F401
)


@pytest.fixture(scope="module")
def retained_facts(golden):
    record = c.WorkerActivationRuntimeInterfacePrerequisiteV1.model_validate(
        golden["result"]["record"]
    )
    facts = c.WorkerActivationRuntimeInterfacePrerequisiteValidationInputV1(
        operator_id=record.operator_id,
        candidate_record_id=record.candidate_record_id,
        subject_previously_reserved=False,
        idempotency_key_previously_reserved=False,
        authority=c.WorkerActivationRuntimeInterfacePrerequisiteAuthorityContextV1(
            authenticated_operator_id=record.operator_id,
            permission=c.PERMISSION,
            permission_verified=True,
            request_received_at=record.recorded_at,
        ),
        create=c.build_create(
            receipt=record.worker_activation_runtime_plan_review,
            receipt_status=record.worker_activation_runtime_plan_review_status,
        ),
        worker_activation_runtime_plan_review=record.worker_activation_runtime_plan_review,
        worker_activation_runtime_plan_review_status=record.worker_activation_runtime_plan_review_status,
    )
    assert c.evaluate_worker_activation_runtime_interface_prerequisite(
        facts
    ).worker_activation_runtime_interface_prerequisite_recorded
    return facts


def test_v060_freeze_retains_exact_inventory_and_schemas():
    source = (ROOT / "docs/architecture/v0.60-runtime-definition-boundary.md").read_text()
    table = source.split("| `blocker` | `owner` | `required_proof` |", 1)[1].split(
        "\n\n", 1
    )[0]
    assert [line for line in table.splitlines() if line.startswith("| `")] == [
        f"| `{entry.blocker}` | `{entry.owner}` | `{entry.required_proof}` |"
        for entry in c.SUCCESS_INVENTORY
    ]
    for model in (
        c.WorkerActivationRuntimeInterfacePrerequisiteV1,
        c.WorkerActivationRuntimeInterfacePrerequisiteStatusV1,
    ):
        assert f'`{model.model_fields["schema"].default}`' in source
    assert "Runtime definition P1-P5 are deferred." in " ".join(source.split())
    assert "No proof is discharged." in source


@pytest.mark.parametrize(
    "section",
    [
        None,
        "authority",
        "create",
        "worker_activation_runtime_plan_review",
        "worker_activation_runtime_plan_review_status",
    ],
)
@pytest.mark.parametrize("value", [False, True])
def test_v060_definition_claims_fail_closed_even_through_model_copy(
    retained_facts, section, value
):
    marker = "worker_activation_runtime_definition_recorded"
    if section is None:
        forged = retained_facts.model_copy(update={marker: value})
    else:
        nested = getattr(retained_facts, section).model_copy(update={marker: value})
        forged = retained_facts.model_copy(update={section: nested})
    before = retained_facts.model_dump(mode="python")
    result = c.evaluate_worker_activation_runtime_interface_prerequisite(forged)
    assert result.eligibility == "blocked"
    assert result.blockers == ("invalid_request",)
    assert result.operator_id == "blocked-evaluation"
    assert result.recognized_v056_review_count == 0
    assert result.inventory == ()
    assert result.earliest_expiry is None
    assert not result.worker_activation_runtime_interface_prerequisite_recorded
    assert result.evaluation_fingerprint == c.evaluation_fingerprint(result)
    assert marker not in result.model_dump_json()
    assert retained_facts.model_dump(mode="python") == before
    with pytest.raises(ValidationError):
        c.build_runtime_interface_prerequisite(
            forged, idempotency_key="v060-unauthorized-definition"
        )


@pytest.mark.parametrize("section", ["record", "status"])
def test_v060_rehashed_successor_schema_cannot_replace_retained_pair(golden, section):
    raw = deepcopy(golden["result"])
    target = raw[section]
    target["schema"] = (
        "worker-activation-runtime-definition-v1"
        if section == "record"
        else "worker-activation-runtime-definition-status-v1"
    )
    field, sign = (
        (
            "runtime_interface_prerequisite_record_fingerprint",
            c.runtime_interface_prerequisite_record_fingerprint,
        )
        if section == "record"
        else ("status_fingerprint", c.status_fingerprint)
    )
    target[field] = sign(target).model_dump(mode="python")
    with pytest.raises(ValidationError, match="literal type or value mismatch"):
        c.WorkerActivationRuntimeInterfacePrerequisiteResultV1.model_validate(raw)
