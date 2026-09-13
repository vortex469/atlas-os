"""v0.58 retains v0.57 evidence; synchronization cannot authorize a successor."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.worker_activation_runtime_interface_prerequisite import contract as c
from app.worker_activation_runtime_interface_prerequisite import store

ROOT = Path(__file__).resolve().parents[4]


def test_no_deferred_admission_production_surface():
    markers = (
        "worker_activation_runtime_interface_admission",
        "worker_activation_runtime_interface_admitted",
        "worker-activation-runtime-interface-admission",
        "workerActivationRuntimeInterfaceAdmission",
        "WorkerActivationRuntimeInterfaceAdmission",
        "WORKER_ACTIVATION_RUNTIME_INTERFACE_ADMISSION",
    )
    # Scan complete production trees, including Agent/worker and deployment.
    # No path is reserved for a hypothetical later implementation.
    paths = []
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
        paths.extend((ROOT / area).rglob("*"))
    paths.extend(ROOT.glob("compose*.yaml"))
    paths.append(ROOT / ".env.example")
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
        }:
            continue
        if (
            path.name.startswith("test_")
            or ".test." in path.name
            or "test" in path.parts
        ):
            continue
        source = path.read_text()
        for marker in markers:
            assert marker not in source, (path.relative_to(ROOT), marker)


def test_synchronized_contract_preserves_exact_inventory_and_bounds():
    source = (
        ROOT / "docs/architecture/v0.58-runtime-interface-admission-provisional.md"
    ).read_text()
    table = source.split("| `blocker` | `owner` | `required_proof` |", 1)[1].split(
        "\n\n", 1
    )[0]
    assert [line for line in table.splitlines() if line.startswith("| `")] == [
        f"| `{entry.blocker}` | `{entry.owner}` | `{entry.required_proof}` |"
        for entry in c.SUCCESS_INVENTORY
    ]
    assert "defer" in source and "A2" in source
    assert "No proof is discharged." in source
    assert "Home Assistant remains blocked without installation artifacts." in source
    assert c.MAX_MODEL_BYTES == 192 * 1024
    assert c.MAX_CREATE_BYTES == 16 * 1024
    assert c.MAX_CREATE_NESTING == 16
    assert c.MAX_FRESHNESS_SECONDS == 30
    assert store.MAX_RECORDS_PER_OPERATOR == 16
    assert store.MAX_TOTAL_RECORDS == 256
    assert store.MAX_DATABASE_BYTES == 256 * 1024 * 1024


@pytest.fixture(scope="module")
def golden():
    raw = json.loads(
        (
            ROOT
            / "services/mission-control/src/test/workerActivationRuntimeInterfacePrerequisite.core.json"
        ).read_text()
    )
    raw["collection"]["items"] = [deepcopy(raw["result"]["record"])]
    # Positive controls prevent a stale/broken fixture from proving rejection.
    c.WorkerActivationRuntimeInterfacePrerequisiteResultV1.model_validate(raw["result"])
    c.WorkerActivationRuntimeInterfacePrerequisiteCollectionV1.model_validate(
        raw["collection"]
    )
    return raw


@pytest.mark.parametrize(
    "section", ["collection", "listed_record", "result", "record", "status"]
)
@pytest.mark.parametrize("value", [True, False])
def test_core_and_ui_golden_cannot_acquire_successor_authority(golden, section, value):
    raw = deepcopy(golden)
    if section in {"collection", "listed_record"}:
        envelope = raw["collection"]
        target = envelope if section == "collection" else envelope["items"][0]
        model = c.WorkerActivationRuntimeInterfacePrerequisiteCollectionV1
    else:
        envelope = raw["result"]
        target = envelope if section == "result" else envelope[section]
        model = c.WorkerActivationRuntimeInterfacePrerequisiteResultV1
    target["worker_activation_runtime_interface_admitted"] = value
    with pytest.raises(ValidationError) as rejected:
        model.model_validate(envelope)
    assert any(
        error["type"] == "extra_forbidden"
        and error["loc"][-1] == "worker_activation_runtime_interface_admitted"
        for error in rejected.value.errors()
    )
