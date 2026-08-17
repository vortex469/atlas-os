"""Pure P2b freshness and conflict evaluation for normalized release facts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.discovery.dynamic_sources import DynamicReleaseFact, DynamicSourceProvenance
from app.discovery.models import DISCOVERY_ID_PATTERN

FRESH_WINDOW = timedelta(hours=24)
STALE_WINDOW = timedelta(days=30)
_VERSION_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+$"
_SOURCE_TYPE_PATTERN = r"^[a-z0-9]+(?:_[a-z0-9]+)*$"


class EvaluationModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class FreshnessState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"


class FreshnessFailureReason(StrEnum):
    INVALID_CHRONOLOGY = "invalid_chronology"


class FreshnessResult(EvaluationModel):
    state: FreshnessState | None = None
    failure_reason: FreshnessFailureReason | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> FreshnessResult:
        if (self.state is None) == (self.failure_reason is None):
            raise ValueError("freshness requires exactly one state or failure reason")
        return self


class CanonicalFactKey(EvaluationModel):
    catalog_item_id: str = Field(pattern=DISCOVERY_ID_PATTERN, max_length=128)
    fact_kind: Literal["latest_stable_release"]


class CanonicalReleaseValue(EvaluationModel):
    version: str = Field(min_length=1, max_length=64, pattern=_VERSION_PATTERN)
    published_at: datetime

    @field_validator("version")
    @classmethod
    def reject_version_whitespace(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("version must be canonical")
        return value

    @field_validator("published_at")
    @classmethod
    def normalize_published_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
        return value.astimezone(UTC)


class NormalizedDynamicProvenance(EvaluationModel):
    source_id: str = Field(pattern=DISCOVERY_ID_PATTERN, max_length=128)
    source_type: str = Field(pattern=_SOURCE_TYPE_PATTERN, max_length=64)
    origin_class: Literal["public_https_allowlisted"]
    trust_tier: Literal["supplemental"]
    repository: str = Field(min_length=1, max_length=256)
    upstream_release_id: int = Field(ge=1)
    retrieved_at: datetime
    expires_at: datetime
    response_etag: str | None = Field(default=None, min_length=1, max_length=256)
    api_version: str = Field(
        min_length=1, max_length=32, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
    )

    @field_validator("repository", "response_etag")
    @classmethod
    def reject_unsafe_text(cls, value: str | None) -> str | None:
        if value is not None and (value != value.strip() or not value.isprintable()):
            raise ValueError("provenance text must be bounded printable text")
        return value

    @field_validator("retrieved_at", "expires_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provenance timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_expiry(self) -> NormalizedDynamicProvenance:
        if self.expires_at != self.retrieved_at + FRESH_WINDOW:
            raise ValueError("expiry must be exactly 24 hours after retrieval")
        return self

    @classmethod
    def from_p1(
        cls, provenance: DynamicSourceProvenance
    ) -> NormalizedDynamicProvenance:
        validated = DynamicSourceProvenance.model_validate(provenance.model_dump())
        return cls.model_validate(validated.model_dump())


class CuratedClaimProvenance(EvaluationModel):
    source_class: Literal["curated"]
    source_id: str = Field(pattern=DISCOVERY_ID_PATTERN, max_length=128)
    trust_tier: Literal["curated"]


class ExplicitCuratedReleaseClaim(EvaluationModel):
    schema_version: Literal["discovery-curated-release-claim-v1"]
    key: CanonicalFactKey
    value: CanonicalReleaseValue
    provenance: CuratedClaimProvenance


class EvaluatedDynamicClaim(EvaluationModel):
    schema_version: Literal["discovery-evaluated-dynamic-claim-v1"]
    fact: DynamicReleaseFact
    provenance: NormalizedDynamicProvenance
    freshness: FreshnessState
    evaluated_at: datetime

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_relationships(self) -> EvaluatedDynamicClaim:
        expected = evaluate_freshness(self.provenance, now=self.evaluated_at)
        if expected.state is not self.freshness:
            raise ValueError("freshness does not match provenance and evaluation time")
        return self

    @classmethod
    def from_p1(
        cls,
        *,
        fact: DynamicReleaseFact,
        provenance: DynamicSourceProvenance,
        now: datetime,
    ) -> EvaluatedDynamicClaim:
        validated_fact = DynamicReleaseFact.model_validate(fact.model_dump())
        normalized = NormalizedDynamicProvenance.from_p1(provenance)
        freshness = evaluate_freshness(normalized, now=now)
        if freshness.state is None:
            raise ClaimEvaluationError("dynamic claim chronology is invalid")
        return cls(
            schema_version="discovery-evaluated-dynamic-claim-v1",
            fact=validated_fact,
            provenance=normalized,
            freshness=freshness.state,
            evaluated_at=_normalize_now(now),
        )

    @property
    def key(self) -> CanonicalFactKey:
        return CanonicalFactKey(
            catalog_item_id=self.fact.catalog_item_id,
            fact_kind=self.fact.fact_kind,
        )

    @property
    def value(self) -> CanonicalReleaseValue:
        return CanonicalReleaseValue(
            version=self.fact.version,
            published_at=self.fact.published_at,
        )


class ConflictState(StrEnum):
    NONE = "none"
    AGREEMENT = "agreement"
    DYNAMIC_CONFLICT = "dynamic_conflict"
    CURATED_CONFLICT = "curated_conflict"


class ConflictEvaluation(EvaluationModel):
    schema_version: Literal["discovery-release-conflict-evaluation-v1"]
    key: CanonicalFactKey
    state: ConflictState
    curated_claim: ExplicitCuratedReleaseClaim | None = None
    dynamic_claims: tuple[EvaluatedDynamicClaim, ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> ConflictEvaluation:
        if self.curated_claim is None and not self.dynamic_claims:
            raise ValueError("conflict evaluation requires at least one claim")
        if self.curated_claim is not None and self.curated_claim.key != self.key:
            raise ValueError("curated claim key does not match evaluation key")
        if any(claim.key != self.key for claim in self.dynamic_claims):
            raise ValueError("dynamic claim key does not match evaluation key")
        if any(
            claim.freshness is FreshnessState.EXPIRED for claim in self.dynamic_claims
        ):
            raise ValueError("expired claims cannot appear in conflict output")
        if self.dynamic_claims != tuple(
            sorted(self.dynamic_claims, key=_claim_sort_key)
        ):
            raise ValueError("dynamic claims must use canonical order")
        if len({_claim_digest(claim) for claim in self.dynamic_claims}) != len(
            self.dynamic_claims
        ):
            raise ValueError("dynamic claims must be deduplicated")
        identities = {
            (claim.provenance.source_id, claim.provenance.retrieved_at, claim.key)
            for claim in self.dynamic_claims
        }
        if len(identities) != len(self.dynamic_claims):
            raise ValueError("dynamic claim source/retrieval identities must be unique")
        expected = _conflict_state(self.curated_claim, self.dynamic_claims)
        if self.state is not expected:
            raise ValueError("conflict state does not match claims")
        return self


class ClaimEvaluationError(ValueError):
    """Bounded invalid/contradictory claim error."""


def _normalize_now(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ClaimEvaluationError("evaluation time must be timezone-aware")
    return now.astimezone(UTC)


def evaluate_freshness(
    provenance: NormalizedDynamicProvenance | DynamicSourceProvenance,
    *,
    now: datetime,
) -> FreshnessResult:
    try:
        current = _normalize_now(now)
        if isinstance(provenance, DynamicSourceProvenance):
            candidate = NormalizedDynamicProvenance.from_p1(provenance)
        else:
            candidate = NormalizedDynamicProvenance.model_validate(
                provenance.model_dump()
            )
        if candidate.expires_at != candidate.retrieved_at + FRESH_WINDOW:
            raise ValueError
        if current < candidate.retrieved_at:
            raise ValueError
    except (ClaimEvaluationError, TypeError, ValueError, ValidationError):
        return FreshnessResult(failure_reason=FreshnessFailureReason.INVALID_CHRONOLOGY)
    if current <= candidate.expires_at:
        return FreshnessResult(state=FreshnessState.FRESH)
    if current <= candidate.retrieved_at + STALE_WINDOW:
        return FreshnessResult(state=FreshnessState.STALE)
    return FreshnessResult(state=FreshnessState.EXPIRED)


def evaluate_release_conflict(
    *,
    curated_claim: ExplicitCuratedReleaseClaim | None,
    dynamic_claims: tuple[EvaluatedDynamicClaim, ...],
) -> ConflictEvaluation | None:
    validated_curated = (
        ExplicitCuratedReleaseClaim.model_validate(curated_claim.model_dump())
        if curated_claim is not None
        else None
    )
    all_validated_dynamic = tuple(
        EvaluatedDynamicClaim.model_validate(claim.model_dump())
        for claim in dynamic_claims
    )
    validated_dynamic = tuple(
        claim
        for claim in all_validated_dynamic
        if claim.freshness is not FreshnessState.EXPIRED
    )
    if validated_curated is None and not validated_dynamic:
        return None

    keys = {claim.key for claim in validated_dynamic}
    if validated_curated is not None:
        keys.add(validated_curated.key)
    if len(keys) != 1:
        raise ClaimEvaluationError("all claims must share one canonical fact key")

    identities: dict[tuple[str, datetime, CanonicalFactKey], EvaluatedDynamicClaim] = {}
    for claim in validated_dynamic:
        identity = (
            claim.provenance.source_id,
            claim.provenance.retrieved_at,
            claim.key,
        )
        existing = identities.get(identity)
        if existing is None:
            identities[identity] = claim
        elif _claim_digest(existing) != _claim_digest(claim):
            raise ClaimEvaluationError("contradictory duplicate dynamic claim")
    ordered = tuple(sorted(identities.values(), key=_claim_sort_key))
    key = next(iter(keys))
    return ConflictEvaluation(
        schema_version="discovery-release-conflict-evaluation-v1",
        key=key,
        state=_conflict_state(validated_curated, ordered),
        curated_claim=validated_curated,
        dynamic_claims=ordered,
    )


def _conflict_state(
    curated: ExplicitCuratedReleaseClaim | None,
    dynamic: tuple[EvaluatedDynamicClaim, ...],
) -> ConflictState:
    if curated is not None:
        if not dynamic:
            return ConflictState.NONE
        if all(claim.value == curated.value for claim in dynamic):
            return ConflictState.AGREEMENT
        return ConflictState.CURATED_CONFLICT
    if len(dynamic) <= 1:
        return ConflictState.NONE
    if len({claim.value for claim in dynamic}) == 1:
        return ConflictState.AGREEMENT
    return ConflictState.DYNAMIC_CONFLICT


def _claim_payload(claim: EvaluatedDynamicClaim) -> bytes:
    payload = claim.model_dump(mode="json")
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()


def _claim_digest(claim: EvaluatedDynamicClaim) -> str:
    return hashlib.sha256(_claim_payload(claim)).hexdigest()


def _claim_sort_key(claim: EvaluatedDynamicClaim) -> tuple[object, ...]:
    return (
        claim.fact.catalog_item_id,
        claim.fact.fact_kind,
        claim.provenance.source_id,
        claim.provenance.retrieved_at,
        _claim_digest(claim),
    )
