"""Retained v0.63 closure must not reserve successor authority or consumers."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.worker_activation_runtime_interface_prerequisite import contract as c
from app.worker_activation_runtime_interface_prerequisite.test_release_closure import (
    MARKERS,
    ROOT,
    v064_allowed_markers,
)
from app.worker_activation_runtime_interface_prerequisite.test_v059_release_closure import (
    golden,  # noqa: F401
)


def test_v063_no_successor_or_operational_consumer():
    forbidden = tuple(
        marker
        for snake, kebab, camel, upper in (
            ("inventory", "inventory", "Inventory", "INVENTORY"),
            ("definition", "definition", "Definition", "DEFINITION"),
            (
                "definition_review",
                "definition-review",
                "DefinitionReview",
                "DEFINITION_REVIEW",
            ),
        )
        for marker in (
            f"worker_activation_runtime_{snake}",
            f"worker-activation-runtime-{kebab}",
            f"workerActivationRuntime{camel}",
            f"WorkerActivationRuntime{camel}",
            f"WORKER_ACTIVATION_RUNTIME_{upper}",
        )
    )
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
        directory = ROOT / area
        assert directory.is_dir()
        paths = list(directory.rglob("*"))
        if area == "deploy":
            paths.extend((*ROOT.glob("compose*.yaml"), ROOT / ".env.example"))
        # Test sources and golden fixtures are evidence, not production consumers.
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
            rejected = forbidden
            if area not in {"services/atlas-core/app", "services/mission-control/src"}:
                rejected += MARKERS
            source = path.read_text()
            for marker in rejected:
                if marker in v064_allowed_markers(path, rejected):
                    continue
                assert marker not in source, (path.relative_to(ROOT), marker)


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
        "worker_activation_runtime_inventory_admitted",
        "worker_activation_runtime_definition_recorded",
        "worker_activation_runtime_definition_review_recorded",
    ],
)
@pytest.mark.parametrize("value", [True, False])
def test_v063_shared_envelopes_reject_successor_authority(
    request, section, marker, value
):
    raw = deepcopy(request.getfixturevalue("golden"))
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
