from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.execution_candidates.models import ExecutionCandidate

FINGERPRINT_VERSION = "candidate-fingerprint-v1"
OPERATIONAL_FINGERPRINT_VERSION = "operational-candidate-fingerprint-v1"


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\s+", " ", value.strip())


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def _normalize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _sorted_enum_values(values: tuple[Any, ...]) -> tuple[str, ...]:
    return tuple(sorted(str(_enum_value(value)) for value in values))


def _fingerprint_payload(candidate: ExecutionCandidate) -> dict[str, object]:
    return {
        "candidate_id": candidate.id,
        "source_recommendation_id": candidate.source_recommendation_id,
        "source_subsystem": candidate.source_subsystem,
        "recommendation_class": candidate.recommendation_class,
        "catalog_item_id": candidate.catalog_item_id,
        "target_id": candidate.target_id,
        "target_type": candidate.target_type,
        "execution_category": candidate.execution_category.value,
        "execution_intent": candidate.execution_intent.value,
        "candidate_status": candidate.status.value,
        "required_approval_level": candidate.required_approval_level.value,
        "constraints": _sorted_enum_values(candidate.constraints),
        "evidence_ids": tuple(sorted(candidate.evidence_ids)),
        "compatibility_assessment_id": candidate.compatibility_assessment_id,
        "compatibility_status": candidate.compatibility_status,
        "relationship_ids": tuple(sorted(candidate.relationship_ids)),
        "expires_at": _normalize_datetime(candidate.expires_at),
        "rationale": _normalize_text(candidate.rationale),
    }


def build_candidate_fingerprint(candidate: ExecutionCandidate) -> str:
    """Build a deterministic, versioned fingerprint for a current candidate."""

    payload = _fingerprint_payload(candidate)
    version = FINGERPRINT_VERSION
    if candidate.operational_target is not None:
        version = OPERATIONAL_FINGERPRINT_VERSION
        payload["operational_target"] = candidate.operational_target.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"{version}:{digest}"
