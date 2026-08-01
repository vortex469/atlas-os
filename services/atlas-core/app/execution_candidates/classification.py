from __future__ import annotations

from typing import Final

from app.execution_candidates.models import (
    ApprovalLevel,
    ExecutionCandidateModel,
    ExecutionCategory,
    ExecutionConstraint,
    ExecutionIntent,
    category_for_intent,
)


class ExecutionClassification(ExecutionCandidateModel):
    """Deterministic executable classification for a recommendation class."""

    recommendation_class: str
    execution_category: ExecutionCategory
    execution_intent: ExecutionIntent
    required_approval_level: ApprovalLevel
    constraints: tuple[ExecutionConstraint, ...] = ()


_NON_EXECUTABLE_RECOMMENDATION_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "compare-options",
        "explain-warning",
        "inspect-diagnostics",
        "investigate-compatibility",
        "monitor-trend",
        "read-documentation",
        "review-logs",
        "validate-unknown-facts",
    }
)

_EXECUTABLE_RECOMMENDATION_CLASSES: Final[
    dict[str, tuple[ExecutionIntent, ApprovalLevel, tuple[ExecutionConstraint, ...]]]
] = {
    "backup": (ExecutionIntent.CREATE_BACKUP, ApprovalLevel.STANDARD, ()),
    "configure-service": (
        ExecutionIntent.CONFIGURE_SERVICE,
        ApprovalLevel.STANDARD,
        (ExecutionConstraint.REQUIRES_PROVIDER,),
    ),
    "create-backup": (ExecutionIntent.CREATE_BACKUP, ApprovalLevel.STANDARD, ()),
    "deploy-container": (
        ExecutionIntent.INSTALL_CONTAINER,
        ApprovalLevel.ELEVATED,
        (
            ExecutionConstraint.REQUIRES_COMPATIBILITY,
            ExecutionConstraint.REQUIRES_PROVIDER,
            ExecutionConstraint.REQUIRES_RESOLVED_RELATIONSHIPS,
        ),
    ),
    "disable-integration": (
        ExecutionIntent.DISABLE_INTEGRATION,
        ApprovalLevel.DESTRUCTIVE,
        (ExecutionConstraint.DESTRUCTIVE_CHANGE,),
    ),
    "enable-integration": (
        ExecutionIntent.ENABLE_INTEGRATION,
        ApprovalLevel.ELEVATED,
        (ExecutionConstraint.REQUIRES_PROVIDER,),
    ),
    "install-container": (
        ExecutionIntent.INSTALL_CONTAINER,
        ApprovalLevel.ELEVATED,
        (
            ExecutionConstraint.REQUIRES_COMPATIBILITY,
            ExecutionConstraint.REQUIRES_PROVIDER,
            ExecutionConstraint.REQUIRES_RESOLVED_RELATIONSHIPS,
        ),
    ),
    "install-provider": (
        ExecutionIntent.INSTALL_PROVIDER,
        ApprovalLevel.ELEVATED,
        (ExecutionConstraint.REQUIRES_COMPATIBILITY,),
    ),
    "remove-integration": (
        ExecutionIntent.REMOVE_INTEGRATION,
        ApprovalLevel.DESTRUCTIVE,
        (
            ExecutionConstraint.DESTRUCTIVE_CHANGE,
            ExecutionConstraint.REQUIRES_BACKUP,
        ),
    ),
    "remove-resource": (
        ExecutionIntent.REMOVE_RESOURCE,
        ApprovalLevel.DESTRUCTIVE,
        (
            ExecutionConstraint.DESTRUCTIVE_CHANGE,
            ExecutionConstraint.REQUIRES_BACKUP,
        ),
    ),
    "restart-container": (
        ExecutionIntent.RESTART_CONTAINER,
        ApprovalLevel.STANDARD,
        (ExecutionConstraint.SERVICE_DISRUPTION,),
    ),
    "restart-provider": (
        ExecutionIntent.RESTART_PROVIDER,
        ApprovalLevel.ELEVATED,
        (ExecutionConstraint.SERVICE_DISRUPTION,),
    ),
    "restart-service": (
        ExecutionIntent.RESTART_SERVICE,
        ApprovalLevel.STANDARD,
        (ExecutionConstraint.SERVICE_DISRUPTION,),
    ),
    "restore": (
        ExecutionIntent.RESTORE_BACKUP,
        ApprovalLevel.DESTRUCTIVE,
        (
            ExecutionConstraint.DESTRUCTIVE_CHANGE,
            ExecutionConstraint.REQUIRES_BACKUP,
            ExecutionConstraint.SERVICE_DISRUPTION,
        ),
    ),
    "restore-backup": (
        ExecutionIntent.RESTORE_BACKUP,
        ApprovalLevel.DESTRUCTIVE,
        (
            ExecutionConstraint.DESTRUCTIVE_CHANGE,
            ExecutionConstraint.REQUIRES_BACKUP,
            ExecutionConstraint.SERVICE_DISRUPTION,
        ),
    ),
    "update-compose-stack": (
        ExecutionIntent.UPDATE_COMPOSE_STACK,
        ApprovalLevel.ELEVATED,
        (
            ExecutionConstraint.REQUIRES_BACKUP,
            ExecutionConstraint.SERVICE_DISRUPTION,
        ),
    ),
    "update-container-image": (
        ExecutionIntent.UPDATE_CONTAINER_IMAGE,
        ApprovalLevel.ELEVATED,
        (
            ExecutionConstraint.REQUIRES_BACKUP,
            ExecutionConstraint.SERVICE_DISRUPTION,
        ),
    ),
}

NON_EXECUTABLE_RECOMMENDATION_CLASSES = _NON_EXECUTABLE_RECOMMENDATION_CLASSES
EXECUTABLE_RECOMMENDATION_CLASSES = frozenset(_EXECUTABLE_RECOMMENDATION_CLASSES)


def normalize_recommendation_class(recommendation_class: str) -> str:
    """Normalize recommendation class identifiers used by Orion-style findings."""

    return recommendation_class.strip().lower().replace("_", "-")


def classify_recommendation_class(recommendation_class: str) -> ExecutionClassification | None:
    """Map a recommendation class to executable intent, or None when non-executable."""

    normalized = normalize_recommendation_class(recommendation_class)
    if normalized in _NON_EXECUTABLE_RECOMMENDATION_CLASSES:
        return None
    mapped = _EXECUTABLE_RECOMMENDATION_CLASSES.get(normalized)
    if mapped is None:
        return None
    intent, approval_level, constraints = mapped
    return ExecutionClassification(
        recommendation_class=normalized,
        execution_category=category_for_intent(intent),
        execution_intent=intent,
        required_approval_level=approval_level,
        constraints=constraints,
    )
