from __future__ import annotations

import ast
import asyncio
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pytest

from app.installation_candidate_admission.assembly import (
    InstallationCandidateAdmissionInputMissing,
    InstallationCandidateAdmissionInputUnavailable,
    InstallationCandidateAdmissionReadDependency,
)
from app.installation_capability.test_assessment import (
    NOW,
    assess,
    destination,
    plan,
    selection,
)
from app.installation_plan.assembly import InstallationPlanItemNotFound
from app.installation_targets.store import SelectionNotFoundError, StoredSelection


@dataclass
class Plans:
    value: object
    error: Exception | None = None
    calls: int = 0

    def assemble(self, item_id: str):
        self.calls += 1
        if self.error:
            raise self.error
        assert item_id == self.value.application.item_id
        return self.value


@dataclass
class Selections:
    value: object
    error: Exception | None = None
    calls: int = 0

    def get(self, selection_id: str, principal_id: str):
        self.calls += 1
        if self.error:
            raise self.error
        assert selection_id == self.value.selection_id
        assert principal_id == "operator-a"
        return StoredSelection(record=self.value, record_version=1)


@dataclass
class Capabilities:
    value: object
    error: Exception | None = None
    calls: int = 0

    async def assemble(self, *, plan, selection):
        self.calls += 1
        if self.error:
            raise self.error
        return self.value if self.value is not None else assess(plan, selection=selection)


def dependency(*, plan_value=None, selection_value=None, assessment=None, now=NOW):
    plan_value = plan_value or plan("Requires at least 2 CPU cores.")
    selection_value = selection_value or selection()
    parts = (
        Plans(plan_value),
        Selections(selection_value),
        Capabilities(assessment),
    )
    return InstallationCandidateAdmissionReadDependency(
        plans=parts[0], selections=parts[1], capabilities=parts[2],
        clock=lambda: now,
    ), parts


def assemble(read, *, item_id="home-assistant", principal_id="operator-a"):
    return asyncio.run(read.assemble(
        item_id=item_id,
        selection_id="00000000-0000-4000-8000-000000000001",
        principal_id=principal_id,
    ))


def test_assembles_satisfied_non_authorizing_result_with_fixed_false_authority():
    read, parts = dependency()
    result = assemble(read)
    assert result.status == "admitted_but_non_executable"
    assert result.reason_codes == ()
    assert result.candidate_record is not None
    assert not any((
        result.approved, result.executable, result.deployable,
        result.dispatchable, result.agent_execution_supported,
        result.candidate_creation_allowed, result.candidate_record.approved,
        result.candidate_record.executable,
        result.candidate_record.agent_execution_supported,
    ))
    assert tuple(part.calls for part in parts) == (1, 1, 1)


def test_home_assistant_remains_not_admitted():
    home = plan(ready=False)
    read, _ = dependency(plan_value=home, assessment=assess(home))
    result = assemble(read)
    assert result.status == "not_admitted"
    assert result.reason_codes == ("installation_plan_not_review_ready",)
    assert result.candidate_record is None


@pytest.mark.parametrize(
    ("selected", "now", "reason"),
    [
        (selection(status="cancelled", terminated_at="2026-08-27T11:30:00Z"), NOW,
         "destination_selection_not_active"),
        (selection(), NOW + timedelta(hours=24),
         "destination_selection_expired"),
    ],
)
def test_inactive_and_expired_selection(selected, now, reason):
    value = plan("Requires at least 2 CPU cores.")
    read, _ = dependency(
        plan_value=value, selection_value=selected,
        assessment=assess(value, selection=selected), now=now,
    )
    assert reason in assemble(read).reason_codes


def test_current_identity_mismatch_is_not_admitted():
    value = plan("Requires at least 2 CPU cores.")
    current = destination(destination_fingerprint="e" * 64)
    assessment = assess(value, current_destination=current)
    read, _ = dependency(plan_value=value, assessment=assessment)
    assert assemble(read).reason_codes == ("destination_replaced_or_moved",)


def test_capability_stale_mismatched_and_not_admissible():
    value = plan("Requires at least 2 CPU cores.")
    old = assess(value)
    read, _ = dependency(
        plan_value=value, assessment=old, now=NOW + timedelta(minutes=5)
    )
    assert assemble(read).reason_codes == ("capability_assessment_stale",)

    other = selection(selection_id="00000000-0000-4000-8000-000000000002")
    read, _ = dependency(plan_value=value, assessment=assess(value, selection=other))
    assert assemble(read).reason_codes == ("capability_assessment_mismatched",)

    blocked = plan("Requires at least 9 CPU cores.")
    read, _ = dependency(plan_value=blocked, assessment=assess(blocked))
    assert assemble(read).reason_codes == ("capability_assessment_not_admissible",)


def test_missing_and_unavailable_errors_are_sanitized():
    read, parts = dependency()
    parts[0].error = InstallationPlanItemNotFound("secret path")
    with pytest.raises(InstallationCandidateAdmissionInputMissing) as caught:
        assemble(read)
    assert str(caught.value) == "installation candidate admission input was not found"
    assert caught.value.__cause__ is None

    read, parts = dependency()
    parts[1].error = SelectionNotFoundError("secret operator")
    with pytest.raises(InstallationCandidateAdmissionInputMissing):
        assemble(read)

    read, parts = dependency()
    parts[2].error = RuntimeError("provider address and token")
    with pytest.raises(InstallationCandidateAdmissionInputUnavailable) as caught:
        assemble(read)
    assert str(caught.value) == "installation candidate admission input is unavailable"
    assert caught.value.__cause__ is None


def test_ownership_mismatch_is_missing_and_assembly_has_no_mutation_calls():
    selected = selection().model_copy(update={"selected_by": "operator-b"})
    read, _ = dependency(selection_value=selected)
    with pytest.raises(InstallationCandidateAdmissionInputMissing):
        assemble(read)

    tree = ast.parse(Path(__file__).with_name("assembly.py").read_text())
    calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    assert not calls & {
        "create", "transition", "cancel", "write", "commit", "execute",
        "add", "delete", "update", "put", "post", "patch",
    }


def test_no_forbidden_authority_imports_or_calls():
    paths = (
        Path(__file__).with_name("assembly.py"),
        Path(__file__).parents[1] / "installation_capability" / "assembly.py",
    )
    forbidden = {
        "execution_candidates", "approval", "workflow", "dispatch", "agent",
        "worker", "provider_intents", "repository", "requests", "httpx",
        "socket", "subprocess", "sqlite3", "open", "write_text", "write_bytes",
    }
    for path in paths:
        tree = ast.parse(path.read_text())
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
        assert not imports & forbidden
        assert not calls & forbidden
