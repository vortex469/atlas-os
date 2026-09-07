"""The v0.54 Mission Control consumer is nested evidence display only."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_no_agent_or_execution_worker_consumers() -> None:
    for directory in (
        "services/atlas-agent/app",
        "services/atlas-execution-worker/atlas_execution_worker",
    ):
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".json", ".yaml", ".yml"}:
                source = path.read_text()
                for marker in (
                    "worker_activation_runtime_admission",
                    "worker-activation-runtime-admission",
                    "WorkerActivationRuntimeAdmission",
                ):
                    assert marker not in source, path.relative_to(ROOT)


def test_ui_reuses_the_exact_predecessor_false_authority_ceiling() -> None:
    from app.worker_activation_runtime_admission.contract import ClosedAuthorityV1
    from app.worker_activation_runtime_prerequisite.contract import (
        ClosedAuthorityV1 as PrerequisiteAuthority,
    )

    assert ClosedAuthorityV1().model_dump() == PrerequisiteAuthority().model_dump()
    ui = ROOT / "services/mission-control/src"
    source = (ui / "api/workerActivationRuntimeAdmission.ts").read_text()
    assert 'import { CLOSED_RUNTIME_AUTHORITY } from "../types/workerActivationRuntimePrerequisite"' in source
    assert "for (const key of CLOSED_RUNTIME_AUTHORITY) check(raw[key] === false)" in source
    types = (ui / "types/workerActivationRuntimeAdmission.ts").read_text()
    assert "extends WorkerActivationRuntimePrerequisite" in types
