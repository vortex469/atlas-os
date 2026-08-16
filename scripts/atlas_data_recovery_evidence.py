"""Bounded machine-readable Atlas Core recovery acceptance evidence."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

SCHEMA_VERSION = "atlas-core-recovery-evidence-v1"
ACTIVATED_SCHEMA_VERSION = "atlas-core-recovery-evidence-v2"
V3_SCHEMA_VERSION = "atlas-core-recovery-evidence-v3"
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
ACTIVATED_REQUIRED_CHECKS = REQUIRED_CHECKS + (
    "provider_intent_store_restoration",
    "provider_intent_import_receipt_preservation",
    "provider_intent_active_authority_preservation",
    "provider_intent_legacy_evidence_preservation",
    "provider_intent_yaml_non_authority",
    "provider_intent_activation_compatibility",
)
V3_REQUIRED_CHECKS = ACTIVATED_REQUIRED_CHECKS + (
    "provider_intent_v3_idempotency",
    "provider_intent_v3_replacement_isolation",
    "provider_intent_v3_suggestion_isolation",
    "provider_intent_v3_discovery_isolation",
    "provider_intent_v3_ace_isolation",
    "provider_intent_v3_legacy_yaml_isolation",
    "provider_intent_v3_lxc_unsupported",
    "provider_intent_v3_schema_v2_preserved",
    "provider_intent_v3_active_records_preserved",
    "provider_intent_v3_legacy_records_preserved",
    "provider_intent_v3_import_receipt_preserved",
    "provider_intent_v3_audit_operator_bound",
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
    *,
    provider_intent_activation: str = PROVIDER_INTENT_ACTIVATION,
    schema_version: str | None = None,
) -> RecoveryEvidence:
    if not SHA_PATTERN.fullmatch(tested_commit_sha):
        raise ValueError("tested commit SHA must be 40 lowercase hexadecimal characters")
    if provider_intent_activation not in {"not_activated", "activated"}:
        raise ValueError("Provider Intent activation is invalid")
    if schema_version is None:
        schema_version = (
            SCHEMA_VERSION
            if provider_intent_activation == "not_activated"
            else ACTIVATED_SCHEMA_VERSION
        )
    if (schema_version, provider_intent_activation) not in {
        (SCHEMA_VERSION, "not_activated"),
        (ACTIVATED_SCHEMA_VERSION, "activated"),
        (V3_SCHEMA_VERSION, "activated"),
    }:
        raise ValueError("recovery evidence schema and activation disagree")
    if schema_version == SCHEMA_VERSION:
        required_checks = REQUIRED_CHECKS
    elif schema_version == V3_SCHEMA_VERSION:
        required_checks = V3_REQUIRED_CHECKS
    else:
        required_checks = ACTIVATED_REQUIRED_CHECKS
    unknown = set(passed_checks) - set(required_checks)
    if unknown:
        raise ValueError("recovery evidence contains unknown checks")
    checks = tuple(
        RecoveryCheck(
            name,
            CheckStatus.PASSED if name in passed_checks else CheckStatus.FAILED,
        )
        for name in required_checks
    )
    status = (
        EvidenceStatus.READY
        if all(check.status is CheckStatus.PASSED for check in checks)
        else EvidenceStatus.NOT_READY
    )
    return RecoveryEvidence(
        schema_version,
        status,
        tested_commit_sha,
        BACKUP_FORMAT_VERSION,
        provider_intent_activation,
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
    if value["schema_version"] not in {
        SCHEMA_VERSION, ACTIVATED_SCHEMA_VERSION, V3_SCHEMA_VERSION,
    }:
        raise ValueError("recovery evidence schema is unsupported")
    if value["backup_format_version"] != BACKUP_FORMAT_VERSION:
        raise ValueError("recovery evidence backup format is unsupported")
    activation = value["provider_intent_activation"]
    schema = value["schema_version"]
    valid_pairs = {
        (SCHEMA_VERSION, "not_activated"),
        (ACTIVATED_SCHEMA_VERSION, "activated"),
        (V3_SCHEMA_VERSION, "activated"),
    }
    if (schema, activation) not in valid_pairs:
        raise ValueError("recovery evidence schema and activation disagree")
    if schema == SCHEMA_VERSION:
        required_checks = REQUIRED_CHECKS
    elif schema == V3_SCHEMA_VERSION:
        required_checks = V3_REQUIRED_CHECKS
    else:
        required_checks = ACTIVATED_REQUIRED_CHECKS

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
    if tuple(check.name for check in checks) != required_checks:
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
        schema,
        derived,
        sha,
        BACKUP_FORMAT_VERSION,
        activation,
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
    parser.add_argument(
        "--provider-intent-activation",
        choices=("not_activated", "activated"),
        default="not_activated",
    )
    parser.add_argument(
        "--schema-version",
        choices=(SCHEMA_VERSION, ACTIVATED_SCHEMA_VERSION, V3_SCHEMA_VERSION),
    )
    args = parser.parse_args()
    if len(args.passed_check) != len(set(args.passed_check)):
        parser.error("recovery evidence checks must not be duplicated")
    evidence = build_recovery_evidence(
        args.tested_commit,
        set(args.passed_check),
        provider_intent_activation=args.provider_intent_activation,
        schema_version=args.schema_version,
    )
    write_recovery_evidence(args.output, evidence)
    return 0 if evidence.status is EvidenceStatus.READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
