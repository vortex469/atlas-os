from __future__ import annotations

import ast
import socket
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from app.execution_candidates.installation_plan_projection import (
    InstallationPlanCandidateProjection,
    InstallationPlanCandidateReason,
    InstallationPlanStatus,
    _projection_reasons,
    project_installation_plan_to_candidate,
)
from app.installation_plan.assembly import default_installation_plan_dependency

STATUSES = (
    "conflicted",
    "missing_deployment_artifact",
    "incompatible",
    "stale_evidence",
    "insufficient_information",
    "plan_ready_for_review",
)
GOLDEN = "34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a"


def _home_assistant_plan():
    dependency = default_installation_plan_dependency(
        repository_root=Path("/opt/atlas"),
        clock=lambda: datetime(2026, 8, 25, tzinfo=UTC),
    )
    return dependency.assemble("home-assistant")


@pytest.mark.parametrize("status", STATUSES)
def test_all_statuses_fail_closed_before_candidate_creation(status: str) -> None:
    reasons = _projection_reasons(cast(InstallationPlanStatus, status))
    assert InstallationPlanCandidateReason.APPROVED_TARGET_CONTRACT_UNAVAILABLE in reasons
    assert InstallationPlanCandidateReason.AGENT_INSTALLATION_INTENT_UNSUPPORTED in reasons
    assert (InstallationPlanCandidateReason.INSTALLATION_PLAN_BLOCKED in reasons) == (
        status != "plan_ready_for_review"
    )


def test_home_assistant_exact_plan_is_preserved_and_non_executable() -> None:
    plan = _home_assistant_plan()
    projection = project_installation_plan_to_candidate(plan)

    assert plan.fingerprint.value == GOLDEN
    assert plan.status == "missing_deployment_artifact"
    assert projection.installation_plan is plan
    assert projection.installation_plan_fingerprint == GOLDEN
    assert projection.item_id == "home-assistant"
    assert projection.catalog_entry_id == "d5-home-assistant"
    assert projection.installation_plan_status == "missing_deployment_artifact"
    assert projection.candidate is None
    assert projection.candidate_created is False
    assert projection.planning_allowed is False
    assert InstallationPlanCandidateReason.INSTALLATION_PLAN_BLOCKED in projection.reason_codes


def test_blockers_confirmations_risks_and_provenance_remain_informational() -> None:
    plan = _home_assistant_plan()
    projection = project_installation_plan_to_candidate(plan)

    assert projection.installation_plan.blockers == plan.blockers
    assert projection.installation_plan.missing_facts == plan.missing_facts
    assert projection.installation_plan.required_operator_confirmations == (
        plan.required_operator_confirmations
    )
    assert projection.installation_plan.risks == plan.risks
    assert projection.installation_plan.assumptions == plan.assumptions
    assert projection.installation_plan.prerequisites == plan.prerequisites
    assert projection.installation_plan.compatibility == plan.compatibility
    assert projection.installation_plan.deployment_artifact == plan.deployment_artifact
    assert projection.installation_plan.image == plan.image
    assert projection.installation_plan.accepted_evidence == plan.accepted_evidence
    assert projection.installation_plan.provenance == plan.provenance
    assert projection.candidate is None


def test_duplicate_projection_is_deterministic_and_ephemeral() -> None:
    plan = _home_assistant_plan()
    first = project_installation_plan_to_candidate(plan)
    second = project_installation_plan_to_candidate(plan)

    assert first == second
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert not hasattr(first, "idempotency_key")
    assert not hasattr(first, "workflow_id")
    assert not hasattr(first, "approval_id")


def test_conflicting_fingerprint_linkage_fails_closed() -> None:
    projection = project_installation_plan_to_candidate(_home_assistant_plan())
    with pytest.raises(ValidationError, match="fingerprint linkage must be exact"):
        InstallationPlanCandidateProjection(
            **{
                **projection.model_dump(mode="python"),
                "installation_plan_fingerprint": "0" * 64,
            }
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("item_id", "different-item", "item linkage must be exact"),
        ("catalog_entry_id", "different-entry", "catalog linkage must be exact"),
        ("installation_plan_status", "incompatible", "status linkage must be exact"),
    ],
)
def test_conflicting_plan_linkage_fails_closed(
    field: str,
    value: str,
    message: str,
) -> None:
    projection = project_installation_plan_to_candidate(_home_assistant_plan())
    with pytest.raises(ValidationError, match=message):
        InstallationPlanCandidateProjection(
            **{
                **projection.model_dump(mode="python"),
                field: value,
            }
        )


def test_projection_contract_cannot_be_promoted_to_authority() -> None:
    projection = project_installation_plan_to_candidate(_home_assistant_plan())
    payload = projection.model_dump(mode="python")

    for field, value in (
        ("candidate_created", True),
        ("planning_allowed", True),
    ):
        with pytest.raises(ValidationError):
            InstallationPlanCandidateProjection(**{**payload, field: value})

    with pytest.raises(ValidationError):
        InstallationPlanCandidateProjection(
            **{**payload, "candidate": object()}
        )


def test_projection_imports_only_contracts_not_authority_services() -> None:
    source = Path(__file__).with_name("installation_plan_projection.py").read_text()
    tree = ast.parse(source)
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert imported == {
        "__future__",
        "enum",
        "typing",
        "pydantic",
        "app.execution_candidates.models",
        "app.installation_plan.contract",
    }


def test_projection_has_no_worker_dispatch_network_subprocess_or_mutation_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("authority side effect attempted")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, forbidden)

    projection = project_installation_plan_to_candidate(_home_assistant_plan())
    assert projection.candidate is None
    assert projection.planning_allowed is False
