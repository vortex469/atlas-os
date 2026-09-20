"""v0.64 P5 authority, consumer-isolation, and release-closure locks."""

from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.worker_activation_runtime_definition import contract as c
from app.worker_activation_runtime_definition.test_contract import definition

ROOT = Path(__file__).resolve().parents[4]


def test_no_effect_plane_or_operational_consumers() -> None:
    forbidden = (
        "worker_activation_runtime_activation_authorized",
        "worker-activation-runtime-activation-authorized",
        "workerActivationRuntimeActivationAuthorized",
        "WorkerActivationRuntimeActivationAuthorized",
        "WORKER_ACTIVATION_RUNTIME_ACTIVATION_AUTHORIZED",
        "worker_activation_runtime_worker_started",
        "worker-activation-runtime-worker-started",
        "workerActivationRuntimeWorkerStarted",
        "WorkerActivationRuntimeWorkerStarted",
        "WORKER_ACTIVATION_RUNTIME_WORKER_STARTED",
    )
    for area in (
        "services/atlas-agent/app",
        "services/atlas-execution-worker/atlas_execution_worker",
        "services/mission-control/src",
        "config",
        "deploy",
        "scripts",
        ".github/workflows",
    ):
        directory = ROOT / area
        assert directory.is_dir()
        paths = list(directory.rglob("*"))
        if area == "deploy":
            paths.extend((*ROOT.glob("compose*.yaml"), ROOT / ".env.example"))
        for path in paths:
            if not path.is_file() or path.suffix not in {
                "",
                ".py",
                ".ts",
                ".tsx",
                ".json",
                ".yaml",
                ".yml",
                ".sh",
                ".example",
            }:
                continue
            if (
                path.name.startswith("test_")
                or ".test." in path.name
                or "test" in path.relative_to(ROOT).parts
            ):
                continue
            source = path.read_text()
            for marker in forbidden:
                assert marker not in source, (path.relative_to(ROOT), marker)


@pytest.mark.parametrize(
    "model, marker",
    [
        (
            c.WorkerActivationRuntimeDefinitionV1,
            "worker_activation_runtime_inventory_admitted",
        ),
        (
            c.WorkerActivationRuntimeDefinitionV1,
            "worker_activation_runtime_definition_review_recorded",
        ),
        (
            c.WorkerActivationRuntimeDefinitionEvaluationV1,
            "worker_activation_runtime_activation_authorized",
        ),
    ],
)
@pytest.mark.parametrize("value", [True, False])
def test_shared_envelopes_reject_unselected_authority(model, marker, value) -> None:
    value_to_copy = definition()
    raw = value_to_copy.model_dump(mode="python")
    if model is c.WorkerActivationRuntimeDefinitionEvaluationV1:
        raw = c.evaluate_worker_activation_runtime_definition(
            value_to_copy, evaluated_at="2026-01-01T00:00:00Z"
        ).model_dump(mode="python")
    forged = deepcopy(raw)
    forged[marker] = value
    with pytest.raises(ValidationError):
        model.model_validate(forged)


def test_selected_definition_keeps_reference_only_authority_ceiling() -> None:
    value = definition()
    assert value.lifecycle == "reference-only"
    assert value.evidence_only is True
    assert value.reference_only is True
    assert value.runtime_effect_allowed is False
    assert value.worker_start_allowed is False
    assert value.activation_allowed is False
    evaluation = c.evaluate_worker_activation_runtime_definition(
        value, evaluated_at="2026-01-01T00:00:00Z"
    )
    assert evaluation.eligibility == c.MARKER
    assert "activation_authorized" not in evaluation.model_dump_json()
