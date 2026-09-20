"""Closed immutable v0.64 controlled runtime definition contract.

This module deliberately describes an activation subject; it does not activate
one.  The evaluator is pure and accepts no executable command, endpoint,
credential, host setting, or ambient policy.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, UTC
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.execution_permission_grant.contract import CanonicalUuid5, OperatorId, canonical_json
from app.installation_execution_admission.contract import FingerprintV1
from app.installation_targets.contract import CanonicalUuid4

MAX_MODEL_BYTES = 192 * 1024
MAX_CREATE_BYTES = 16 * 1024
MAX_ITEMS = 32
PERMISSION = "installation.execution.worker_activation_runtime_definition.evaluate"
SCOPE = "worker_activation_runtime_definition_only"
MARKER = "worker_activation_runtime_definition_recorded"

RefusalV1 = Literal[
    "invalid_request", "unsupported_runtime", "incompatible_policy",
    "ambiguous_state", "fingerprint_mismatch", "definition_expired",
]

_SHA256 = re.compile(r"[0-9a-f]{64}")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")


def _nfc(value: str) -> str:
    if value != unicodedata.normalize("NFC", value):
        raise ValueError("strings must be NFC normalized")
    return value


def _identity(value: str) -> str:
    if not value.isascii() or _ID.fullmatch(value) is None:
        raise ValueError("canonical identity required")
    return value


def _digest(value: str) -> str:
    if _SHA256.fullmatch(value) is None:
        raise ValueError("lowercase SHA-256 digest required")
    return value


def _utc(value: str) -> str:
    if _UTC.fullmatch(value) is None:
        raise ValueError("whole-second UTC timestamp required")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise ValueError("whole-second UTC timestamp required") from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("whole-second UTC timestamp required")
    return value


Identity = Annotated[str, AfterValidator(_nfc), AfterValidator(_identity)]
Sha256 = Annotated[str, AfterValidator(_digest)]
UtcSecond = Annotated[str, AfterValidator(_utc)]


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _json_collections(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_collections(item) for key, item in value.items()}
    if isinstance(value, list):
        return tuple(_json_collections(item) for item in value)
    return value


def _plain(value: Any, depth: int = 0) -> Any:
    if depth > 32:
        raise ValueError("contract nesting exceeds bound")
    if isinstance(value, BaseModel):
        value = {**value.__dict__, **(value.__pydantic_extra__ or {})}
    if isinstance(value, dict):
        return {key: _plain(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return type(value)(_plain(item, depth + 1) for item in value)
    return value


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    @classmethod
    def model_validate_json(cls, json_data: str | bytes | bytearray, **kwargs: Any) -> Any:
        encoded = json_data.encode() if isinstance(json_data, str) else bytes(json_data)
        if len(encoded) > MAX_MODEL_BYTES:
            raise ValueError("contract envelope exceeds bound")
        raw = json.loads(encoded, object_pairs_hook=_unique_keys)
        return cls.model_validate(_json_collections(raw), **kwargs)

    @model_validator(mode="before")
    @classmethod
    def reparse(cls, value: Any) -> Any:
        raw = _plain(value)
        if len(canonical_json(raw)) > MAX_MODEL_BYTES:
            raise ValueError("contract envelope exceeds bound")
        return raw

    @model_validator(mode="after")
    def bounded(self) -> "ContractModel":
        if len(canonical_json(self)) > MAX_MODEL_BYTES:
            raise ValueError("contract envelope exceeds bound")
        return self


class RuntimeResourceLimitsV1(ContractModel):
    schema: Literal["worker-activation-runtime-resource-limits-v1"] = "worker-activation-runtime-resource-limits-v1"
    cpu_millis: int = Field(ge=1, le=1_000_000)
    memory_bytes: int = Field(ge=1, le=1 << 40)
    pid_limit: int = Field(ge=1, le=65_536)


class RuntimeFilesystemPolicyV1(ContractModel):
    schema: Literal["worker-activation-runtime-filesystem-policy-v1"] = "worker-activation-runtime-filesystem-policy-v1"
    root_read_only: Literal[True] = True
    writable_paths: tuple[Identity, ...] = ()
    mount_paths: tuple[Identity, ...] = ()

    @model_validator(mode="after")
    def bounded_paths(self) -> "RuntimeFilesystemPolicyV1":
        if len(self.writable_paths) > MAX_ITEMS or len(self.mount_paths) > MAX_ITEMS:
            raise ValueError("filesystem policy exceeds bound")
        if len(set(self.writable_paths)) != len(self.writable_paths) or len(set(self.mount_paths)) != len(self.mount_paths):
            raise ValueError("filesystem paths must be unique")
        return self


class RuntimeNetworkPolicyV1(ContractModel):
    schema: Literal["worker-activation-runtime-network-policy-v1"] = "worker-activation-runtime-network-policy-v1"
    mode: Literal["none", "allowlist"] = "none"
    egress_hosts: tuple[Identity, ...] = ()
    egress_ports: tuple[int, ...] = ()

    @model_validator(mode="after")
    def exact_policy(self) -> "RuntimeNetworkPolicyV1":
        if self.mode == "none" and (self.egress_hosts or self.egress_ports):
            raise ValueError("network allowlist is incompatible with none")
        if self.mode == "allowlist" and not self.egress_hosts:
            raise ValueError("network allowlist requires hosts")
        if any(port < 1 or port > 65535 for port in self.egress_ports) or len(self.egress_ports) > MAX_ITEMS:
            raise ValueError("invalid network port policy")
        if len(set(self.egress_hosts)) != len(self.egress_hosts) or len(set(self.egress_ports)) != len(self.egress_ports):
            raise ValueError("network policy entries must be unique")
        return self


class WorkerActivationRuntimeDefinitionV1(ContractModel):
    schema: Literal["worker-activation-runtime-definition-v1"] = "worker-activation-runtime-definition-v1"
    definition_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    runtime_name: Identity
    runtime_version: Identity
    artifact_digest: Sha256
    capabilities: tuple[Literal["cpu", "memory", "pid", "filesystem", "network"], ...]
    lifecycle: Literal["reference-only"] = "reference-only"
    resources: RuntimeResourceLimitsV1
    filesystem: RuntimeFilesystemPolicyV1
    network: RuntimeNetworkPolicyV1
    valid_until: UtcSecond
    evidence_only: Literal[True] = True
    reference_only: Literal[True] = True
    runtime_effect_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    activation_allowed: Literal[False] = False
    definition_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> "WorkerActivationRuntimeDefinitionV1":
        if not self.capabilities or len(self.capabilities) > MAX_ITEMS or len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("capabilities must be a non-empty unique tuple")
        if "network" not in self.capabilities and self.network.mode != "none":
            raise ValueError("network policy requires network capability")
        if self.definition_fingerprint != definition_fingerprint(self):
            raise ValueError("definition fingerprint mismatch")
        return self


class WorkerActivationRuntimeDefinitionCreateV1(ContractModel):
    schema: Literal["worker-activation-runtime-definition-create-v1"] = "worker-activation-runtime-definition-create-v1"
    definition_id: CanonicalUuid5
    definition_fingerprint: FingerprintV1
    valid_until: UtcSecond
    requested_scope: Literal[SCOPE] = SCOPE

    @model_validator(mode="after")
    def bounded_create(self) -> "WorkerActivationRuntimeDefinitionCreateV1":
        if len(canonical_json(self)) > MAX_CREATE_BYTES:
            raise ValueError("create envelope exceeds bound")
        return self


class WorkerActivationRuntimeDefinitionEvaluationV1(ContractModel):
    schema: Literal["worker-activation-runtime-definition-evaluation-v1"] = "worker-activation-runtime-definition-evaluation-v1"
    definition_id: CanonicalUuid5
    evaluated_at: UtcSecond
    state: Literal["recorded", "blocked"]
    eligibility: Literal[MARKER, "blocked"]
    refusal: RefusalV1 | None = None
    definition_fingerprint: FingerprintV1
    evaluation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_evaluation(self) -> "WorkerActivationRuntimeDefinitionEvaluationV1":
        if (self.state == "recorded") != (self.eligibility == MARKER) or (self.state == "blocked") != (self.refusal is not None):
            raise ValueError("evaluation shape mismatch")
        if self.evaluation_fingerprint != evaluation_fingerprint(self):
            raise ValueError("evaluation fingerprint mismatch")
        return self


class WorkerActivationRuntimeDefinitionV1Record(ContractModel):
    """The bounded, durable evidence record; it never grants runtime access."""
    schema: Literal["worker-activation-runtime-definition-record-v1"] = "worker-activation-runtime-definition-record-v1"
    definition_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    definition: WorkerActivationRuntimeDefinitionV1
    evaluation: WorkerActivationRuntimeDefinitionEvaluationV1
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    record_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_record(self) -> "WorkerActivationRuntimeDefinitionV1Record":
        if (self.definition_id, self.operator_id, self.candidate_record_id, self.valid_until) != (
            self.definition.definition_id, self.definition.operator_id,
            self.definition.candidate_record_id, self.definition.valid_until
        ) or self.evaluation.definition_id != self.definition_id or self.evaluation.definition_fingerprint != self.definition.definition_fingerprint:
            raise ValueError("definition record linkage mismatch")
        if self.subject_fingerprint != subject_fingerprint(self.operator_id, self.candidate_record_id, self.definition_id):
            raise ValueError("definition subject fingerprint mismatch")
        if self.record_fingerprint != record_fingerprint(self):
            raise ValueError("definition record fingerprint mismatch")
        return self


class WorkerActivationRuntimeDefinitionStatusV1(ContractModel):
    schema: Literal["worker-activation-runtime-definition-status-v1"] = "worker-activation-runtime-definition-status-v1"
    definition_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["active", "expired"]
    evaluation_fingerprint: FingerprintV1
    status_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_status(self) -> "WorkerActivationRuntimeDefinitionStatusV1":
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("definition status fingerprint mismatch")
        return self


class WorkerActivationRuntimeDefinitionResultV1(ContractModel):
    schema: Literal["worker-activation-runtime-definition-result-v1"] = "worker-activation-runtime-definition-result-v1"
    record: WorkerActivationRuntimeDefinitionV1Record
    status: WorkerActivationRuntimeDefinitionStatusV1
    exact_duplicate: bool = False


class WorkerActivationRuntimeDefinitionCollectionV1(ContractModel):
    schema: Literal["worker-activation-runtime-definition-collection-v1"] = "worker-activation-runtime-definition-collection-v1"
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    items: tuple[WorkerActivationRuntimeDefinitionV1Record, ...]
    count: int
    collection_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_collection(self) -> "WorkerActivationRuntimeDefinitionCollectionV1":
        if self.count != len(self.items) or self.count > MAX_ITEMS or len({x.definition_id for x in self.items}) != self.count:
            raise ValueError("definition collection bound mismatch")
        if any(x.operator_id != self.operator_id or x.candidate_record_id != self.candidate_record_id for x in self.items) or self.collection_fingerprint != collection_fingerprint(self):
            raise ValueError("definition collection linkage mismatch")
        return self


class WorkerActivationRuntimeDefinitionSubjectReservationV1(ContractModel):
    schema: Literal["worker-activation-runtime-definition-reservation-v1"] = "worker-activation-runtime-definition-reservation-v1"
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    definition_id: CanonicalUuid5
    reserved_at: UtcSecond
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    reservation_fingerprint: FingerprintV1
    permanent: Literal[True] = True

    @model_validator(mode="after")
    def exact_reservation(self) -> "WorkerActivationRuntimeDefinitionSubjectReservationV1":
        if self.subject_fingerprint != subject_fingerprint(self.operator_id, self.candidate_record_id, self.definition_id) or self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("definition reservation fingerprint mismatch")
        return self


class WorkerActivationRuntimeDefinitionAuditV1(ContractModel):
    schema: Literal["worker-activation-runtime-definition-audit-v1"] = "worker-activation-runtime-definition-audit-v1"
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    occurred_at: UtcSecond
    outcome: Literal["recorded", "indeterminate"]
    subject_fingerprint: FingerprintV1
    correlation_fingerprint: FingerprintV1
    record_fingerprint: FingerprintV1 | None
    audit_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_audit(self) -> "WorkerActivationRuntimeDefinitionAuditV1":
        if (self.record_fingerprint is not None) != (self.outcome == "recorded") or self.audit_fingerprint != audit_fingerprint(self):
            raise ValueError("definition audit mismatch")
        return self


class WorkerActivationRuntimeDefinitionErrorV1(ContractModel):
    schema: Literal["worker-activation-runtime-definition-error-v1"] = "worker-activation-runtime-definition-error-v1"
    error_code: Literal["unauthenticated", "forbidden", "installation_capability_unsupported", "invalid_request", "store_corrupt", "unavailable", "quota_exceeded", "record_too_large", "idempotency_conflict", "permanent_subject_reserved", "append_indeterminate", "definition_not_found"]
    correlation_fingerprint: FingerprintV1
    retryable: Literal[False] = False
    redacted: Literal[True] = True


def _model_fingerprint(kind: str, value: Any, field: str) -> FingerprintV1:
    raw = _plain(value)
    if isinstance(raw, dict) and "schema" not in raw:
        raw["schema"] = {
            "record": "worker-activation-runtime-definition-record-v1",
            "status": "worker-activation-runtime-definition-status-v1",
            "collection": "worker-activation-runtime-definition-collection-v1",
            "reservation": "worker-activation-runtime-definition-reservation-v1",
            "audit": "worker-activation-runtime-definition-audit-v1",
        }[kind]
    raw.pop(field, None)
    return _fingerprint(kind, raw)


def subject_fingerprint(operator_id: str, candidate_record_id: str, definition_id: str) -> FingerprintV1:
    return _fingerprint("subject", {"operator_id": operator_id, "candidate_record_id": candidate_record_id, "definition_id": definition_id})


def idempotency_key_fingerprint(operator_id: str, key: str) -> FingerprintV1:
    return _fingerprint("idempotency-key", {"operator_id": operator_id, "key": key})


def request_fingerprint(operator_id: str, candidate_record_id: str, create: WorkerActivationRuntimeDefinitionCreateV1) -> FingerprintV1:
    return _fingerprint("request", {"operator_id": operator_id, "candidate_record_id": candidate_record_id, "create": create})


def record_fingerprint(value: Any) -> FingerprintV1:
    return _model_fingerprint("record", value, "record_fingerprint")


def status_fingerprint(value: Any) -> FingerprintV1:
    return _model_fingerprint("status", value, "status_fingerprint")


def collection_fingerprint(value: Any) -> FingerprintV1:
    return _model_fingerprint("collection", value, "collection_fingerprint")


def reservation_fingerprint(value: Any) -> FingerprintV1:
    return _model_fingerprint("reservation", value, "reservation_fingerprint")


def audit_fingerprint(value: Any) -> FingerprintV1:
    return _model_fingerprint("audit", value, "audit_fingerprint")

# Public names follow the other Core evidence components.  Keep the original
# internal spelling as a compatibility alias for early consumers of P1.
WorkerActivationRuntimeDefinitionRecordV1 = WorkerActivationRuntimeDefinitionV1Record
WorkerActivationRuntimeDefinitionAuditEvidenceV1 = WorkerActivationRuntimeDefinitionAuditV1


def _fingerprint(kind: str, value: Any) -> FingerprintV1:
    import hashlib
    digest = hashlib.sha256((f"atlas:worker-activation-runtime-definition-{kind}:v1\0").encode() + canonical_json(value)).hexdigest()
    return FingerprintV1(algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=digest)


def definition_fingerprint(value: WorkerActivationRuntimeDefinitionV1 | dict[str, Any]) -> FingerprintV1:
    raw = _plain(value)
    raw.setdefault("schema", "worker-activation-runtime-definition-v1")
    raw.setdefault("lifecycle", "reference-only")
    raw.setdefault("evidence_only", True)
    raw.setdefault("reference_only", True)
    raw.setdefault("runtime_effect_allowed", False)
    raw.setdefault("worker_start_allowed", False)
    raw.setdefault("activation_allowed", False)
    raw["resources"] = RuntimeResourceLimitsV1.model_validate(raw["resources"]).model_dump(mode="json")
    raw["filesystem"] = RuntimeFilesystemPolicyV1.model_validate(raw["filesystem"]).model_dump(mode="json")
    raw["network"] = RuntimeNetworkPolicyV1.model_validate(raw["network"]).model_dump(mode="json")
    raw.pop("definition_fingerprint", None)
    return _fingerprint("definition", raw)


def evaluation_fingerprint(value: WorkerActivationRuntimeDefinitionEvaluationV1 | dict[str, Any]) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else WorkerActivationRuntimeDefinitionEvaluationV1.model_construct(**value).model_dump(mode="json")
    raw.pop("evaluation_fingerprint", None)
    return _fingerprint("evaluation", raw)


def evaluate_worker_activation_runtime_definition(value: Any, *, evaluated_at: str | None = None) -> WorkerActivationRuntimeDefinitionEvaluationV1:
    """Return a deterministic, redacted decision; never execute or echo input."""
    now = evaluated_at or "1970-01-01T00:00:00Z"
    try:
        now = _utc(now)
        definition = WorkerActivationRuntimeDefinitionV1.model_validate(value)
        if now >= definition.valid_until:
            raise ValueError("definition expired")
        result = {"definition_id": definition.definition_id, "evaluated_at": now, "state": "recorded", "eligibility": MARKER, "refusal": None, "definition_fingerprint": definition.definition_fingerprint}
    except (ValueError, TypeError, RecursionError, OverflowError, ValidationError):
        raw = value if isinstance(value, dict) else {}
        definition_id = raw.get("definition_id")
        if not isinstance(definition_id, str) or not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", definition_id):
            definition_id = "00000000-0000-5000-8000-000000000000"
        now = now if _UTC.fullmatch(now) else "1970-01-01T00:00:00Z"
        result = {"definition_id": definition_id, "evaluated_at": now, "state": "blocked", "eligibility": "blocked", "refusal": "invalid_request", "definition_fingerprint": FingerprintV1(algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value="0" * 64)}
    seed = WorkerActivationRuntimeDefinitionEvaluationV1.model_construct(**result)
    return WorkerActivationRuntimeDefinitionEvaluationV1.model_validate({**_plain(seed), "evaluation_fingerprint": evaluation_fingerprint(seed)})
