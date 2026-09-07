from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def _read(relative: str) -> str:
    return ROOT.joinpath(relative).read_text(encoding="utf-8")


def test_v052_scope_is_frozen_from_released_v051_baseline() -> None:
    roadmap = _read("ROADMAP.md")
    changelog = _read("CHANGELOG.md")
    checklist = _read("docs/RELEASE_CHECKLIST.md")
    contract = _read(
        "docs/architecture/"
        "controlled-worker-queue-claim-lease-acknowledgement-boundary-v1.md"
    )

    assert (
        "Status: **Atlas v0.52 P0-P5 closed controlled worker queue "
        "claim/lease/acknowledgement receipt evidence contract**."
        in contract
    )
    assert (
        "## Completed v0.52 plan - Controlled Worker Queue Claim/Lease/"
        "Acknowledgement Boundary"
        in roadmap
    )
    assert (
        "#### v0.52 P0 - Controlled Worker Queue Claim/Lease/"
        "Acknowledgement Boundary"
        in changelog
    )
    assert (
        "## Atlas v0.52 P0 Controlled Worker Queue Claim/Lease/"
        "Acknowledgement Boundary - selected"
        in checklist
    )

    scope_text = f"{roadmap}\n{changelog}\n{checklist}\n{contract}".lower()
    for phrase in (
        "8d1ece090b14e6fc2d06332b14b03559b252555d",
        "atlas-v0.51.0",
        "one exact active same-owner v0.51",
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
        "controlled_worker_queue_claim_lease_acknowledgement_recorded",
        "inherited inert queue-item lineage",
        "explicitly constructed",
        "default-off",
        "single-subject queue receipt boundary",
        "reservation-before-effect",
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
        assert phrase in scope_text


def test_v052_p0_documents_only_queue_receipt_and_blocks_later_authority() -> None:
    contract = _read(
        "docs/architecture/"
        "controlled-worker-queue-claim-lease-acknowledgement-boundary-v1.md"
    )

    assert "P0 is documentation-only and adds no runtime architecture." in contract
    assert "P1 - closed immutable Core contract models" in contract
    assert "P2 - explicitly constructed append-only Core receipt service/store" in (
        contract
    )
    assert "P3 - guarded default-off owner-scoped Core list/create/get API" in (
        contract
    )
    assert "P4 - nested Mission Control read-only presentation only" in contract
    assert "P5 - release isolation and regression closure" in contract

    for forbidden_authority in (
        "does not authorize worker activation runtime",
        "worker store contact",
        "worker runtime contact",
        "worker-start admission",
        "worker start",
        "Agent invocation",
        "execution authorization",
        "execution start",
        "scheduler/workflow execution",
        "process execution",
        "installation",
        "mutation",
        "deployment",
        "rollback",
        "artifact publication",
        "tag push",
        "release publication",
        "effect consumer",
    ):
        assert forbidden_authority in contract

    assert "caller-supplied credentials" in contract
    assert "caller-supplied queue selectors" in contract
    assert "claim tokens" in contract
    assert "lease tokens" in contract
    assert "acknowledgement handles" in contract
    assert "autonomous queue polling" in contract
    assert "work discovery" in contract
