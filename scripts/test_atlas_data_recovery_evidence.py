from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.atlas_data_recovery_evidence import (
    ACTIVATED_REQUIRED_CHECKS,
    ACTIVATED_SCHEMA_VERSION,
    REQUIRED_CHECKS,
    CheckStatus,
    EvidenceStatus,
    build_recovery_evidence,
    load_recovery_evidence,
    parse_recovery_evidence,
    write_recovery_evidence,
)

SHA = "a" * 40


def ready_payload() -> dict[str, object]:
    return json.loads(
        json.dumps(build_recovery_evidence(SHA, set(REQUIRED_CHECKS)).to_dict())
    )


def test_complete_actual_check_set_is_ready_and_deterministic(tmp_path: Path) -> None:
    evidence = build_recovery_evidence(SHA, set(REQUIRED_CHECKS))
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_recovery_evidence(first, evidence)
    write_recovery_evidence(second, evidence)
    assert evidence.status is EvidenceStatus.READY
    assert first.read_bytes() == second.read_bytes()
    assert load_recovery_evidence(first, expected_commit_sha=SHA) == evidence


def test_activated_evidence_uses_explicit_v2_semantics() -> None:
    evidence = build_recovery_evidence(
        SHA,
        set(ACTIVATED_REQUIRED_CHECKS),
        provider_intent_activation="activated",
    )
    payload = json.loads(json.dumps(evidence.to_dict()))
    assert evidence.schema_version == ACTIVATED_SCHEMA_VERSION
    assert evidence.status is EvidenceStatus.READY
    assert parse_recovery_evidence(payload) == evidence
    payload["schema_version"] = "atlas-core-recovery-evidence-v1"
    with pytest.raises(ValueError, match="schema and activation disagree"):
        parse_recovery_evidence(payload)


@pytest.mark.parametrize("missing", ACTIVATED_REQUIRED_CHECKS)
def test_each_missing_activated_v2_check_is_not_ready(missing: str) -> None:
    evidence = build_recovery_evidence(
        SHA,
        set(ACTIVATED_REQUIRED_CHECKS) - {missing},
        provider_intent_activation="activated",
    )
    assert evidence.status is EvidenceStatus.NOT_READY


def test_evidence_cli_exit_status_follows_required_checks(tmp_path: Path) -> None:
    script = Path(__file__).with_name("atlas_data_recovery_evidence.py")
    for name, checks, expected_code in (
        ("ready", REQUIRED_CHECKS, 0),
        (
            "cleanup-failed",
            tuple(check for check in REQUIRED_CHECKS if check != "disposable_cleanup"),
            1,
        ),
        (
            "production-guard-failed",
            tuple(
                check
                for check in REQUIRED_CHECKS
                if check != "production_volume_protection"
            ),
            1,
        ),
    ):
        output = tmp_path / f"{name}.json"
        command = [
            sys.executable,
            str(script),
            "--output",
            str(output),
            "--tested-commit",
            SHA,
        ]
        for check in checks:
            command.extend(("--passed-check", check))
        result = subprocess.run(command, check=False)
        assert result.returncode == expected_code
        expected_status = (
            EvidenceStatus.READY if expected_code == 0 else EvidenceStatus.NOT_READY
        )
        assert load_recovery_evidence(output).status is expected_status


@pytest.mark.parametrize("missing", REQUIRED_CHECKS)
def test_each_missing_required_check_is_not_ready(missing: str) -> None:
    evidence = build_recovery_evidence(SHA, set(REQUIRED_CHECKS) - {missing})
    assert evidence.status is EvidenceStatus.NOT_READY
    assert next(check for check in evidence.checks if check.name == missing).status is CheckStatus.FAILED


def test_wrong_sha_and_unexpected_provider_intent_activation_are_rejected() -> None:
    payload = ready_payload()
    with pytest.raises(ValueError, match="does not match"):
        parse_recovery_evidence(payload, expected_commit_sha="b" * 40)
    payload["provider_intent_activation"] = "activated"
    with pytest.raises(ValueError, match="activation"):
        parse_recovery_evidence(payload, expected_commit_sha=SHA)


def test_missing_or_failed_branch_cannot_declare_ready() -> None:
    payload = ready_payload()
    payload["checks"] = payload["checks"][:-1]  # type: ignore[index]
    with pytest.raises(ValueError, match="incomplete"):
        parse_recovery_evidence(payload)
    payload = ready_payload()
    payload["checks"][0]["status"] = "failed"  # type: ignore[index]
    with pytest.raises(ValueError, match="inconsistent"):
        parse_recovery_evidence(payload)


@pytest.mark.parametrize(
    "field",
    ("credential", "secret_value", "session_token", "csrf", "environment"),
)
def test_unsafe_fields_are_rejected(field: str) -> None:
    payload = ready_payload()
    payload[field] = "unsafe"
    with pytest.raises(ValueError, match="fields|prohibited"):
        parse_recovery_evidence(payload)
    assert field not in json.dumps(ready_payload())
