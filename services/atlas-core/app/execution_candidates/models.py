from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EXECUTION_CANDIDATE_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_COMPATIBILITY_STATUSES = frozenset(
    {"compatible", "compatible_with_warnings", "insufficient_information", "incompatible"}
)
_UNSAFE_TEXT_MARKERS = (
    "&&",
    "||",
    "`",
    "$(",
    ";",
    "rm -rf",
    "bash ",
    " sh ",
    "sudo ",
    "curl ",
    "wget ",
    "password=",
    "token=",
    "secret=",
    "api_key",
    "private_key",
)


class ExecutionCandidateModel(BaseModel):
    """Base immutable model for execution-candidate contracts."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ExecutionCandidateStatus(StrEnum):
    """Planning eligibility state for an execution candidate."""

    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"


class ExecutionCategory(StrEnum):
    """Broad execution categories that may be planned by Atlas Agent later."""

    INSTALL = "install"
    CONFIGURE = "configure"
    UPDATE = "update"
    RESTART = "restart"
    BACKUP = "backup"
    RESTORE = "restore"
    REMOVE = "remove"
    UNSUPPORTED = "unsupported"


class ExecutionIntent(StrEnum):
    """Specific intent under a broad execution category."""

    INSTALL_CONTAINER = "install-container"
    INSTALL_PROVIDER = "install-provider"
    CONFIGURE_SERVICE = "configure-service"
    ENABLE_INTEGRATION = "enable-integration"
    DISABLE_INTEGRATION = "disable-integration"
    UPDATE_COMPOSE_STACK = "update-compose-stack"
    UPDATE_CONTAINER_IMAGE = "update-container-image"
    RESTART_SERVICE = "restart-service"
    RESTART_CONTAINER = "restart-container"
    RESTART_PROVIDER = "restart-provider"
    CREATE_BACKUP = "create-backup"
    RESTORE_BACKUP = "restore-backup"
    REMOVE_RESOURCE = "remove-resource"
    REMOVE_INTEGRATION = "remove-integration"
    UNSUPPORTED_RECOMMENDATION = "unsupported-recommendation"


class ApprovalLevel(StrEnum):
    """Minimum stated approval level before planning may be considered."""

    STANDARD = "standard"
    ELEVATED = "elevated"
    DESTRUCTIVE = "destructive"


class ExecutionConstraint(StrEnum):
    """Controlled planning constraints for future Atlas Agent handoff."""

    REQUIRES_BACKUP = "requires-backup"
    REQUIRES_PROVIDER = "requires-provider"
    REQUIRES_CONNECTIVITY = "requires-connectivity"
    REQUIRES_COMPATIBILITY = "requires-compatibility"
    REQUIRES_RESOLVED_RELATIONSHIPS = "requires-resolved-relationships"
    REQUIRES_CURRENT_EVIDENCE = "requires-current-evidence"
    MANUAL_STEP_REQUIRED = "manual-step-required"
    DESTRUCTIVE_CHANGE = "destructive-change"
    SERVICE_DISRUPTION = "service-disruption"


INTENT_CATEGORY_MAP: dict[ExecutionIntent, ExecutionCategory] = {
    ExecutionIntent.INSTALL_CONTAINER: ExecutionCategory.INSTALL,
    ExecutionIntent.INSTALL_PROVIDER: ExecutionCategory.INSTALL,
    ExecutionIntent.CONFIGURE_SERVICE: ExecutionCategory.CONFIGURE,
    ExecutionIntent.ENABLE_INTEGRATION: ExecutionCategory.CONFIGURE,
    ExecutionIntent.DISABLE_INTEGRATION: ExecutionCategory.CONFIGURE,
    ExecutionIntent.UPDATE_COMPOSE_STACK: ExecutionCategory.UPDATE,
    ExecutionIntent.UPDATE_CONTAINER_IMAGE: ExecutionCategory.UPDATE,
    ExecutionIntent.RESTART_SERVICE: ExecutionCategory.RESTART,
    ExecutionIntent.RESTART_CONTAINER: ExecutionCategory.RESTART,
    ExecutionIntent.RESTART_PROVIDER: ExecutionCategory.RESTART,
    ExecutionIntent.CREATE_BACKUP: ExecutionCategory.BACKUP,
    ExecutionIntent.RESTORE_BACKUP: ExecutionCategory.RESTORE,
    ExecutionIntent.REMOVE_RESOURCE: ExecutionCategory.REMOVE,
    ExecutionIntent.REMOVE_INTEGRATION: ExecutionCategory.REMOVE,
    ExecutionIntent.UNSUPPORTED_RECOMMENDATION: ExecutionCategory.UNSUPPORTED,
}

DESTRUCTIVE_INTENTS = frozenset(
    {
        ExecutionIntent.DISABLE_INTEGRATION,
        ExecutionIntent.RESTORE_BACKUP,
        ExecutionIntent.REMOVE_RESOURCE,
        ExecutionIntent.REMOVE_INTEGRATION,
    }
)

DISRUPTIVE_INTENTS = frozenset(
    {
        ExecutionIntent.UPDATE_COMPOSE_STACK,
        ExecutionIntent.UPDATE_CONTAINER_IMAGE,
        ExecutionIntent.RESTART_SERVICE,
        ExecutionIntent.RESTART_CONTAINER,
        ExecutionIntent.RESTART_PROVIDER,
        ExecutionIntent.RESTORE_BACKUP,
        ExecutionIntent.REMOVE_RESOURCE,
        ExecutionIntent.REMOVE_INTEGRATION,
    }
)


def category_for_intent(intent: ExecutionIntent) -> ExecutionCategory:
    """Return the one supported category for an execution intent."""

    return INTENT_CATEGORY_MAP[intent]


def normalize_candidate_id_part(value: str | None) -> str:
    """Normalize a stable identity component for deterministic candidate IDs."""

    if value is None:
        return "none"
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower())
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    if not normalized:
        raise ValueError("candidate identity parts must not be empty.")
    return normalized


def build_execution_candidate_id(
    *,
    source_subsystem: str,
    source_recommendation_id: str,
    catalog_item_id: str | None,
    target_id: str,
    execution_category: ExecutionCategory,
    execution_intent: ExecutionIntent,
) -> str:
    """Build a deterministic candidate ID from immutable identity inputs only."""

    parts = (
        "candidate",
        normalize_candidate_id_part(source_subsystem),
        normalize_candidate_id_part(source_recommendation_id),
        normalize_candidate_id_part(catalog_item_id),
        normalize_candidate_id_part(target_id),
        normalize_candidate_id_part(execution_category.value),
        normalize_candidate_id_part(execution_intent.value),
    )
    return "-".join(parts)


def contains_unsafe_payload(value: str) -> bool:
    """Return true when text appears to contain command or secret-like payloads."""

    lower_value = value.lower()
    return any(marker in lower_value for marker in _UNSAFE_TEXT_MARKERS)


def _normalize_unique_string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    candidates = value if isinstance(value, (list, tuple, set, frozenset)) else (value,)
    normalized: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, str):
            raise TypeError("values must be strings.")
        item = candidate.strip().lower()
        if not item:
            raise ValueError("values must not be empty.")
        if contains_unsafe_payload(item):
            raise ValueError("values must not contain command or secret-like payloads.")
        normalized.add(item)
    return tuple(sorted(normalized))


def _normalize_unique_constraints(value: Any) -> tuple[ExecutionConstraint, ...]:
    if value is None:
        return ()
    candidates = value if isinstance(value, (list, tuple, set, frozenset)) else (value,)
    constraints = {ExecutionConstraint(candidate) for candidate in candidates}
    return tuple(sorted(constraints, key=lambda constraint: constraint.value))


class ExecutionCandidate(ExecutionCandidateModel):
    """Immutable recommendation intent that may be eligible for Agent planning."""

    id: str = Field(pattern=EXECUTION_CANDIDATE_ID_PATTERN)
    source_recommendation_id: str = Field(pattern=EXECUTION_CANDIDATE_ID_PATTERN)
    source_subsystem: str = Field(pattern=EXECUTION_CANDIDATE_ID_PATTERN)
    recommendation_class: str = Field(pattern=EXECUTION_CANDIDATE_ID_PATTERN)
    catalog_item_id: str | None = Field(default=None, pattern=EXECUTION_CANDIDATE_ID_PATTERN)
    target_id: str = Field(min_length=1)
    target_type: str = Field(pattern=EXECUTION_CANDIDATE_ID_PATTERN)
    execution_category: ExecutionCategory
    execution_intent: ExecutionIntent
    status: ExecutionCandidateStatus
    required_approval_level: ApprovalLevel
    rationale: str = Field(min_length=1)
    constraints: tuple[ExecutionConstraint, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    compatibility_assessment_id: str | None = Field(default=None, pattern=EXECUTION_CANDIDATE_ID_PATTERN)
    compatibility_status: str | None = None
    relationship_ids: tuple[str, ...] = ()
    created_at: datetime
    expires_at: datetime | None = None

    @field_validator("constraints", mode="before")
    @classmethod
    def normalize_constraints(cls, value: Any) -> tuple[ExecutionConstraint, ...]:
        return _normalize_unique_constraints(value)

    @field_validator("evidence_ids", "relationship_ids", mode="before")
    @classmethod
    def normalize_identifier_tuple(cls, value: Any) -> tuple[str, ...]:
        return _normalize_unique_string_tuple(value)

    @field_validator("target_id", "rationale", mode="before")
    @classmethod
    def validate_safe_text(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty.")
        if contains_unsafe_payload(normalized):
            raise ValueError("value must not contain command or secret-like payloads.")
        return normalized

    @field_validator("compatibility_status")
    @classmethod
    def validate_compatibility_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in _COMPATIBILITY_STATUSES:
            raise ValueError("compatibility_status is unsupported.")
        return normalized

    @model_validator(mode="after")
    def validate_candidate(self) -> ExecutionCandidate:
        expected_category = category_for_intent(self.execution_intent)
        if self.execution_category != expected_category:
            raise ValueError("execution_intent must map to execution_category.")
        expected_id = build_execution_candidate_id(
            source_subsystem=self.source_subsystem,
            source_recommendation_id=self.source_recommendation_id,
            catalog_item_id=self.catalog_item_id,
            target_id=self.target_id,
            execution_category=self.execution_category,
            execution_intent=self.execution_intent,
        )
        if self.id != expected_id:
            raise ValueError("id must match deterministic execution candidate identity.")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at.")
        return self
