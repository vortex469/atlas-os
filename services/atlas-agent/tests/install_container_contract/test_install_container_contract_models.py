from __future__ import annotations

import json
from copy import deepcopy

import pytest
from app.install_container_contract import (
    AgentInstallContainerErrorV1,
    AgentInstallContainerRequestV1,
    FingerprintV1,
    InstallContainerArtifactV1,
    InstallContainerLimitsV1,
    ReasonCode,
    StrictContractError,
    canonical_json,
    parse_request_json,
    request_fingerprint,
    runtime_limit_policy_fingerprint,
)
from pydantic import ValidationError

HEX = "a" * 64
UUID1 = "123e4567-e89b-42d3-a456-426614174000"
UUID2 = "123e4567-e89b-42d3-b456-426614174001"


def fingerprint(value: str = HEX) -> dict[str, str]:
    return {
        "algorithm": "sha256",
        "canonicalization": "atlas-jcs-nfc-v1",
        "value": value,
    }


def request_dict() -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "agent-install-container-request-v1",
        "operation": "install-container",
        "mode": "validate-only",
        "request_id": UUID1,
        "issued_at": "2026-08-28T12:00:00Z",
        "expires_at": "2026-08-28T12:05:00Z",
        "subject": {
            "provider": "proxmox",
            "resource_type": "qemu",
            "placement_kind": "existing-guest",
            "resource_id": "vm-101",
            "destination_fingerprint": HEX,
        },
        "approval": {
            "candidate_record_id": UUID1,
            "candidate_envelope_fingerprint": fingerprint(),
            "admission_fingerprint": fingerprint("b" * 64),
            "candidate_record_fingerprint": fingerprint("c" * 64),
            "approval_intent_id": UUID2,
            "approval_intent_fingerprint": fingerprint("d" * 64),
        },
        "artifact": {
            "kind": "single-oci-container-v1",
            "source_plan_fingerprint": fingerprint("e" * 64),
            "source_repository_path": "deploy/service.yaml",
            "source_service": "service",
            "source_content_digest": "sha256:" + "f" * 64,
            "image": "ghcr.io/example/service@sha256:" + "1" * 64,
            "runtime": "rootless-podman",
            "container_name": "atlas-0123456789abcdef",
            "command": None,
            "entrypoint": None,
            "environment": [],
            "secrets": [],
            "host_mounts": [],
            "devices": [],
            "published_ports": [],
            "network_mode": "none",
            "privileged": False,
            "read_only_root_filesystem": True,
            "capabilities_add": [],
            "capabilities_drop": ["ALL"],
            "no_new_privileges": True,
            "tmpfs": [{
                "container_path": "/tmp",
                "size_bytes": "67108864",
                "options": ["nodev", "noexec", "nosuid"],
            }],
            "restart_policy": "no",
        },
        "limits": {
            "cpu_count": "1",
            "memory_bytes": "536870912",
            "pids": "128",
            "tmpfs_bytes": "67108864",
        },
    }
    value["request_fingerprint"] = request_fingerprint(value).model_dump(mode="json")
    return value


def test_request_is_closed_immutable_and_fingerprint_bound() -> None:
    value = request_dict()
    request = AgentInstallContainerRequestV1.model_validate(value)
    assert request == parse_request_json(json.dumps(value))
    assert canonical_json(request) == canonical_json(request)
    with pytest.raises(ValidationError):
        request.request_id = UUID2  # type: ignore[misc]

    unknown = deepcopy(value)
    unknown["token"] = "do-not-echo"
    with pytest.raises(ValidationError):
        AgentInstallContainerRequestV1.model_validate(unknown)


def test_missing_or_invalid_proof_and_changed_request_fingerprint_are_rejected() -> None:
    for field in (
        "candidate_envelope_fingerprint",
        "admission_fingerprint",
        "candidate_record_fingerprint",
        "approval_intent_fingerprint",
    ):
        value = request_dict()
        del value["approval"][field]  # type: ignore[index]
        with pytest.raises(ValidationError):
            AgentInstallContainerRequestV1.model_validate(value)

    changed = request_dict()
    changed["subject"]["resource_id"] = "vm-102"  # type: ignore[index]
    with pytest.raises(ValidationError, match="fingerprint mismatch"):
        AgentInstallContainerRequestV1.model_validate(changed)


@pytest.mark.parametrize(
    ("path", "invalid"),
    [
        (("subject", "provider"), "docker"),
        (("subject", "resource_type"), "lxc"),
        (("subject", "placement_kind"), "new-guest"),
        (("artifact", "image"), "ghcr.io/example/service:latest"),
        (("artifact", "source_repository_path"), "../compose.yaml"),
        (("artifact", "runtime"), "docker"),
        (("artifact", "network_mode"), "host"),
        (("artifact", "privileged"), True),
        (("artifact", "read_only_root_filesystem"), False),
        (("limits", "memory_bytes"), "1073741824"),
    ],
)
def test_subject_artifact_runtime_filesystem_network_and_limits_are_closed(
    path: tuple[str, str], invalid: object
) -> None:
    value = request_dict()
    value[path[0]][path[1]] = invalid  # type: ignore[index]
    value["request_fingerprint"] = request_fingerprint(value).model_dump(mode="json")
    with pytest.raises(ValidationError):
        AgentInstallContainerRequestV1.model_validate(value)


def test_duplicate_keys_numbers_non_nfc_and_window_are_rejected() -> None:
    with pytest.raises(StrictContractError):
        parse_request_json('{"schema":"one","schema":"two"}')

    value = request_dict()
    value["issued_at"] = "2026-08-28T12:00:00.1Z"
    with pytest.raises(ValidationError):
        AgentInstallContainerRequestV1.model_validate(value)

    value = request_dict()
    value["expires_at"] = "2026-08-28T12:05:01Z"
    value["request_fingerprint"] = request_fingerprint(value).model_dump(mode="json")
    with pytest.raises(ValidationError, match="five minutes"):
        AgentInstallContainerRequestV1.model_validate(value)


def test_domain_separated_fingerprints_are_deterministic_and_sensitive() -> None:
    first = request_dict()
    second = deepcopy(first)
    second["artifact"]["container_name"] = "atlas-fedcba9876543210"  # type: ignore[index]
    assert request_fingerprint(first) == request_fingerprint(first)
    assert request_fingerprint(first) != request_fingerprint(second)

    request = AgentInstallContainerRequestV1.model_validate(first)
    policy = runtime_limit_policy_fingerprint(request.artifact, request.limits)
    assert policy == runtime_limit_policy_fingerprint(request.artifact, request.limits)
    assert policy != request.request_fingerprint


def test_redacted_error_has_no_payload_or_exception_fields() -> None:
    error = AgentInstallContainerErrorV1(
        schema="agent-install-container-error-v1",
        reason_code=ReasonCode.VALIDATION_CONTRACT_FAILURE,
        request_id=UUID1,
        request_fingerprint=FingerprintV1.model_validate(fingerprint()),
        correlation_id="validation-1",
        redacted=True,
    )
    dumped = error.model_dump(mode="json")
    assert set(dumped) == {
        "schema", "reason_code", "request_id", "request_fingerprint",
        "correlation_id", "redacted",
    }
    for forbidden in ("token", "exception", "image", "path", "command"):
        assert forbidden not in json.dumps(dumped)


def test_authority_fields_are_literal_false_in_closed_schemas() -> None:
    # Literal false is a schema-level refusal: strict validation cannot coerce or enable it.
    from app.install_container_contract import AgentInstallContainerValidationV1

    schema = AgentInstallContainerValidationV1.model_json_schema()
    for field in ("execution_supported", "dispatch_allowed", "mutation_allowed", "replay_allowed"):
        assert schema["properties"][field]["const"] is False


def test_artifact_and_limits_are_strict_models() -> None:
    value = request_dict()
    artifact = InstallContainerArtifactV1.model_validate(value["artifact"])
    limits = InstallContainerLimitsV1.model_validate(value["limits"])
    assert artifact.image_digest == "sha256:" + "1" * 64
    with pytest.raises(ValidationError):
        InstallContainerLimitsV1.model_validate({**limits.model_dump(), "pids": 128})
