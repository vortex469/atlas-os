"""v0.63 retains the closed v0.57 pair; no successor authority is added."""

import pytest
from pydantic import ValidationError

from app.worker_activation_runtime_interface_prerequisite import contract as c
from app.worker_activation_runtime_interface_prerequisite.test_v059_release_closure import (
    ROOT,
    golden,  # noqa: F401
)


@pytest.fixture(scope="module", params=["record", "status"])
def retained_pair_member(request):
    evidence = request.getfixturevalue("golden")
    model, field, sign = {
        "record": (
            c.WorkerActivationRuntimeInterfacePrerequisiteV1,
            "runtime_interface_prerequisite_record_fingerprint",
            c.runtime_interface_prerequisite_record_fingerprint,
        ),
        "status": (
            c.WorkerActivationRuntimeInterfacePrerequisiteStatusV1,
            "status_fingerprint",
            c.status_fingerprint,
        ),
    }[request.param]
    member = model.model_validate(evidence["result"][request.param])
    assert member.inventory == c.SUCCESS_INVENTORY
    assert member.worker_activation_runtime_interface_prerequisite_recorded is True
    return member, field, sign


def test_v063_retains_the_frozen_pair_and_bounds():
    source = " ".join(
        (ROOT / "docs/architecture/v0.63-authority-boundary.md").read_text().split()
    )
    assert "Successor P1-P5 remain deferred." in source
    assert "The accepted pair remains" in source
    assert "no successor pair, reader, route, consumer or authority field" in source
    for model in (
        c.WorkerActivationRuntimeInterfacePrerequisiteV1,
        c.WorkerActivationRuntimeInterfacePrerequisiteStatusV1,
    ):
        assert f"{model.model_fields['schema'].default}" in source
    assert c.MAX_MODEL_BYTES == 192 * 1024
    assert c.MAX_FRESHNESS_SECONDS == 30


@pytest.mark.parametrize(
    "marker",
    [
        "worker_activation_runtime_inventory_admitted",
        "worker_activation_runtime_definition_recorded",
        "worker_activation_runtime_definition_review_recorded",
    ],
)
@pytest.mark.parametrize("value", [False, True])
def test_v063_deferred_markers_are_rejected_even_when_rehashed(
    retained_pair_member, marker, value
):
    member, field, sign = retained_pair_member
    before = member.model_dump(mode="python")
    raw = member.model_dump(mode="python")
    raw[marker] = value
    raw[field] = sign(raw)
    for forged in (raw, member.model_copy(update=raw)):
        with pytest.raises(ValidationError) as failure:
            type(member).model_validate(forged)
        assert any(
            error["type"] == "extra_forbidden" and error["loc"] == (marker,)
            for error in failure.value.errors()
        )
    assert member.model_dump(mode="python") == before


def test_v063_cannot_relabel_the_retained_schema(retained_pair_member):
    member, field, sign = retained_pair_member
    raw = member.model_dump(mode="python")
    raw["schema"] = raw["schema"].removesuffix("-v1") + "-v063"
    raw[field] = sign(raw)
    with pytest.raises(ValidationError, match="literal type or value mismatch"):
        type(member).model_validate(raw)


def test_v063_retained_evidence_is_deeply_immutable(retained_pair_member):
    member, field, _ = retained_pair_member
    with pytest.raises(ValidationError, match="frozen"):
        member.inventory = ()
    with pytest.raises(ValidationError, match="frozen"):
        member.inventory[0].owner = "runtime"
    with pytest.raises(ValidationError, match="frozen"):
        getattr(member, field).value = "0" * 64
