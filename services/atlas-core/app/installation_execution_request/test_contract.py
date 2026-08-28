from __future__ import annotations

import ast
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_approval_intent.test_approval_intent import candidate, stores
from app.installation_candidate_lifecycle.test_lifecycle import NOW
from app.installation_execution_request.contract import (
    AgentInstallContainerAuditEvidenceV1,
    AgentInstallContainerRequestV1,
    AgentInstallContainerValidationV1,
    InstallationExecutionRequestCreateV1,
    InstallationExecutionRequestErrorV1,
    InstallationExecutionRequestIdempotencyV1,
    InstallationExecutionRequestResultV1,
    StrictContractError,
    _fingerprint,
    _runtime_policy_fingerprint,
    build_execution_request,
    create_fingerprint,
    execution_request_fingerprint,
    execution_request_state,
    parse_create_json,
)

REQUEST_ID = "00000000-0000-4000-8000-000000000201"
CORE_ID = "00000000-0000-4000-8000-000000000301"


def fp(value: str) -> dict[str, str]:
    return {
        "algorithm": "sha256",
        "canonicalization": "atlas-jcs-nfc-v1",
        "value": value,
    }


def chain(tmp_path: Path):
    candidates, intents = stores(tmp_path, [NOW])
    envelope = candidate(candidates)
    intent, _ = intents.create(
        operator_id="operator-a",
        candidate_record_id=envelope.candidate_record_id,
        idempotency_key="approval",
    )
    record = envelope.candidate_record
    approval = {
        "candidate_record_id": envelope.candidate_record_id,
        "candidate_envelope_fingerprint": fp(envelope.envelope_fingerprint),
        "admission_fingerprint": fp(envelope.admission_fingerprint),
        "candidate_record_fingerprint": fp(record.record_fingerprint),
        "approval_intent_id": intent.approval_intent_id,
        "approval_intent_fingerprint": fp(intent.intent_fingerprint),
    }
    request_raw = {
        "schema": "agent-install-container-request-v1",
        "operation": "install-container",
        "mode": "validate-only",
        "request_id": REQUEST_ID,
        "issued_at": "2026-08-27T11:59:00Z",
        "expires_at": "2026-08-27T12:04:00Z",
        "subject": {
            "provider": "proxmox",
            "resource_type": "qemu",
            "placement_kind": "existing-guest",
            "resource_id": "vm-101",
            "destination_fingerprint": record.current_destination_fingerprint,
        },
        "approval": approval,
        "artifact": {
            "kind": "single-oci-container-v1",
            "source_plan_fingerprint": fp(record.plan_fingerprint),
            "source_repository_path": "deploy/service.yaml",
            "source_service": "service",
            "source_content_digest": "sha256:" + "a" * 64,
            "image": "ghcr.io/atlas/service@sha256:" + "b" * 64,
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
            "tmpfs": [
                {
                    "container_path": "/tmp",
                    "size_bytes": "67108864",
                    "options": ["nodev", "noexec", "nosuid"],
                }
            ],
            "restart_policy": "no",
        },
        "limits": {
            "cpu_count": "1",
            "memory_bytes": "536870912",
            "pids": "128",
            "tmpfs_bytes": "67108864",
        },
    }
    request_raw["request_fingerprint"] = _fingerprint(
        "atlas:agent-install-container-request:v1", request_raw
    ).model_dump(mode="json")
    request = AgentInstallContainerRequestV1.model_validate(request_raw)
    evidence_raw = {
        "evidence_schema": "agent-install-container-audit-evidence-v1",
        "request_id": request.request_id,
        "request_fingerprint": request.request_fingerprint.model_dump(mode="json"),
        "approval": approval,
        "subject": request.subject.model_dump(mode="json"),
        "artifact_kind": request.artifact.kind,
        "source_plan_fingerprint": request.artifact.source_plan_fingerprint.model_dump(
            mode="json"
        ),
        "source_repository_path": request.artifact.source_repository_path,
        "source_service": request.artifact.source_service,
        "source_content_digest": request.artifact.source_content_digest,
        "image_digest": request.artifact.image_digest,
        "runtime_limit_policy_fingerprint": _runtime_policy_fingerprint(
            request.artifact, request.limits
        ).model_dump(mode="json"),
        "validated_at": "2026-08-27T11:59:30Z",
        "status": "valid_but_unsupported",
        "reason_codes": [],
        "execution_supported": False,
        "dispatch_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    evidence_raw["evidence_fingerprint"] = _fingerprint(
        "atlas:agent-install-container-audit-evidence:v1", evidence_raw
    ).model_dump(mode="json")
    evidence = AgentInstallContainerAuditEvidenceV1.model_validate(evidence_raw)
    validation_raw = {
        "schema": "agent-install-container-validation-v1",
        "request_id": request.request_id,
        "request_fingerprint": request.request_fingerprint.model_dump(mode="json"),
        "validated_at": evidence.validated_at,
        "status": evidence.status,
        "reason_codes": [],
        "execution_supported": False,
        "dispatch_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
        "evidence": evidence.model_dump(mode="json"),
    }
    validation_raw["validation_fingerprint"] = _fingerprint(
        "atlas:agent-install-container-validation:v1", validation_raw
    ).model_dump(mode="json")
    create = InstallationExecutionRequestCreateV1(
        candidate_record_id=envelope.candidate_record_id,
        approval_intent_id=intent.approval_intent_id,
        agent_request=request,
        agent_validation=AgentInstallContainerValidationV1.model_validate(
            validation_raw
        ),
    )
    return envelope, intent, create


def built(tmp_path: Path):
    envelope, intent, create = chain(tmp_path)
    return build_execution_request(
        owner_id="operator-a",
        execution_request_id=CORE_ID,
        recorded_at="2026-08-27T12:00:00Z",
        envelope=envelope,
        approval_intent=intent,
        create=create,
    )


def test_valid_request_is_closed_immutable_inert_and_deterministic(
    tmp_path: Path,
) -> None:
    request = built(tmp_path)
    assert request.execution_request_fingerprint == execution_request_fingerprint(
        owner_id="operator-a", record=request
    )
    assert execution_request_state(request, now=request.recorded_at) == "recorded"
    assert execution_request_state(request, now=request.valid_until) == "expired"
    assert not any(
        (
            request.execution_authorized,
            request.dispatch_allowed,
            request.agent_invocation_allowed,
            request.mutation_allowed,
            request.replay_allowed,
        )
    )
    with pytest.raises(ValidationError):
        request.mode = "execute"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        type(request).model_validate({**request.model_dump(), "command": "install"})
    assert request.execution_request_fingerprint != execution_request_fingerprint(
        owner_id="operator-b", record=request
    )


def test_create_json_rejects_duplicate_unknown_and_oversize(tmp_path: Path) -> None:
    _, _, create = chain(tmp_path)
    payload = json.dumps(create.model_dump(mode="json"))
    assert parse_create_json(payload) == create
    with pytest.raises(StrictContractError):
        parse_create_json(
            payload[:-1] + ',"schema":"installation-execution-request-create-v1"}'
        )
    unknown = create.model_dump(mode="json")
    unknown["token"] = "secret"
    with pytest.raises(StrictContractError):
        parse_create_json(json.dumps(unknown))
    with pytest.raises(StrictContractError):
        parse_create_json(b" " * (96 * 1024 + 1))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (
            ("agent_request", "approval", "candidate_record_fingerprint", "value"),
            "0" * 64,
        ),
        (("agent_validation", "validation_fingerprint", "value"), "0" * 64),
        (("agent_validation", "evidence", "evidence_fingerprint", "value"), "0" * 64),
    ],
)
def test_missing_or_changed_fingerprints_fail(
    tmp_path: Path, path: tuple[str, ...], value: str
) -> None:
    _, _, create = chain(tmp_path)
    raw = create.model_dump(mode="json")
    target = raw
    for key in path[:-1]:
        target = target[key]  # type: ignore[assignment,index]
    target[path[-1]] = value  # type: ignore[index]
    with pytest.raises(ValidationError):
        InstallationExecutionRequestCreateV1.model_validate(raw)


def test_ownership_linkage_freshness_and_expiry_fail_closed(tmp_path: Path) -> None:
    envelope, intent, create = chain(tmp_path)
    arguments = {
        "owner_id": "operator-a",
        "execution_request_id": CORE_ID,
        "recorded_at": "2026-08-27T12:00:00Z",
        "envelope": envelope,
        "approval_intent": intent,
        "create": create,
    }
    with pytest.raises(ValueError, match="ownership"):
        build_execution_request(**{**arguments, "owner_id": "operator-b"})
    with pytest.raises(ValueError, match="fresh"):
        build_execution_request(**{**arguments, "recorded_at": "2026-08-27T12:00:31Z"})
    stale = deepcopy(create.model_dump(mode="json"))
    stale["candidate_record_id"] = CORE_ID
    with pytest.raises(ValueError, match="linkage"):
        build_execution_request(
            **{
                **arguments,
                "create": InstallationExecutionRequestCreateV1.model_validate(stale),
            }
        )
    with pytest.raises(ValueError, match="current"):
        build_execution_request(
            **{**arguments, "recorded_at": envelope.candidate_record.valid_until}
        )


def test_redacted_error_idempotency_and_result_shapes(tmp_path: Path) -> None:
    request = built(tmp_path)
    error = InstallationExecutionRequestErrorV1(
        error_code="unavailable", correlation_id="correlation-1"
    )
    assert error.model_dump() == {
        "schema": "installation-execution-request-error-v1",
        "error_code": "unavailable",
        "correlation_id": "correlation-1",
        "execution_request_id": None,
        "execution_request_fingerprint": None,
        "redacted": True,
    }
    assert (
        InstallationExecutionRequestResultV1(
            disposition="created", request=request, error=None
        ).request
        == request
    )
    with pytest.raises(ValidationError):
        InstallationExecutionRequestResultV1(
            disposition="exact_replay", request=None, error=error
        )
    _, _, create = chain(tmp_path)
    reservation = InstallationExecutionRequestIdempotencyV1(
        owner_id="operator-a",
        key="retry-key",
        create_fingerprint=create_fingerprint(create),
    )
    assert reservation.operation == "create-installation-execution-request"
    with pytest.raises(ValidationError):
        InstallationExecutionRequestIdempotencyV1(
            owner_id="operator-a",
            key="contains space",
            create_fingerprint=create_fingerprint(create),
        )


def test_contract_has_no_forbidden_imports_or_calls() -> None:
    source_path = Path(__file__).with_name("contract.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = {
        "subprocess",
        "docker",
        "podman",
        "socket",
        "requests",
        "httpx",
        "app.clients",
        "app.deploy",
        "app.execution",
        "app.operational_dispatch",
    }
    assert not any(
        name == token or name.startswith(token + ".")
        for name in imports
        for token in forbidden
    )
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert calls.isdisjoint(
        {"open", "exec", "eval", "compile", "system", "run", "Popen"}
    )
