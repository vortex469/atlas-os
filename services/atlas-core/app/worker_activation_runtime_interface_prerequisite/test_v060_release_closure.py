"""Retained v0.60 closure must not reserve any runtime-definition consumer."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.worker_activation_runtime_interface_prerequisite import contract as c
from app.worker_activation_runtime_interface_prerequisite.test_release_closure import (
    MARKERS,
    ROOT,
)
from app.worker_activation_runtime_interface_prerequisite.test_v059_release_closure import (
    golden,  # noqa: F401
)


def test_v060_no_definition_or_operational_consumer():
    definition_markers = (
        "worker_activation_runtime_definition",
        "worker-activation-runtime-definition",
        "workerActivationRuntimeDefinition",
        "WorkerActivationRuntimeDefinition",
        "WORKER_ACTIVATION_RUNTIME_DEFINITION",
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
        # No successor package, version, or production path gets an exception.
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
            forbidden = definition_markers
            if area not in {"services/atlas-core/app", "services/mission-control/src"}:
                forbidden += MARKERS
            source = path.read_text()
            for marker in forbidden:
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
@pytest.mark.parametrize("value", [True, False])
def test_v060_shared_envelopes_reject_definition_authority(request, section, value):
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
    marker = "worker_activation_runtime_definition_recorded"
    target[marker] = value
    with pytest.raises(ValidationError) as rejected:
        model.model_validate(envelope)
    assert any(
        error["type"] == "extra_forbidden" and error["loc"][-1] == marker
        for error in rejected.value.errors()
    )
