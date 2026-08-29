"""P4 offline goldens for the isolated dormant real-intake route factory."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

from app.real_agent_intake_boundary import (
    INTAKE_PATH,
    AgentInstallationIntakeAuthenticationContextV1,
    AgentInstallationIntakeRequestV1,
    AgentRealIntakeEvidenceService,
    AgentRealIntakeEvidenceStore,
    DormantIntakeAuthenticationError,
    create_dormant_real_intake_router,
    request_fingerprint,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tests.real_agent_intake_boundary.test_real_agent_intake_models import request_dict
from tests.real_agent_intake_boundary.test_real_agent_intake_service import (
    EvidenceReader,
)

TOKEN = "test-only-dedicated-core-intake-credential"


class Authenticator:
    def authenticate(self, bearer_credential: str):
        if bearer_credential != TOKEN:
            raise DormantIntakeAuthenticationError("unauthenticated")
        return AgentInstallationIntakeAuthenticationContextV1()


class UnauthorizedAuthenticator:
    def authenticate(self, bearer_credential: str):
        _ = bearer_credential
        raise DormantIntakeAuthenticationError("unauthorized")


def clock() -> datetime:
    return datetime(2026, 8, 29, 12, 0, 25, tzinfo=UTC)


def application(tmp_path: Path, *, enabled: bool = True, authenticator=None):
    reader = EvidenceReader()
    store = AgentRealIntakeEvidenceStore(
        tmp_path / "dormant.sqlite3",
        clock=clock,
        id_factory=lambda: uuid.UUID("00000000-0000-4000-8000-000000000703"),
    )
    service = AgentRealIntakeEvidenceService(
        store=store, evidence_reader=reader, enabled=True
    )
    app = FastAPI()
    app.include_router(
        create_dormant_real_intake_router(
            service=service,
            authenticator=authenticator or Authenticator(),
            correlation_id_factory=lambda: "offline-intake-1",
            enabled=enabled,
        )
    )
    return app, reader


def headers(**overrides: str) -> dict[str, str]:
    result = {
        "Authorization": f"Bearer {TOKEN}",
        "Idempotency-Key": "offline-key-1",
        "Content-Type": "application/json",
    }
    result.update(overrides)
    return result


def test_factory_has_exact_single_post_and_closed_openapi(tmp_path: Path) -> None:
    app, _ = application(tmp_path)
    document = app.openapi()
    assert set(document["paths"]) == {INTAKE_PATH}
    operation = document["paths"][INTAKE_PATH]
    assert set(operation) == {"post"}
    post = operation["post"]
    assert {
        (parameter["name"], parameter["in"], parameter["required"])
        for parameter in post["parameters"]
    } == {
        ("Authorization", "header", True),
        ("Idempotency-Key", "header", True),
    }
    assert set(post["requestBody"]["content"]) == {"application/json"}
    request_schema = post["requestBody"]["content"]["application/json"]["schema"]
    assert request_schema["additionalProperties"] is False
    assert request_schema["properties"]["operation"]["const"] == "install-container"
    response_schema = post["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("AgentInstallationIntakeResultV1")
    for sibling in (
        "execute",
        "deploy",
        "dispatch",
        "deliver",
        "start-workflow",
        "runtime",
    ):
        assert sibling not in document["paths"]


def test_valid_admission_exact_retry_and_fixed_false_authority(tmp_path: Path) -> None:
    app, reader = application(tmp_path)
    client = TestClient(app, base_url="https://agent.internal")
    body = request_dict()
    first = client.post(INTAKE_PATH, content=json.dumps(body), headers=headers())
    assert first.status_code == 200
    result = first.json()
    assert result["outcome"] == "admitted_for_evidence_only"
    assert result["admission"]["delivery_received"] is True
    assert result["admission"]["evidence_admission_granted"] is True
    for field in (
        "execution_admission_granted",
        "execution_authorized",
        "worker_allowed",
        "mutation_allowed",
        "replay_allowed",
    ):
        assert result["admission"][field] is False
    assert first.headers["cache-control"] == "no-store"
    second = client.post(INTAKE_PATH, content=json.dumps(body), headers=headers())
    assert second.content == first.content
    assert reader.calls == 1


def test_default_disabled_auth_authorization_and_https_fail_closed(tmp_path: Path) -> None:
    disabled, reader = application(tmp_path / "disabled", enabled=False)
    response = TestClient(disabled, base_url="https://agent.internal").post(
        INTAKE_PATH, content=json.dumps(request_dict()), headers=headers()
    )
    assert response.json() == {
        "schema": "agent-installation-intake-result-v1",
        "intake_request_id": None,
        "outcome": "rejected",
        "admission": None,
        "reason_code": "unavailable",
    }
    assert reader.calls == 0

    app, _ = application(tmp_path / "auth")
    client = TestClient(app, base_url="https://agent.internal")
    missing = client.post(
        INTAKE_PATH,
        content=json.dumps(request_dict()),
        headers={"Idempotency-Key": "key", "Content-Type": "application/json"},
    )
    assert missing.json()["reason_code"] == "unauthenticated"
    assert missing.json()["intake_request_id"] is None
    unauthorized_app, _ = application(
        tmp_path / "unauthorized", authenticator=UnauthorizedAuthenticator()
    )
    unauthorized = TestClient(
        unauthorized_app, base_url="https://agent.internal"
    ).post(INTAKE_PATH, content=json.dumps(request_dict()), headers=headers())
    assert unauthorized.status_code == missing.status_code
    assert set(unauthorized.json()) == set(missing.json())
    assert unauthorized.json()["reason_code"] == "unauthorized"

    cleartext = TestClient(app).post(
        INTAKE_PATH, content=json.dumps(request_dict()), headers=headers()
    )
    assert cleartext.json()["reason_code"] == "malformed"


def test_closed_parsing_bounds_headers_and_method_contract(tmp_path: Path) -> None:
    app, reader = application(tmp_path)
    client = TestClient(app, base_url="https://agent.internal")
    raw = json.dumps(request_dict())
    duplicate = raw[:-1] + ',"schema":"agent-installation-intake-request-v1"}'
    assert client.post(INTAKE_PATH, content=duplicate, headers=headers()).json()[
        "reason_code"
    ] == "malformed"
    unknown = {**request_dict(), "command": "install"}
    assert client.post(
        INTAKE_PATH, content=json.dumps(unknown), headers=headers()
    ).json()["reason_code"] == "malformed"
    for bad_headers in (
        headers(**{"Content-Type": "text/plain"}),
        headers(**{"Content-Encoding": "gzip"}),
        headers(**{"X-Operator-Id": "operator-a"}),
        headers(**{"X-Forwarded-Proto": "https"}),
    ):
        assert client.post(INTAKE_PATH, content=raw, headers=bad_headers).json()[
            "reason_code"
        ] == "malformed"
    assert client.post(
        INTAKE_PATH,
        content=raw,
        headers=headers(**{"Content-Length": str(64 * 1024 + 1)}),
    ).json()["reason_code"] == "malformed"
    assert client.post(
        INTAKE_PATH + "?operator_id=operator-a", content=raw, headers=headers()
    ).json()["reason_code"] == "malformed"
    method = client.get(INTAKE_PATH)
    assert method.status_code == 405
    assert method.headers["allow"] == "POST"
    assert reader.calls == 0


def test_idempotency_conflict_linkage_and_redaction(tmp_path: Path) -> None:
    app, reader = application(tmp_path)
    client = TestClient(app, base_url="https://agent.internal")
    body = request_dict()
    assert client.post(INTAKE_PATH, content=json.dumps(body), headers=headers()).json()[
        "outcome"
    ] == "admitted_for_evidence_only"
    changed = deepcopy(body)
    changed["delivery_attempt_id"] = "00000000-0000-4000-8000-000000000799"
    changed["request_fingerprint"] = request_fingerprint(changed).model_dump(mode="json")
    conflict = client.post(
        INTAKE_PATH, content=json.dumps(changed), headers=headers()
    ).json()
    assert conflict["reason_code"] == "replay_conflict"
    assert conflict["admission"] is None
    assert "operator-a" not in json.dumps(conflict)

    mismatched_app, mismatched_reader = application(tmp_path / "linkage")
    request = AgentInstallationIntakeRequestV1.model_validate(request_dict())
    mismatched_reader.linkage_override = request.envelope.linkage.model_copy(
        update={"execution_request_id": "00000000-0000-4000-8000-000000000299"}
    )
    mismatch = TestClient(
        mismatched_app, base_url="https://agent.internal"
    ).post(INTAKE_PATH, content=json.dumps(request_dict()), headers=headers())
    assert mismatch.json()["reason_code"] == "linkage_mismatch"
    assert reader.calls == 1
