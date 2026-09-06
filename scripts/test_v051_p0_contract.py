from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return ROOT.joinpath(relative).read_text(encoding="utf-8")


def test_v051_p0_contract_freezes_narrow_admission_boundary() -> None:
    changelog = _read("CHANGELOG.md")
    roadmap = _read("ROADMAP.md")
    checklist = _read("docs/RELEASE_CHECKLIST.md")
    contract = _read(
        "docs/architecture/"
        "controlled-worker-queue-claim-lease-acknowledgement-admission-v1.md"
    )

    assert (
        "Status: **Atlas v0.51 P0 frozen controlled worker queue claim/lease/"
        "acknowledgement admission contract**."
        in contract
    )
    assert (
        "#### v0.51 P0 - Controlled Worker Queue Claim/Lease/"
        "Acknowledgement Admission"
        in changelog
    )
    assert (
        "## Selected v0.51 P0 plan - Controlled Worker Queue Claim/Lease/"
        "Acknowledgement Admission"
        in roadmap
    )
    assert (
        "## Atlas v0.51 P0 Controlled Worker Queue Claim/Lease/"
        "Acknowledgement Admission - selected"
        in checklist
    )

    closure_text = f"{changelog}\n{roadmap}\n{checklist}\n{contract}".lower()
    for phrase in (
        "one exact active same-owner v0.50",
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
        "v0.50_prerequisite_frozen",
        "queue_adapter_not_defined",
        "queue_claim_not_defined",
        "queue_lease_not_defined",
        "queue_ack_not_defined",
        "worker_activation_runtime_not_defined",
        "store_contact_not_defined",
        "runtime_contact_not_defined",
        "worker_start_admission_not_defined",
        "worker_start_not_defined",
        "agent_invocation_not_defined",
        "execution_start_boundary_not_defined",
        "agent/execution-worker zero-consumer",
        "compose.execution-smoke.override.yaml",
    ):
        assert phrase in closure_text


def test_v051_p0_adds_no_runtime_or_effect_surface() -> None:
    contract = _read(
        "docs/architecture/"
        "controlled-worker-queue-claim-lease-acknowledgement-admission-v1.md"
    ).lower()

    assert not ROOT.joinpath("compose.execution-smoke.override.yaml").exists()
    admission_module = ROOT.joinpath(
        "services/atlas-core/app/"
        "controlled_worker_queue_claim_lease_acknowledgement_admission"
    )
    if admission_module.exists():
        assert sorted(
            path.name
            for path in admission_module.iterdir()
            if path.name != "__pycache__"
        ) == [
            "__init__.py",
            "contract.py",
            "test_contract.py",
        ]
        source = admission_module.joinpath("contract.py").read_text(
            encoding="utf-8"
        ).lower()
        for forbidden in (
            "fastapi",
            "sqlite",
            "subprocess",
            "requests",
            ".enqueue(",
            ".dequeue(",
            ".claim(",
            ".lease(",
            ".acknowledge(",
            ".execute(",
            ".invoke_agent(",
        ):
            assert forbidden not in source

    for phrase in (
        "p0 does not implement runtime authority",
        "v0.51 p0 exposes no api or ui surface",
        "v0.51 p0 makes no agent or execution-worker change",
        "all downstream authority remains fixed false/default off",
        "release closure for v0.51 may add tests and documentation only",
    ):
        assert phrase in contract
