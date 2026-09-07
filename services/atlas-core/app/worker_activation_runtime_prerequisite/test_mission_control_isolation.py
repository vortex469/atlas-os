"""P4 has only a nested evidence reader and no downstream runtime consumer."""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_p4_has_zero_agent_and_execution_worker_consumers() -> None:
    for directory in (
        "services/atlas-agent/app",
        "services/atlas-execution-worker/atlas_execution_worker",
    ):
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".json", ".yaml", ".yml"}:
                source = path.read_text()
                for marker in (
                    "worker_activation_runtime_prerequisite",
                    "worker-activation-runtime-prerequisite",
                    "WorkerActivationRuntimePrerequisite",
                ):
                    assert marker not in source, path.relative_to(ROOT)


def test_p4_false_authority_fields_match_core_contracts_exactly() -> None:
    ui = ROOT / "services/mission-control/src/types"
    for core_module, ui_module in (
        ("controlled_worker_queue_claim_lease_acknowledgement", "controlledWorkerQueueReceipt"),
        ("worker_activation_runtime_prerequisite", "workerActivationRuntimePrerequisite"),
    ):
        contract = ast.parse(
            (ROOT / f"services/atlas-core/app/{core_module}/contract.py").read_text()
        )
        authority = next(
            node for node in contract.body
            if isinstance(node, ast.ClassDef) and node.name == "ClosedAuthorityV1"
        )
        fields = {
            node.target.id for node in authority.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and isinstance(node.value, ast.Constant)
            and node.value.value is False
        }
        source = (ui / f"{ui_module}.ts").read_text()
        array = source.split("as const;", 1)[0]
        assert set(re.findall(r'"([a-z_]+)"', array)) == fields
