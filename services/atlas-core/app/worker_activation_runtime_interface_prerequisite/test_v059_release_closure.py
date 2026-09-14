"""Retained v0.59 closure: synchronization cannot create successor authority."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.worker_activation_runtime_interface_prerequisite import contract as c
from app.worker_activation_runtime_interface_prerequisite.test_release_closure import (
    MARKERS,
)

ROOT = Path(__file__).resolve().parents[4]


def test_v059_normative_inventory_matches_retained_core():
    source = (
        ROOT / "docs/architecture/v0.59-runtime-interface-boundary.md"
    ).read_text()
    table = source.split("| `blocker` | `owner` | `required_proof` |", 1)[1].split(
        "\n\n", 1
    )[0]
    assert [line for line in table.splitlines() if line.startswith("| `")] == [
        f"| `{entry.blocker}` | `{entry.owner}` | `{entry.required_proof}` |"
        for entry in c.SUCCESS_INVENTORY
    ]
    assert "No proof is discharged." in source
    assert "Home Assistant remains blocked without installation artifacts." in source
    assert "Definition-review P1-P5" in source
    assert "are deferred" in source


def test_v059_no_successor_or_workflow_consumer():
    # Scan all production text extensions used by the historical closure scan,
    # plus workflows. No successor directory or historical exception is allowed.
    markers = tuple(
        marker
        for snake, kebab, camel, upper in (
            ("admission", "admission", "Admission", "ADMISSION"),
            (
                "definition_review",
                "definition-review",
                "DefinitionReview",
                "DEFINITION_REVIEW",
            ),
        )
        for marker in (
            f"worker_activation_runtime_interface_{snake}",
            f"worker-activation-runtime-interface-{kebab}",
            f"workerActivationRuntimeInterface{camel}",
            f"WorkerActivationRuntimeInterface{camel}",
            f"WORKER_ACTIVATION_RUNTIME_INTERFACE_{upper}",
        )
    ) + ("worker_activation_runtime_interface_admitted",)
    for area in (
        "services/atlas-core/app",
        "services/atlas-agent/app",
        "services/atlas-execution-worker/atlas_execution_worker",
        "services/mission-control/src",
        "config",
        "deploy",
        "scripts",
        ".github/workflows",
    ):
        assert (ROOT / area).is_dir()
        paths = list((ROOT / area).rglob("*"))
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
                or "test" in path.parts
            ):
                continue
            source = path.read_text()
            forbidden = markers + MARKERS if area == ".github/workflows" else markers
            for marker in forbidden:
                assert marker not in source, (path.relative_to(ROOT), marker)


@pytest.fixture(scope="module")
def golden():
    raw = json.loads(
        (
            ROOT
            / "services/mission-control/src/test/workerActivationRuntimeInterfacePrerequisite.core.json"
        ).read_text()
    )
    raw["collection"]["items"] = [deepcopy(raw["result"]["record"])]
    # Both full envelopes must be accepted before their mutations prove refusal.
    c.WorkerActivationRuntimeInterfacePrerequisiteResultV1.model_validate(raw["result"])
    c.WorkerActivationRuntimeInterfacePrerequisiteCollectionV1.model_validate(
        raw["collection"]
    )
    return raw


@pytest.mark.parametrize(
    "section",
    [
        "collection",
        "listed_record",
        "result",
        "record",
        "status",
        "worker_activation_runtime_plan_review",
        "worker_activation_runtime_plan_review_status",
    ],
)
@pytest.mark.parametrize(
    "marker",
    [
        "worker_activation_runtime_interface_admitted",
        "worker_activation_runtime_interface_definition_review_recorded",
    ],
)
@pytest.mark.parametrize("value", [True, False])
def test_v059_shared_ui_golden_rejects_successors_recursively(
    golden, section, marker, value
):
    raw = deepcopy(golden)
    if section in {"collection", "listed_record"}:
        envelope = raw["collection"]
        target = envelope if section == "collection" else envelope["items"][0]
        model = c.WorkerActivationRuntimeInterfacePrerequisiteCollectionV1
    else:
        envelope = raw["result"]
        if section.startswith("worker_activation_runtime_plan_review"):
            target = envelope["record"][section]
        else:
            target = envelope if section == "result" else envelope[section]
        model = c.WorkerActivationRuntimeInterfacePrerequisiteResultV1
    target[marker] = value
    with pytest.raises(ValidationError) as rejected:
        model.model_validate(envelope)
    assert any(
        error["type"] == "extra_forbidden" and error["loc"][-1] == marker
        for error in rejected.value.errors()
    )
