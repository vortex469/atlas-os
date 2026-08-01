"""Immutable candidate-planning intake models."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

SUPPORTED_EXECUTION_INTENTS = frozenset({"update-compose-stack"})


class CandidatePlanningSessionStatus(StrEnum):
    """Lifecycle state for side-effect-free candidate-planning sessions."""

    INTAKE_REJECTED = "intake_rejected"
    UNSUPPORTED_INTENT = "unsupported_intent"
    READY_FOR_PLANNING = "ready_for_planning"


class CoreCandidatePlanningIntakeStatus(StrEnum):
    """Atlas Core planning-intake statuses consumed over HTTP."""

    ACCEPTED_FOR_PLANNING = "accepted_for_planning"
    NOT_FOUND = "not_found"
    STALE = "stale"
    NOT_ELIGIBLE = "not_eligible"
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    TARGET_UNAVAILABLE = "target_unavailable"
    EXPIRED = "expired"
    POLICY_DENIED = "policy_denied"
    REJECTED = "rejected"


class CandidatePlanningFailureCode(StrEnum):
    """Sanitized service-level failure codes."""

    ATLAS_CORE_UNAVAILABLE = "atlas_core_unavailable"
    INTAKE_REJECTED = "intake_rejected"
    MISSING_CANDIDATE_SNAPSHOT = "missing_candidate_snapshot"
    MISSING_CANDIDATE_FINGERPRINT = "missing_candidate_fingerprint"
    UNSUPPORTED_INTENT = "unsupported_intent"
    CONFLICTING_ACTIVE_SESSION = "conflicting_active_session"
    PERSISTENCE_FAILED = "persistence_failed"


@dataclass(frozen=True, slots=True)
class CandidatePlanRequest:
    """Agent-facing request to create or reuse a planning-only session."""

    candidate_id: str
    expected_candidate_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateSnapshot:
    """Sanitized authoritative candidate snapshot returned by Atlas Core."""

    candidate_id: str
    candidate_fingerprint: str
    source_recommendation_id: str
    source_subsystem: str
    recommendation_class: str
    catalog_item_id: str | None
    target_id: str
    target_type: str
    execution_category: str
    execution_intent: str
    required_approval_level: str
    rationale: str
    constraints: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    compatibility_assessment_id: str | None
    compatibility_status: str | None
    relationship_ids: tuple[str, ...]
    expires_at: datetime | None
    intake_status: CoreCandidatePlanningIntakeStatus
    intake_reason_codes: tuple[str, ...]
    intake_timestamp: datetime


@dataclass(frozen=True, slots=True)
class CandidatePlanningSession:
    """Immutable planning-only session for one accepted current candidate."""

    identifier: str
    candidate_id: str
    candidate_fingerprint: str
    status: CandidatePlanningSessionStatus
    snapshot: CandidateSnapshot
    created_at: datetime
    unsupported_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CandidatePlanResponse:
    """Agent API response for candidate-planning intake."""

    session_id: str | None
    candidate_id: str
    status: CandidatePlanningSessionStatus
    planning_allowed: bool
    intake_status: CoreCandidatePlanningIntakeStatus
    intake_reason_codes: tuple[str, ...]
    candidate_fingerprint: str | None = None
    unsupported_reason: str | None = None


def build_candidate_planning_session_id(
    *,
    candidate_id: str,
    candidate_fingerprint: str,
) -> str:
    """Build a deterministic collision-safe session ID from full fingerprint input."""

    digest = hashlib.sha256(f"{candidate_id}\0{candidate_fingerprint}".encode()).hexdigest()
    return f"candidate-plan-{digest}"


def is_supported_execution_intent(execution_intent: str) -> bool:
    """Return whether Atlas Agent can create a planning session for an intent."""

    return execution_intent in SUPPORTED_EXECUTION_INTENTS
