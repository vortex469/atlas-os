"""Durable, non-executing operator operational-intent candidate source."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Literal, NamedTuple

from pydantic import Field, field_validator, model_validator

from app.execution_candidates.eligibility import validate_candidate_for_planning
from app.execution_candidates.models import (
    ApprovalLevel,
    ExecutionCandidate,
    ExecutionCandidateEffectKind,
    ExecutionCandidateModel,
    ExecutionCandidateStatus,
    ExecutionCategory,
    ExecutionConstraint,
    ExecutionIntent,
    OperationalTargetReference,
    build_execution_candidate_id,
)
from app.providers import ProviderNotFoundError
from app.services.provider_resources import (
    OperationalTargetResolutionError,
    ProviderResourceOperationError,
    ProviderResourcesNotSupportedError,
    ResolvedOperationalTarget,
)

OPERATOR_INTENT_SOURCE = "operator-intent"
OPERATOR_INTENT_RECOMMENDATION = "restart-service"
OPERATOR_INTENT_SCHEMA_VERSION = 1
MINIMUM_INTENT_LIFETIME = timedelta(minutes=1)
MAXIMUM_INTENT_LIFETIME = timedelta(hours=24)


class OperatorOperationalIntentRequest(ExecutionCandidateModel):
    execution_intent: Literal["restart-service"]
    provider_id: Literal["proxmox"]
    resource_id: str = Field(pattern=r"^[0-9]+$")
    resource_type: Literal["qemu"]
    expected_target_fingerprint: str | None = Field(
        default=None,
        pattern=r"^operational-target-fingerprint-v1:[a-f0-9]{64}$",
    )
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def require_aware_expiry(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("operator intent expiry must be timezone-aware")
        normalized = value.astimezone(UTC)
        now = datetime.now(UTC)
        if normalized <= now:
            raise ValueError("operator intent expiry must be in the future")
        if normalized > now + MAXIMUM_INTENT_LIFETIME:
            raise ValueError("operator intent expiry exceeds the maximum lifetime")
        return normalized


class OperatorOperationalIntentRecord(ExecutionCandidateModel):
    schema_version: Literal[1] = OPERATOR_INTENT_SCHEMA_VERSION
    record_id: str = Field(pattern=r"^operator-intent-record-[a-f0-9]{64}$")
    request_digest: str = Field(pattern=r"^operator-intent-request-v1:[a-f0-9]{64}$")
    operator_id: str = Field(min_length=1, max_length=200)
    execution_intent: Literal["restart-service"]
    provider_id: Literal["proxmox"]
    resource_id: str = Field(pattern=r"^[0-9]+$")
    resource_type: Literal["qemu"]
    target_fingerprint: str
    target_version: str | None = None
    expected_state: str
    created_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_identity(self) -> OperatorOperationalIntentRecord:
        if self.expires_at <= self.created_at:
            raise ValueError("operator intent expiry must follow creation")
        identity, digest = build_operator_intent_identity(
            operator_id=self.operator_id,
            execution_intent=self.execution_intent,
            provider_id=self.provider_id,
            resource_id=self.resource_id,
            resource_type=self.resource_type,
            target_fingerprint=self.target_fingerprint,
            target_version=self.target_version,
            expected_state=self.expected_state,
            created_at=self.created_at,
            expires_at=self.expires_at,
        )
        if self.record_id != identity or self.request_digest != digest:
            raise ValueError("operator intent identity does not match its immutable payload")
        return self


class OperatorIntentCreationResult(ExecutionCandidateModel):
    outcome: Literal["created", "reused"]
    candidate_id: str
    candidate: ExecutionCandidate


class OperatorIntentStoreConflictError(RuntimeError):
    """A deterministic record identity was reused with different semantics."""


class OperatorIntentStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize()
        if self.database_path != ":memory:":
            Path(self.database_path).chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS operator_intents (
                    record_id TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    schema_version INTEGER NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS operator_intent_audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at TEXT NOT NULL,
                    record_id TEXT,
                    candidate_id TEXT,
                    operator_id TEXT,
                    event TEXT NOT NULL,
                    reason TEXT NOT NULL
                )
            """)

    def put(self, record: OperatorOperationalIntentRecord) -> tuple[OperatorOperationalIntentRecord, bool]:
        encoded = record.model_dump_json()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT request_digest, record_json FROM operator_intents WHERE record_id=?",
                (record.record_id,),
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO operator_intents VALUES (?, ?, ?, ?, ?, ?)",
                    (record.record_id, record.request_digest, encoded,
                     record.created_at.isoformat(), record.expires_at.isoformat(), record.schema_version),
                )
                connection.commit()
                return record, True
            if row["request_digest"] != record.request_digest:
                connection.rollback()
                raise OperatorIntentStoreConflictError(
                    "operator intent identity conflicts with an existing immutable record"
                )
            connection.commit()
            return OperatorOperationalIntentRecord.model_validate_json(row["record_json"]), False

    def list(self) -> tuple[OperatorOperationalIntentRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM operator_intents ORDER BY record_id"
            ).fetchall()
        return tuple(
            OperatorOperationalIntentRecord.model_validate_json(row["record_json"])
            for row in rows
        )

    def append_audit(
        self,
        *,
        event: str,
        reason: str,
        occurred_at: datetime,
        record_id: str | None = None,
        candidate_id: str | None = None,
        operator_id: str | None = None,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO operator_intent_audit "
                "(occurred_at, record_id, candidate_id, operator_id, event, reason) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (occurred_at.isoformat(), record_id, candidate_id, operator_id, event, reason),
            )


TargetResolver = Callable[[str, str, str], Awaitable[ResolvedOperationalTarget]]


class OperatorIntentProjection(NamedTuple):
    candidate: ExecutionCandidate
    reason: Literal["eligible", "expired", "target_stale", "target_unavailable"]


def _canonical_digest(prefix: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()}"


def build_operator_intent_identity(**payload: object) -> tuple[str, str]:
    payload.pop("created_at", None)
    normalized = {
        key: value.astimezone(UTC).isoformat() if isinstance(value, datetime) else value
        for key, value in payload.items()
    }
    digest = _canonical_digest("operator-intent-request-v1", normalized)
    identity_digest = hashlib.sha256(digest.encode("ascii")).hexdigest()
    return f"operator-intent-record-{identity_digest}", digest


def validate_restart_target(target: ResolvedOperationalTarget) -> None:
    resource = target.resource
    metadata = resource.metadata
    if resource.provider_id != "proxmox" or resource.resource_type != "qemu":
        raise ValueError("operator intent target does not match the supported provider resource tuple")
    if resource.identity is None:
        raise ValueError("operator intent target lacks authoritative identity")
    if resource.current_state != "running":
        raise ValueError("operator intent target is not running")
    if bool(metadata.get("template")):
        raise ValueError("operator intent target is a template")
    if metadata.get("lock") not in {None, ""}:
        raise ValueError("operator intent target is locked or migrating")
    if bool(metadata.get("migrating")):
        raise ValueError("operator intent target is migrating")
    qmp = metadata.get("qmp")
    if qmp is not None and qmp != "running":
        raise ValueError("operator intent target QMP state is unavailable")


def record_from_request(
    request: OperatorOperationalIntentRequest,
    *,
    operator_id: str,
    target: ResolvedOperationalTarget,
    now: datetime,
) -> OperatorOperationalIntentRecord:
    expires_at = request.expires_at.astimezone(UTC)
    if expires_at < now + MINIMUM_INTENT_LIFETIME or expires_at > now + MAXIMUM_INTENT_LIFETIME:
        raise ValueError("operator intent expiry is outside the permitted bounded lifetime")
    validate_restart_target(target)
    if (
        request.expected_target_fingerprint is not None
        and request.expected_target_fingerprint != target.resource_fingerprint
    ):
        raise ValueError("operator intent expected target fingerprint is stale")
    payload = {
        "operator_id": operator_id,
        "execution_intent": request.execution_intent,
        "provider_id": request.provider_id,
        "resource_id": request.resource_id,
        "resource_type": request.resource_type,
        "target_fingerprint": target.resource_fingerprint,
        "target_version": target.resource.identity.token_version if target.resource.identity else None,
        "expected_state": target.resource.current_state,
        "created_at": now,
        "expires_at": expires_at,
    }
    record_id, request_digest = build_operator_intent_identity(**payload)
    return OperatorOperationalIntentRecord(
        record_id=record_id,
        request_digest=request_digest,
        **payload,
    )


def candidate_from_record(
    record: OperatorOperationalIntentRecord,
    *,
    status: ExecutionCandidateStatus,
) -> ExecutionCandidate:
    evidence_id = f"operator-intent-evidence-{record.request_digest.rsplit(':', 1)[1]}"
    candidate_id = build_execution_candidate_id(
        source_subsystem=OPERATOR_INTENT_SOURCE,
        source_recommendation_id=record.record_id,
        catalog_item_id=None,
        target_id=record.resource_id,
        execution_category=ExecutionCategory.RESTART,
        execution_intent=ExecutionIntent.RESTART_SERVICE,
    )
    return ExecutionCandidate(
        id=candidate_id,
        source_recommendation_id=record.record_id,
        source_subsystem=OPERATOR_INTENT_SOURCE,
        recommendation_class=OPERATOR_INTENT_RECOMMENDATION,
        target_id=record.resource_id,
        target_type=record.resource_type,
        execution_category=ExecutionCategory.RESTART,
        execution_intent=ExecutionIntent.RESTART_SERVICE,
        effect_kind=ExecutionCandidateEffectKind.OPERATIONAL_ACTION,
        status=status,
        required_approval_level=ApprovalLevel.STANDARD,
        rationale="An authenticated operator requested bounded maintenance for this exact resource.",
        constraints=(ExecutionConstraint.SERVICE_DISRUPTION,),
        evidence_ids=(evidence_id,),
        created_at=record.created_at,
        expires_at=record.expires_at,
        operational_target=OperationalTargetReference(
            provider_id=record.provider_id,
            resource_id=record.resource_id,
            resource_type=record.resource_type,
            resource_fingerprint=record.target_fingerprint,
            resource_version=record.target_version,
            expected_state=record.expected_state,
        ),
    )


async def project_operator_intent(
    record: OperatorOperationalIntentRecord,
    *,
    resolver: TargetResolver,
    now: datetime,
) -> ExecutionCandidate:
    return (await project_operator_intent_with_reason(record, resolver=resolver, now=now)).candidate


async def project_operator_intent_with_reason(
    record: OperatorOperationalIntentRecord,
    *,
    resolver: TargetResolver,
    now: datetime,
) -> OperatorIntentProjection:
    candidate = candidate_from_record(record, status=ExecutionCandidateStatus.NOT_ELIGIBLE)
    if record.expires_at <= now:
        return OperatorIntentProjection(candidate, "expired")
    try:
        target = await resolver(record.provider_id, record.resource_id, record.resource_type)
        validate_restart_target(target)
    except (
        OperationalTargetResolutionError,
        ProviderNotFoundError,
        ProviderResourceOperationError,
        ProviderResourcesNotSupportedError,
        ValueError,
    ):
        return OperatorIntentProjection(candidate, "target_unavailable")
    if target.resource_fingerprint != record.target_fingerprint:
        return OperatorIntentProjection(candidate, "target_stale")
    candidate = candidate.model_copy(update={"status": ExecutionCandidateStatus.ELIGIBLE})
    eligibility = validate_candidate_for_planning(
        candidate,
        available_evidence_ids=candidate.evidence_ids,
        now=now,
    )
    projected = candidate.model_copy(update={"status": eligibility.status})
    reason = "eligible" if eligibility.status is ExecutionCandidateStatus.ELIGIBLE else "target_unavailable"
    return OperatorIntentProjection(projected, reason)


async def create_operator_intent(
    request: OperatorOperationalIntentRequest,
    *,
    operator_id: str,
    store: OperatorIntentStore,
    resolver: TargetResolver,
    now: datetime | None = None,
) -> OperatorIntentCreationResult:
    creation_time = (now or datetime.now(UTC)).astimezone(UTC)
    target = await resolver(request.provider_id, request.resource_id, request.resource_type)
    record = record_from_request(
        request,
        operator_id=operator_id,
        target=target,
        now=creation_time,
    )
    stored, created = store.put(record)
    candidate = await project_operator_intent(stored, resolver=resolver, now=creation_time)
    store.append_audit(
        event="intent_accepted" if created else "intent_reused",
        reason="created" if created else "idempotent_duplicate",
        occurred_at=creation_time,
        record_id=stored.record_id,
        candidate_id=candidate.id,
        operator_id=operator_id,
    )
    return OperatorIntentCreationResult(
        outcome="created" if created else "reused",
        candidate_id=candidate.id,
        candidate=candidate,
    )
