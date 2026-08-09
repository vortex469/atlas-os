"""Candidate plan fingerprinting and workflow-shell conversion helpers."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from app.candidate_planning.models import CandidatePlan

PLAN_FINGERPRINT_VERSION = "candidate-plan-fingerprint-v1"

_UNSAFE_PLAN_PATTERNS = (
    re.compile(r"\b(?:sudo|bash|sh|python|node|npm|docker|docker-compose|kubectl)\b"),
    re.compile(r"(?:&&|\|\||;|`|\$\(|\bexec\b)"),
)


def candidate_plan_fingerprint(plan: CandidatePlan) -> str:
    """Return a deterministic versioned fingerprint for a candidate plan."""

    payload = {
        "candidate_fingerprint": plan.candidate_fingerprint,
        "candidate_id": plan.candidate_id,
        "constraints": sorted(plan.constraints),
        "evidence_ids": sorted(plan.evidence_ids),
        "identifier": plan.identifier,
        "likely_affected_components": sorted(plan.likely_affected_components),
        "likely_affected_files": sorted(_path(path) for path in plan.likely_affected_files),
        "objective": _normalize_text(plan.objective),
        "planning_assumptions": sorted(_normalize_text(item) for item in plan.assumptions),
        "proposed_descriptive_steps": tuple(
            _normalize_text(item) for item in plan.proposed_steps
        ),
        "repository_branch": plan.repository_branch,
        "repository_head": plan.repository_head,
        "revalidated_candidate_fingerprint": plan.revalidated_candidate_fingerprint,
        "rollback_considerations": tuple(
            _normalize_text(item) for item in plan.rollback_considerations
        ),
        "session_id": plan.session_id,
        "title": _normalize_text(plan.title),
        "unresolved_questions": tuple(
            _normalize_text(item) for item in plan.unresolved_questions
        ),
        "verification_strategy": tuple(
            _normalize_text(item) for item in plan.verification_strategy
        ),
        "version": PLAN_FINGERPRINT_VERSION,
        "mutation": None
        if plan.mutation is None
        else {
            "file": _path(plan.mutation.file),
            "service": plan.mutation.service,
            "property": plan.mutation.property,
            "operation": plan.mutation.operation,
            "expected_value": plan.mutation.expected_value,
            "desired_value": plan.mutation.desired_value,
            "preservation_constraints": sorted(plan.mutation.preservation_constraints),
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{PLAN_FINGERPRINT_VERSION}:{hashlib.sha256(encoded.encode()).hexdigest()}"


def build_candidate_workflow_id(
    *,
    candidate_planning_session_id: str,
    candidate_fingerprint: str,
    plan_fingerprint: str,
) -> str:
    """Build a deterministic workflow-shell ID for one session and plan fingerprint."""

    digest = hashlib.sha256(
        f"{candidate_planning_session_id}\0{candidate_fingerprint}\0{plan_fingerprint}".encode()
    ).hexdigest()
    return f"candidate-workflow-{digest}"


def validate_candidate_plan_safe(plan: CandidatePlan) -> None:
    """Reject candidate plans that contain executable command-like content."""

    values: list[str] = [
        plan.title,
        plan.objective,
        *plan.assumptions,
        *plan.constraints,
        *plan.proposed_steps,
        *plan.likely_affected_components,
        *plan.verification_strategy,
        *plan.rollback_considerations,
        *plan.unresolved_questions,
    ]
    values.extend(_path(path) for path in plan.likely_affected_files)
    if plan.mutation is not None:
        values.extend(
            value
            for value in (
                _path(plan.mutation.file),
                plan.mutation.service,
                plan.mutation.property,
                plan.mutation.operation,
                plan.mutation.expected_value or "",
                plan.mutation.desired_value,
                *plan.mutation.preservation_constraints,
            )
            if value
        )
    for value in values:
        normalized = _normalize_text(value).lower()
        for pattern in _UNSAFE_PLAN_PATTERNS:
            if pattern.search(normalized):
                raise ValueError("Candidate plan contains executable command-like content.")


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _path(value: Path) -> str:
    return value.as_posix()
