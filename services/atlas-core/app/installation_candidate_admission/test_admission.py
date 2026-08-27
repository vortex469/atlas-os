from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_candidate_admission.contract import (
    InstallationCandidateAdmissionV1,
)
from app.installation_candidate_admission.evaluation import (
    evaluate_installation_candidate_admission,
)
from app.installation_capability.test_assessment import (
    NOW,
    assess,
    destination,
    plan,
    provider_facts,
    selection,
)


def admit(**updates: object):
    value = plan("Requires at least 2 CPU cores.")
    inputs = {
        "plan": value,
        "selection": selection(),
        "current_destination": destination(),
        "capability_assessment": assess(value),
        "evaluated_at": NOW,
    }
    inputs.update(updates)
    return evaluate_installation_candidate_admission(**inputs)


def test_closed_schema_and_fixed_false_authority() -> None:
    result = admit()
    assert result.status == "admitted_but_non_executable"
    assert result.reason_codes == ()
    assert result.candidate_record is not None
    assert not any((
        result.approved, result.executable, result.deployable,
        result.dispatchable, result.agent_execution_supported,
        result.candidate_creation_allowed,
    ))
    with pytest.raises(ValidationError):
        InstallationCandidateAdmissionV1.model_validate(
            {**result.model_dump(), "command": "install"}
        )


def test_status_precedence_and_reason_ordering() -> None:
    stale = selection(
        status="stale", terminated_at="2026-08-27T11:30:00Z",
        expires_at="2026-08-28T11:00:00Z",
    )
    current = destination(destination_fingerprint="e" * 64)
    result = admit(selection=stale, current_destination=current)
    assert result.status == "not_admitted"
    assert result.candidate_record is None
    assert result.reason_codes == (
        "destination_selection_not_active", "destination_replaced_or_moved"
    )
    blocked_plan = plan(ready=False)
    result = admit(
        plan=blocked_plan, selection=stale, current_destination=current,
        capability_assessment=assess(blocked_plan),
    )
    assert result.reason_codes == ("installation_plan_not_review_ready",)


def test_fingerprint_stability_and_sensitivity() -> None:
    first = admit()
    assert first.admission_fingerprint == admit().admission_fingerprint
    changed_plan = plan("Requires at least 3 CPU cores.")
    changed = admit(
        plan=changed_plan, capability_assessment=assess(changed_plan)
    )
    assert first.admission_fingerprint != changed.admission_fingerprint
    assert first.candidate_record.record_fingerprint != (
        changed.candidate_record.record_fingerprint
    )


def test_stale_mismatched_and_non_authorizing_capability_fail_closed() -> None:
    value = plan("Requires at least 2 CPU cores.")
    stale = admit(
        plan=value,
        capability_assessment=assess(
            value,
            provider_facts=provider_facts(fresh_until="2026-08-27T12:05:00Z"),
        ),
        evaluated_at=datetime(2026, 8, 27, 12, 5, tzinfo=UTC),
    )
    assert stale.reason_codes == ("capability_assessment_stale",)
    other = selection(selection_id="00000000-0000-4000-8000-000000000002")
    mismatched = admit(selection=other)
    assert mismatched.reason_codes == ("capability_assessment_mismatched",)
    blocked = plan("Requires at least 9 CPU cores.")
    result = admit(plan=blocked, capability_assessment=assess(blocked))
    assert result.reason_codes == ("capability_assessment_not_admissible",)


def test_home_assistant_golden_is_not_admitted() -> None:
    home = plan(ready=False)
    result = admit(plan=home, capability_assessment=assess(home))
    assert home.fingerprint.value == (
        "34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a"
    )
    assert home.deployment_artifact.state == "missing"
    assert result.status == "not_admitted"
    assert result.reason_codes == ("installation_plan_not_review_ready",)
    assert result.candidate_record is None


def test_missing_input_is_no_result_and_invalid_input_fails_closed() -> None:
    assert admit(current_destination=None) is None
    assert admit(evaluated_at=NOW.replace(microsecond=1)).reason_codes == (
        "input_invalid",
    )


def test_no_forbidden_authority_imports_or_calls() -> None:
    tree = ast.parse(Path(__file__).with_name("evaluation.py").read_text())
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    forbidden = {
        "execution_candidates", "approval", "workflow", "dispatch", "agent",
        "worker", "provider_intents", "repository", "requests", "httpx",
        "socket", "subprocess", "sqlite3", "open", "write_text", "write_bytes",
    }
    assert not imports & forbidden
    assert not calls & forbidden
