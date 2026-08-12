from __future__ import annotations

from enum import StrEnum
from typing import Final

from app.execution_candidates.models import (
    ApprovalLevel,
    ExecutionCandidateModel,
    ExecutionCategory,
    ExecutionConstraint,
    ExecutionIntent,
    category_for_intent,
)


class RecommendationClass(StrEnum):
    """Controlled recommendation-class vocabulary for candidate projection."""

    RESTART_SERVICE = "restart_service"
    RESTART_CONTAINER = "restart_container"
    RESTART_PROVIDER = "restart_provider"
    CONFIGURE_SERVICE = "configure_service"
    ENABLE_INTEGRATION = "enable_integration"
    DISABLE_INTEGRATION = "disable_integration"
    INSTALL_CONTAINER = "install_container"
    INSTALL_PROVIDER = "install_provider"
    UPDATE_COMPOSE_STACK = "update_compose_stack"
    RC1_VALIDATION_SMOKE = "rc1_validation_smoke"
    UPDATE_CONTAINER_IMAGE = "update_container_image"
    CREATE_BACKUP = "create_backup"
    RESTORE_BACKUP = "restore_backup"
    REMOVE_RESOURCE = "remove_resource"
    REMOVE_INTEGRATION = "remove_integration"
    INVESTIGATE_COMPATIBILITY = "investigate_compatibility"
    REVIEW_INCOMPATIBILITY = "review_incompatibility"
    REVIEW_COMPATIBILITY_WARNING = "review_compatibility_warning"
    REVIEW_LOGS = "review_logs"
    INSPECT_DIAGNOSTICS = "inspect_diagnostics"
    READ_DOCUMENTATION = "read_documentation"
    COMPARE_OPTIONS = "compare_options"
    MONITOR_TREND = "monitor_trend"
    VALIDATE_UNKNOWN_FACTS = "validate_unknown_facts"


class ExecutionClassification(ExecutionCandidateModel):
    """Deterministic executable classification for a recommendation class."""

    recommendation_class: RecommendationClass
    execution_category: ExecutionCategory
    execution_intent: ExecutionIntent
    required_approval_level: ApprovalLevel
    constraints: tuple[ExecutionConstraint, ...] = ()


_ADVISORY_RECOMMENDATION_CLASSES: Final[frozenset[RecommendationClass]] = frozenset(
    {
        RecommendationClass.COMPARE_OPTIONS,
        RecommendationClass.INSPECT_DIAGNOSTICS,
        RecommendationClass.INVESTIGATE_COMPATIBILITY,
        RecommendationClass.MONITOR_TREND,
        RecommendationClass.READ_DOCUMENTATION,
        RecommendationClass.REVIEW_COMPATIBILITY_WARNING,
        RecommendationClass.REVIEW_INCOMPATIBILITY,
        RecommendationClass.REVIEW_LOGS,
        RecommendationClass.VALIDATE_UNKNOWN_FACTS,
    }
)

_EXECUTABLE_RECOMMENDATION_CLASSES: Final[
    dict[RecommendationClass, tuple[ExecutionIntent, ApprovalLevel, tuple[ExecutionConstraint, ...]]]
] = {
    RecommendationClass.CONFIGURE_SERVICE: (
        ExecutionIntent.CONFIGURE_SERVICE,
        ApprovalLevel.STANDARD,
        (ExecutionConstraint.REQUIRES_PROVIDER,),
    ),
    RecommendationClass.CREATE_BACKUP: (ExecutionIntent.CREATE_BACKUP, ApprovalLevel.STANDARD, ()),
    RecommendationClass.DISABLE_INTEGRATION: (
        ExecutionIntent.DISABLE_INTEGRATION,
        ApprovalLevel.DESTRUCTIVE,
        (ExecutionConstraint.DESTRUCTIVE_CHANGE,),
    ),
    RecommendationClass.ENABLE_INTEGRATION: (
        ExecutionIntent.ENABLE_INTEGRATION,
        ApprovalLevel.ELEVATED,
        (ExecutionConstraint.REQUIRES_PROVIDER,),
    ),
    RecommendationClass.INSTALL_CONTAINER: (
        ExecutionIntent.INSTALL_CONTAINER,
        ApprovalLevel.ELEVATED,
        (
            ExecutionConstraint.REQUIRES_COMPATIBILITY,
            ExecutionConstraint.REQUIRES_PROVIDER,
            ExecutionConstraint.REQUIRES_RESOLVED_RELATIONSHIPS,
        ),
    ),
    RecommendationClass.INSTALL_PROVIDER: (
        ExecutionIntent.INSTALL_PROVIDER,
        ApprovalLevel.ELEVATED,
        (ExecutionConstraint.REQUIRES_COMPATIBILITY,),
    ),
    RecommendationClass.REMOVE_INTEGRATION: (
        ExecutionIntent.REMOVE_INTEGRATION,
        ApprovalLevel.DESTRUCTIVE,
        (
            ExecutionConstraint.DESTRUCTIVE_CHANGE,
            ExecutionConstraint.REQUIRES_BACKUP,
        ),
    ),
    RecommendationClass.REMOVE_RESOURCE: (
        ExecutionIntent.REMOVE_RESOURCE,
        ApprovalLevel.DESTRUCTIVE,
        (
            ExecutionConstraint.DESTRUCTIVE_CHANGE,
            ExecutionConstraint.REQUIRES_BACKUP,
        ),
    ),
    RecommendationClass.RESTART_CONTAINER: (
        ExecutionIntent.RESTART_CONTAINER,
        ApprovalLevel.STANDARD,
        (ExecutionConstraint.SERVICE_DISRUPTION,),
    ),
    RecommendationClass.RESTART_PROVIDER: (
        ExecutionIntent.RESTART_PROVIDER,
        ApprovalLevel.ELEVATED,
        (ExecutionConstraint.SERVICE_DISRUPTION,),
    ),
    RecommendationClass.RESTART_SERVICE: (
        ExecutionIntent.RESTART_SERVICE,
        ApprovalLevel.STANDARD,
        (ExecutionConstraint.SERVICE_DISRUPTION,),
    ),
    RecommendationClass.RESTORE_BACKUP: (
        ExecutionIntent.RESTORE_BACKUP,
        ApprovalLevel.DESTRUCTIVE,
        (
            ExecutionConstraint.DESTRUCTIVE_CHANGE,
            ExecutionConstraint.REQUIRES_BACKUP,
            ExecutionConstraint.SERVICE_DISRUPTION,
        ),
    ),
    RecommendationClass.UPDATE_COMPOSE_STACK: (
        ExecutionIntent.UPDATE_COMPOSE_STACK,
        ApprovalLevel.ELEVATED,
        (
            ExecutionConstraint.REQUIRES_BACKUP,
            ExecutionConstraint.SERVICE_DISRUPTION,
        ),
    ),
    RecommendationClass.RC1_VALIDATION_SMOKE: (
        ExecutionIntent.RC1_VALIDATION_SMOKE,
        ApprovalLevel.STANDARD,
        (ExecutionConstraint.REQUIRES_CURRENT_EVIDENCE,),
    ),
    RecommendationClass.UPDATE_CONTAINER_IMAGE: (
        ExecutionIntent.UPDATE_CONTAINER_IMAGE,
        ApprovalLevel.ELEVATED,
        (
            ExecutionConstraint.REQUIRES_BACKUP,
            ExecutionConstraint.SERVICE_DISRUPTION,
        ),
    ),
}

ADVISORY_RECOMMENDATION_CLASSES = _ADVISORY_RECOMMENDATION_CLASSES
EXECUTABLE_RECOMMENDATION_CLASSES = frozenset(
    recommendation_class.value for recommendation_class in _EXECUTABLE_RECOMMENDATION_CLASSES
)
NON_EXECUTABLE_RECOMMENDATION_CLASSES = frozenset(
    recommendation_class.value for recommendation_class in _ADVISORY_RECOMMENDATION_CLASSES
)


def normalize_recommendation_class(recommendation_class: str) -> str:
    """Normalize legacy hyphenated values into the canonical enum vocabulary."""

    return recommendation_class.strip().lower().replace("-", "_")


def parse_recommendation_class(recommendation_class: str) -> RecommendationClass:
    """Parse a recommendation-class value through the controlled vocabulary."""

    return RecommendationClass(normalize_recommendation_class(recommendation_class))


def classify_recommendation_class(
    recommendation_class: str | RecommendationClass,
) -> ExecutionClassification | None:
    """Map a recommendation class to executable intent, or None when advisory."""

    try:
        parsed = (
            recommendation_class
            if isinstance(recommendation_class, RecommendationClass)
            else parse_recommendation_class(recommendation_class)
        )
    except ValueError:
        return None
    if parsed in _ADVISORY_RECOMMENDATION_CLASSES:
        return None
    mapped = _EXECUTABLE_RECOMMENDATION_CLASSES.get(parsed)
    if mapped is None:
        return None
    intent, approval_level, constraints = mapped
    return ExecutionClassification(
        recommendation_class=parsed,
        execution_category=category_for_intent(intent),
        execution_intent=intent,
        required_approval_level=approval_level,
        constraints=constraints,
    )
