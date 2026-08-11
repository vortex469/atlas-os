"""Versioned contracts for the future Agent-to-execution-worker boundary.

S1 defines data and validation only. It does not add a worker, transport, or
change the local execution engine. The worker is never an approval or workflow
authority, and the attestation fields are structured evidence, not proof of
identity.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any

SCHEMA_VERSION = 1
_DIGEST_PREFIX = "execution-request-digest-v1:"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:-]{0,255}$")
_HEAD_RE = re.compile(r"^[0-9a-f]{40,64}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_MAX_TEXT_BYTES = 1_048_576
_MAX_PATCH_BYTES = 4_194_304
_MAX_CHANGED_FILES = 64
_MIN_TIMEOUT = 1.0
_MAX_TIMEOUT = 3_600.0


class WorkerExecutionIntent(StrEnum):
    """Execution intents supported by the RC1 worker contract."""

    UPDATE_COMPOSE_STACK = "update-compose-stack"
    RC1_VALIDATION_SMOKE = "rc1-validation-smoke"


RC1_SMOKE_TARGET = "services/atlas-agent/tests/test_execution_engine.py"
RC1_SMOKE_MARKER = "# Atlas RC1 execution smoke marker"
RC1_SMOKE_ARGV = ("atlas-rc1-validation-smoke",)


class WorkerExecutionStatus(StrEnum):
    """Outcome category, kept separate from the failure reason."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class WorkerFailureCode(StrEnum):
    """Deterministic failure reasons returned by a future worker."""

    STALE_REPOSITORY = "stale_repository"
    INVALID_REQUEST = "invalid_request"
    INVALID_ARGV = "invalid_argv"
    SANDBOX_UNAVAILABLE = "sandbox_unavailable"
    AUTH_UNAVAILABLE = "auth_unavailable"
    TIMEOUT = "timeout"
    CODEX_FAILED = "codex_failed"
    OUT_OF_SCOPE_CHANGES = "out_of_scope_changes"
    NO_COMMITTABLE_CHANGES = "no_committable_changes"
    DUPLICATE_REQUEST = "duplicate_request"
    WORKER_UNAVAILABLE = "worker_unavailable"
    WORKER_CRASH = "worker_crash"


@dataclass(frozen=True, slots=True)
class BoundedOutput:
    """Captured output with explicit truncation evidence."""

    text: str
    truncated: bool = False
    original_bytes: int | None = None

    def validate(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("output text must be a string")
        encoded = len(self.text.encode("utf-8"))
        if encoded > _MAX_TEXT_BYTES:
            raise ValueError("output exceeds the contract bound")
        if self.original_bytes is not None and (
            not isinstance(self.original_bytes, int)
            or self.original_bytes < encoded
        ):
            raise ValueError("invalid output original_bytes")
        if self.truncated and (
            self.original_bytes is None or self.original_bytes <= encoded
        ):
            raise ValueError("truncated output requires larger original_bytes")
        if not self.truncated and self.original_bytes not in (None, encoded):
            raise ValueError("untruncated output has inconsistent original_bytes")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "text": self.text,
            "truncated": self.truncated,
            "original_bytes": self.original_bytes,
        }

    @classmethod
    def from_dict(cls, value: Any) -> BoundedOutput:
        if not isinstance(value, dict) or set(value) != {
            "text",
            "truncated",
            "original_bytes",
        }:
            raise ValueError("invalid bounded output")
        result = cls(value["text"], value["truncated"], value["original_bytes"])
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class WorkerAttestation:
    """Structured runtime evidence, not a cryptographic attestation."""

    runtime_uid: int
    readonly_rootfs: bool
    no_new_privileges: bool
    effective_capabilities: str
    sandbox_profile: str

    def validate(self) -> None:
        if self.runtime_uid != 10001:
            raise ValueError("worker runtime uid must be 10001")
        if not isinstance(self.readonly_rootfs, bool) or not self.readonly_rootfs:
            raise ValueError("worker rootfs must be read-only")
        if not isinstance(self.no_new_privileges, bool) or not self.no_new_privileges:
            raise ValueError("worker must have no-new-privileges")
        if not self.effective_capabilities or any(
            char not in "0123456789abcdefABCDEF, _-" for char in self.effective_capabilities
        ):
            raise ValueError("invalid capability representation")
        if not self.sandbox_profile or "unconfined" in self.sandbox_profile.lower():
            raise ValueError("sandbox profile must be named and confined")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "runtime_uid": self.runtime_uid,
            "readonly_rootfs": self.readonly_rootfs,
            "no_new_privileges": self.no_new_privileges,
            "effective_capabilities": self.effective_capabilities,
            "sandbox_profile": self.sandbox_profile,
        }

    @classmethod
    def from_dict(cls, value: Any) -> WorkerAttestation:
        fields = {
            "runtime_uid",
            "readonly_rootfs",
            "no_new_privileges",
            "effective_capabilities",
            "sandbox_profile",
        }
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError("invalid worker attestation")
        result = cls(
            runtime_uid=value["runtime_uid"],
            readonly_rootfs=value["readonly_rootfs"],
            no_new_privileges=value["no_new_privileges"],
            effective_capabilities=value["effective_capabilities"],
            sandbox_profile=value["sandbox_profile"],
        )
        result.validate()
        return result


def _validate_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ValueError(f"invalid {name}")


def _validate_path(value: str, name: str, *, allow_dot: bool) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise ValueError(f"invalid {name}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or (not allow_dot and value == "."):
        raise ValueError(f"unsafe {name}")
    normalized = path.as_posix()
    if normalized == "." and not allow_dot:
        raise ValueError(f"unsafe {name}")
    return normalized


def _canonical_files(files: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized = tuple(_validate_path(item, "affected file", allow_dot=False) for item in files)
    if len(normalized) != len(set(normalized)):
        raise ValueError("duplicate affected file")
    if len(normalized) > _MAX_CHANGED_FILES:
        raise ValueError("too many affected files")
    return tuple(sorted(normalized))


def _canonical_request_payload(request: WorkerExecutionRequest) -> dict[str, Any]:
    return {
        "schema_version": request.schema_version,
        "execution_request_id": request.execution_request_id,
        "workflow_id": request.workflow_id,
        "candidate_id": request.candidate_id,
        "candidate_fingerprint": request.candidate_fingerprint,
        "plan_id": request.plan_id,
        "plan_fingerprint": request.plan_fingerprint,
        "execution_intent": request.execution_intent,
        "repository_token": request.repository_token,
        "expected_repository_head": request.expected_repository_head,
        "repository_branch": request.repository_branch,
        "argv": list(request.argv),
        "working_directory": request.working_directory,
        "allowed_affected_files": list(request.allowed_affected_files),
        "timeout_seconds": request.timeout_seconds,
    }


def _digest_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _DIGEST_PREFIX + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class WorkerExecutionRequest:
    """Immutable, approved request intended for a future execution worker."""

    schema_version: int
    execution_request_id: str
    workflow_id: str
    candidate_id: str
    candidate_fingerprint: str
    plan_id: str
    plan_fingerprint: str
    execution_intent: str
    repository_token: str
    expected_repository_head: str
    repository_branch: str | None
    argv: tuple[str, ...]
    working_directory: str
    allowed_affected_files: tuple[str, ...]
    timeout_seconds: float
    request_digest: str

    @classmethod
    def build(cls, **values: Any) -> WorkerExecutionRequest:
        values = dict(values)
        values.setdefault("schema_version", SCHEMA_VERSION)
        values["argv"] = tuple(values["argv"])
        values["allowed_affected_files"] = _canonical_files(values["allowed_affected_files"])
        values["working_directory"] = _validate_path(
            values["working_directory"], "working directory", allow_dot=True
        )
        values["request_digest"] = ""
        request = cls(**values)
        request.validate(check_digest=False)
        return cls(**{**values, "request_digest": _digest_payload(_canonical_request_payload(request))})

    def validate(self, *, check_digest: bool = True) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported worker request schema")
        for value, name in (
            (self.execution_request_id, "execution request id"),
            (self.workflow_id, "workflow id"),
            (self.candidate_id, "candidate id"),
            (self.candidate_fingerprint, "candidate fingerprint"),
            (self.plan_id, "plan id"),
            (self.plan_fingerprint, "plan fingerprint"),
        ):
            _validate_id(value, name)
        if self.execution_intent not in (
            WorkerExecutionIntent.UPDATE_COMPOSE_STACK,
            WorkerExecutionIntent.RC1_VALIDATION_SMOKE,
        ):
            raise ValueError("unsupported execution intent")
        if not isinstance(self.repository_token, str) or not _TOKEN_RE.fullmatch(self.repository_token):
            raise ValueError("invalid repository token")
        if not isinstance(self.expected_repository_head, str) or not _HEAD_RE.fullmatch(
            self.expected_repository_head
        ):
            raise ValueError("invalid expected repository head")
        if self.repository_branch is not None and (
            not isinstance(self.repository_branch, str)
            or not _BRANCH_RE.fullmatch(self.repository_branch)
        ):
            raise ValueError("invalid repository branch")
        if not self.argv or any(not isinstance(item, str) or not item or "\x00" in item for item in self.argv):
            raise ValueError("invalid argv")
        if self.execution_intent == WorkerExecutionIntent.RC1_VALIDATION_SMOKE:
            if self.argv != RC1_SMOKE_ARGV:
                raise ValueError("invalid RC1 validation smoke operation")
            if self.working_directory != ".":
                raise ValueError("RC1 validation smoke must run at repository root")
            if self.allowed_affected_files != (RC1_SMOKE_TARGET,):
                raise ValueError("RC1 validation smoke target is fixed")
        elif self.argv[0] != "codex" or len(self.argv) < 3 or self.argv[1] != "exec":
            raise ValueError("unsupported Codex argv")
        _validate_path(self.working_directory, "working directory", allow_dot=True)
        _canonical_files(self.allowed_affected_files)
        if not isinstance(self.timeout_seconds, (int, float)) or not math.isfinite(self.timeout_seconds):
            raise ValueError("invalid timeout")
        if not _MIN_TIMEOUT <= self.timeout_seconds <= _MAX_TIMEOUT:
            raise ValueError("timeout outside contract bounds")
        if check_digest:
            if not isinstance(self.request_digest, str) or not re.fullmatch(
                rf"{re.escape(_DIGEST_PREFIX)}[0-9a-f]{{64}}", self.request_digest
            ):
                raise ValueError("malformed request digest")
            if self.request_digest != _digest_payload(_canonical_request_payload(self)):
                raise ValueError("request digest mismatch")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {**_canonical_request_payload(self), "request_digest": self.request_digest}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_dict(cls, value: Any) -> WorkerExecutionRequest:
        fields = set(cls.__dataclass_fields__)
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError("unknown or missing worker request fields")
        result = cls(**{**value, "argv": tuple(value["argv"]), "allowed_affected_files": tuple(value["allowed_affected_files"])})
        result.validate()
        return result

    @classmethod
    def from_json(cls, value: str) -> WorkerExecutionRequest:
        return cls.from_dict(json.loads(value))


@dataclass(frozen=True, slots=True)
class WorkerExecutionResult:
    """Bounded result evidence returned by a future execution worker."""

    schema_version: int
    execution_request_id: str
    status: WorkerExecutionStatus
    return_code: int | None
    stdout: BoundedOutput
    stderr: BoundedOutput
    changed_files: tuple[str, ...]
    patch_digest: str | None
    patch_size_bytes: int | None
    patch_truncated: bool
    duration_seconds: float
    failure_code: WorkerFailureCode | None
    workspace_head: str | None
    worker_attestation: WorkerAttestation
    base_repository_head: str | None = None
    patch: BoundedOutput | None = None

    def validate(self, request: WorkerExecutionRequest | None = None) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported worker result schema")
        _validate_id(self.execution_request_id, "execution request id")
        if request is not None and self.execution_request_id != request.execution_request_id:
            raise ValueError("result request ID mismatch")
        self.stdout.validate()
        self.stderr.validate()
        files = _canonical_files(self.changed_files)
        if files != self.changed_files:
            raise ValueError("changed files must be canonicalized")
        if (
            request is not None
            and self.failure_code is not WorkerFailureCode.OUT_OF_SCOPE_CHANGES
            and not set(files).issubset(request.allowed_affected_files)
        ):
            raise ValueError("changed file is outside approved scope")
        if self.patch_digest is not None and not re.fullmatch(r"sha256:[0-9a-f]{64}", self.patch_digest):
            raise ValueError("malformed patch digest")
        if self.patch_size_bytes is not None and not 0 <= self.patch_size_bytes <= _MAX_PATCH_BYTES:
            raise ValueError("invalid patch size")
        if self.patch_truncated and self.patch_size_bytes is None:
            raise ValueError("truncated patch requires patch size")
        if not isinstance(self.duration_seconds, (int, float)) or not math.isfinite(self.duration_seconds) or self.duration_seconds < 0:
            raise ValueError("invalid duration")
        if self.workspace_head is not None and not _HEAD_RE.fullmatch(self.workspace_head):
            raise ValueError("invalid workspace head")
        if self.base_repository_head is not None and not _HEAD_RE.fullmatch(self.base_repository_head):
            raise ValueError("invalid base repository head")
        if self.patch is not None:
            self.patch.validate()
            if self.patch.original_bytes is not None and self.patch.original_bytes > _MAX_PATCH_BYTES:
                raise ValueError("patch exceeds the contract bound")
        self.worker_attestation.validate()
        if self.status is WorkerExecutionStatus.SUCCEEDED:
            if self.failure_code is not None or self.return_code != 0:
                raise ValueError("success result has failure evidence")
        elif self.failure_code is None:
            raise ValueError("non-success result requires failure code")
        if self.status is WorkerExecutionStatus.UNKNOWN and self.failure_code is not WorkerFailureCode.WORKER_CRASH:
            raise ValueError("unknown result requires worker_crash")
        if self.failure_code is WorkerFailureCode.WORKER_CRASH and self.status is not WorkerExecutionStatus.UNKNOWN:
            raise ValueError("worker_crash requires unknown status")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "execution_request_id": self.execution_request_id,
            "status": self.status,
            "return_code": self.return_code,
            "stdout": self.stdout.to_dict(),
            "stderr": self.stderr.to_dict(),
            "changed_files": list(self.changed_files),
            "patch_digest": self.patch_digest,
            "patch_size_bytes": self.patch_size_bytes,
            "patch_truncated": self.patch_truncated,
            "duration_seconds": self.duration_seconds,
            "failure_code": self.failure_code,
            "workspace_head": self.workspace_head,
            "worker_attestation": self.worker_attestation.to_dict(),
            "base_repository_head": self.base_repository_head,
            "patch": self.patch.to_dict() if self.patch else None,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_dict(cls, value: Any) -> WorkerExecutionResult:
        fields = set(cls.__dataclass_fields__)
        if not isinstance(value, dict) or not set(value).issubset(fields) or not {
            "schema_version",
            "execution_request_id",
            "status",
            "return_code",
            "stdout",
            "stderr",
            "changed_files",
            "patch_digest",
            "patch_size_bytes",
            "patch_truncated",
            "duration_seconds",
            "failure_code",
            "workspace_head",
            "worker_attestation",
        }.issubset(value):
            raise ValueError("unknown or missing worker result fields")
        result = cls(
            **{
                **value,
                "status": WorkerExecutionStatus(value["status"]),
                "failure_code": WorkerFailureCode(value["failure_code"]) if value["failure_code"] else None,
                "stdout": BoundedOutput.from_dict(value["stdout"]),
                "stderr": BoundedOutput.from_dict(value["stderr"]),
                "changed_files": tuple(value["changed_files"]),
                "worker_attestation": WorkerAttestation.from_dict(value["worker_attestation"]),
                "base_repository_head": value.get("base_repository_head"),
                "patch": BoundedOutput.from_dict(value["patch"]) if value.get("patch") else None,
            }
        )
        result.validate()
        return result

    @classmethod
    def from_json(cls, value: str) -> WorkerExecutionResult:
        return cls.from_dict(json.loads(value))


def validate_worker_execution_request(request: WorkerExecutionRequest) -> None:
    """Validate an immutable request before transport or execution."""

    request.validate()


def validate_worker_execution_result(
    result: WorkerExecutionResult, request: WorkerExecutionRequest
) -> None:
    """Validate result identity, bounds, attestation, and approved file scope."""

    result.validate(request)


__all__ = [
    "BoundedOutput",
    "WorkerAttestation",
    "WorkerExecutionIntent",
    "WorkerExecutionRequest",
    "WorkerExecutionResult",
    "WorkerExecutionStatus",
    "WorkerFailureCode",
    "validate_worker_execution_request",
    "validate_worker_execution_result",
]
