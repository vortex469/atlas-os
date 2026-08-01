from __future__ import annotations

import pytest

from app.execution_candidates.classification import (
    NON_EXECUTABLE_RECOMMENDATION_CLASSES,
    classify_recommendation_class,
)
from app.execution_candidates.models import (
    ApprovalLevel,
    ExecutionCategory,
    ExecutionConstraint,
    ExecutionIntent,
    category_for_intent,
)


@pytest.mark.parametrize(
    ("recommendation_class", "category", "intent", "approval"),
    [
        ("install-container", ExecutionCategory.INSTALL, ExecutionIntent.INSTALL_CONTAINER, ApprovalLevel.ELEVATED),
        ("install-provider", ExecutionCategory.INSTALL, ExecutionIntent.INSTALL_PROVIDER, ApprovalLevel.ELEVATED),
        ("configure-service", ExecutionCategory.CONFIGURE, ExecutionIntent.CONFIGURE_SERVICE, ApprovalLevel.STANDARD),
        ("enable-integration", ExecutionCategory.CONFIGURE, ExecutionIntent.ENABLE_INTEGRATION, ApprovalLevel.ELEVATED),
        ("update-compose-stack", ExecutionCategory.UPDATE, ExecutionIntent.UPDATE_COMPOSE_STACK, ApprovalLevel.ELEVATED),
        ("restart-service", ExecutionCategory.RESTART, ExecutionIntent.RESTART_SERVICE, ApprovalLevel.STANDARD),
        ("create-backup", ExecutionCategory.BACKUP, ExecutionIntent.CREATE_BACKUP, ApprovalLevel.STANDARD),
        ("restore-backup", ExecutionCategory.RESTORE, ExecutionIntent.RESTORE_BACKUP, ApprovalLevel.DESTRUCTIVE),
        ("remove-resource", ExecutionCategory.REMOVE, ExecutionIntent.REMOVE_RESOURCE, ApprovalLevel.DESTRUCTIVE),
    ],
)
def test_executable_classes_map_deterministically(
    recommendation_class: str,
    category: ExecutionCategory,
    intent: ExecutionIntent,
    approval: ApprovalLevel,
) -> None:
    classification = classify_recommendation_class(recommendation_class)

    assert classification is not None
    assert classification.execution_category == category
    assert classification.execution_intent == intent
    assert classification.required_approval_level == approval


def test_each_intent_maps_to_exactly_one_category() -> None:
    mapped = {intent: category_for_intent(intent) for intent in ExecutionIntent}

    assert set(mapped) == set(ExecutionIntent)
    assert mapped[ExecutionIntent.RESTART_SERVICE] == ExecutionCategory.RESTART
    assert mapped[ExecutionIntent.RESTORE_BACKUP] == ExecutionCategory.RESTORE


@pytest.mark.parametrize("recommendation_class", sorted(NON_EXECUTABLE_RECOMMENDATION_CLASSES))
def test_non_executable_classes_return_none(recommendation_class: str) -> None:
    assert classify_recommendation_class(recommendation_class) is None


def test_unknown_class_does_not_become_executable() -> None:
    assert classify_recommendation_class("make-it-better") is None


def test_classification_input_is_normalized() -> None:
    first = classify_recommendation_class("Restart_Service")
    second = classify_recommendation_class(" restart-service ")

    assert first == second
    assert first is not None
    assert ExecutionConstraint.SERVICE_DISRUPTION in first.constraints
