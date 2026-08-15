"""Bounded machine-readable Atlas Core recovery acceptance evidence."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

SCHEMA_VERSION = "atlas-core-recovery-evidence-v1"
BACKUP_FORMAT_VERSION = 3
PROVIDER_INTENT_ACTIVATION = "not_activated"
EXPECTED_OPERATIONAL_BOUNDARY = ("restart-service/proxmox/qemu",)
EXPECTED_REPOSITORY_BOUNDARY = ("update-compose-stack",)
SHA_PATTERN = re.compile(r"^[a-f0-9]{40}$")
REQUIRED_CHECKS = (
    "exact_commit_binding",
    "recovery_gate",
    "v3_completeness",
    "operational_ledger_no_replay",
    "operator_intent_preservation",
    "session_invalidation",
    "provider_intent_pre_activation_cleanup",
    "runtime_config_secret_restoration",
    "audit_present",
    "audit_absent",
    "handled_rollback",
    "interrupted_recovery",
    "startup_interlock",
    "unmanaged_state_preservation",
    "permission_ownership",
    "production_volume_protection",
    "legacy_v1_compatibility",
    "legacy_v2_compatibility",
    "legacy_partial_restore_guard",
    "execution_boundary_parity",
    "disposable_cleanup",
)
_FORBIDDEN_FIELD_FRAGMENTS = (
    "credential",
    "cookie",
    "csrf",
    "environment",
    "native_identity",
    "operation_payload",
    "provider_token",
    "secret_value",
    "session_token",
)


class EvidenceStatus(StrEnum):
    READY = "ready"
    NOT_READY = "not_ready"


class CheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RecoveryCheck:
    name: str
    status: CheckStatus


@dataclass(frozen=True, slots=True)
class RecoveryEvidence:
    schema_version: str
    status: EvidenceStatus
    tested_commit_sha: str
    backup_format_version: int
    provider_intent_activation: str
    operational_boundary: tuple[str, ...]
    repository_boundary: tuple[str, ...]
    checks: tuple[RecoveryCheck, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_recovery_evidence(
    tested_commit_sha: str,
    passed_checks: set[str] | frozenset[str],
) -> RecoveryEvidence:
    if not SHA_PATTERN.fullmatch(tested_commit_sha):
        raise ValueError("tested commit SHA must be 40 lowercase hexadecimal characters")
    unknown = set(passed_checks) - set(REQUIRED_CHECKS)
    if unknown:
        raise ValueError("recovery evidence contains unknown checks")
    checks = tuple(
        RecoveryCheck(
            name,
            CheckStatus.PASSED if name in passed_checks else CheckStatus.FAILED,
        )
        for name in REQUIRED_CHECKS
    )
    status = (
        EvidenceStatus.READY
        if all(check.status is CheckStatus.PASSED for check in checks)
        else EvidenceStatus.NOT_READY
    )
    return RecoveryEvidence(
        SCHEMA_VERSION,
        status,
        tested_commit_sha,
        BACKUP_FORMAT_VERSION,
        PROVIDER_INTENT_ACTIVATION,
        EXPECTED_OPERATIONAL_BOUNDARY,
        EXPECTED_REPOSITORY_BOUNDARY,
        checks,
    )


def parse_recovery_evidence(
    value: object,
    *,
    expected_commit_sha: str | None = None,
) -> RecoveryEvidence:
    if not isinstance(value, dict):
        raise TypeError("recovery evidence must be an object")
    expected_fields = {
        "schema_version",
        "status",
        "tested_commit_sha",
        "backup_format_version",
        "provider_intent_activation",
        "operational_boundary",
        "repository_boundary",
        "checks",
    }
    if set(value) != expected_fields:
        raise ValueError("recovery evidence fields are invalid")
    _reject_forbidden_fields(value)
    if value["schema_version"] != SCHEMA_VERSION:
        raise ValueError("recovery evidence schema is unsupported")
    if value["backup_format_version"] != BACKUP_FORMAT_VERSION:
        raise ValueError("recovery evidence backup format is unsupported")
    if value["provider_intent_activation"] != PROVIDER_INTENT_ACTIVATION:
        raise ValueError("recovery evidence Provider Intent activation is unsafe")
    sha = value["tested_commit_sha"]
    if not isinstance(sha, str) or not SHA_PATTERN.fullmatch(sha):
        raise ValueError("recovery evidence commit SHA is invalid")
    if expected_commit_sha is not None and sha != expected_commit_sha:
        raise ValueError("recovery evidence commit SHA does not match candidate")
    if value["operational_boundary"] != list(EXPECTED_OPERATIONAL_BOUNDARY):
        raise ValueError("recovery evidence operational boundary is invalid")
    if value["repository_boundary"] != list(EXPECTED_REPOSITORY_BOUNDARY):
        raise ValueError("recovery evidence repository boundary is invalid")
    raw_checks = value["checks"]
    if not isinstance(raw_checks, list):
        raise TypeError("recovery evidence checks must be a list")
    checks: list[RecoveryCheck] = []
    for raw in raw_checks:
        if not isinstance(raw, dict) or set(raw) != {"name", "status"}:
            raise ValueError("recovery evidence check is invalid")
        try:
            checks.append(RecoveryCheck(str(raw["name"]), CheckStatus(raw["status"])))
        except ValueError as error:
            raise ValueError("recovery evidence check status is invalid") from error
    if tuple(check.name for check in checks) != REQUIRED_CHECKS:
        raise ValueError("recovery evidence checks are incomplete or unordered")
    derived = (
        EvidenceStatus.READY
        if all(check.status is CheckStatus.PASSED for check in checks)
        else EvidenceStatus.NOT_READY
    )
    try:
        declared = EvidenceStatus(value["status"])
    except ValueError as error:
        raise ValueError("recovery evidence status is invalid") from error
    if declared is not derived:
        raise ValueError("recovery evidence summary is inconsistent")
    return RecoveryEvidence(
        SCHEMA_VERSION,
        derived,
        sha,
        BACKUP_FORMAT_VERSION,
        PROVIDER_INTENT_ACTIVATION,
        EXPECTED_OPERATIONAL_BOUNDARY,
        EXPECTED_REPOSITORY_BOUNDARY,
        tuple(checks),
    )


def load_recovery_evidence(
    path: Path,
    *,
    expected_commit_sha: str | None = None,
) -> RecoveryEvidence:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("recovery evidence cannot be read") from error
    return parse_recovery_evidence(value, expected_commit_sha=expected_commit_sha)


def write_recovery_evidence(path: Path, evidence: RecoveryEvidence) -> None:
    path.write_text(
        json.dumps(evidence.to_dict(), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _reject_forbidden_fields(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in _FORBIDDEN_FIELD_FRAGMENTS):
                raise ValueError("recovery evidence contains a prohibited field")
            _reject_forbidden_fields(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_fields(child)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tested-commit", required=True)
    parser.add_argument("--passed-check", action="append", default=[])
    args = parser.parse_args()
    evidence = build_recovery_evidence(args.tested_commit, set(args.passed_check))
    write_recovery_evidence(args.output, evidence)
    return 0 if evidence.status is EvidenceStatus.READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
