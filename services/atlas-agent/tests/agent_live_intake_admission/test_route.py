from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from app.agent_live_intake_admission.contract import (
    INTAKE_PATH,
    AgentLiveIntakeAuthenticationReferenceV1,
    AgentLiveIntakeSourceV1,
    envelope_fingerprint,
    idempotency_key_fingerprint,
)
from app.agent_live_intake_admission.route import (
    LiveIntakeAuthenticationError,
    Mode0400FileLiveIntakeAuthenticator,
    create_agent_live_intake_router,
)
from app.config.settings import Settings
from fastapi import FastAPI
from fastapi.testclient import TestClient

from .test_contract import OPERATOR, canonical
from .test_service_store import authentication, service

TOKEN = "dedicated-live-intake-token"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Idempotency-Key": "send-once",
    "Content-Type": "application/json",
}


class Authenticator:
    def __init__(self, *, source_host: str = "atlas-agent.internal", fail: str | None = None) -> None:
        self.source_host = source_host
        self.fail = fail

    def authenticate(self, bearer_credential: str):
        if self.fail is not None or bearer_credential != TOKEN:
            raise LiveIntakeAuthenticationError(self.fail or "unauthenticated")
        return authentication(host=self.source_host)


def client(tmp_path: Path, *, authenticator=None, reader=None, now=None):
    kwargs = {"reader": reader} if reader is not None else {}
    if now is not None:
        kwargs["now"] = now
    live, _, env = service(tmp_path, **kwargs)
    source = AgentLiveIntakeSourceV1(host="atlas-agent.internal")
    app = FastAPI(docs_url=None, redoc_url=None)
    app.include_router(
        create_agent_live_intake_router(
            service=live,
            authenticator=authenticator or Authenticator(),
            expected_source=source,
            correlation_id_factory=lambda: "intake-route-1",
        )
    )
    return TestClient(app, base_url="https://atlas-agent.internal"), env, app


def post(test_client: TestClient, env, *, headers=None):
    return test_client.post(INTAKE_PATH, content=canonical(env), headers=headers or HEADERS)


def test_valid_admission_exact_route_and_idempotent_retry(tmp_path: Path) -> None:
    test_client, env, _ = client(tmp_path)
    first = post(test_client, env)
    assert first.status_code == 200 and first.headers["cache-control"] == "no-store"
    assert first.json()["outcome"] == "admitted_for_evidence_only"
    assert post(test_client, env).json() == first.json()
    assert test_client.get(INTAKE_PATH).status_code == 405


def test_auth_source_https_and_header_failures_are_redacted(tmp_path: Path) -> None:
    test_client, env, _ = client(tmp_path)
    for headers in (
        {"Idempotency-Key": "send-once", "Content-Type": "application/json"},
        HEADERS | {"Authorization": "Basic secret"},
        HEADERS | {"Forwarded": "proto=https"},
        HEADERS | {"X-Forwarded-For": "127.0.0.1"},
        HEADERS | {"Cookie": "secret=value"},
    ):
        body = post(test_client, env, headers=headers).json()
        assert body["outcome"] == "rejected"
        assert body["send_attempt_id"] is None and body["intake_request_id"] is None
        assert TOKEN not in json.dumps(body)
    wrong, env, _ = client(tmp_path / "source", authenticator=Authenticator(source_host="other.internal"))
    assert post(wrong, env).json()["reason_code"] == "unauthenticated"
    insecure = TestClient(test_client.app, base_url="http://atlas-agent.internal")
    assert post(insecure, env).json()["reason_code"] == "malformed"


def test_idempotency_content_type_body_depth_duplicate_and_closed_json(tmp_path: Path) -> None:
    test_client, env, _ = client(tmp_path)
    for headers in (
        {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        HEADERS | {"Idempotency-Key": "has space"},
        HEADERS | {"Idempotency-Key": "x" * 129},
        HEADERS | {"Content-Type": "application/json; charset=utf-8"},
        HEADERS | {"Content-Encoding": "gzip"},
    ):
        assert post(test_client, env, headers=headers).json()["reason_code"] == "malformed"
    duplicate = canonical(env)[:-1] + b',"schema":"agent-live-intake-envelope-v1"}'
    assert test_client.post(INTAKE_PATH, content=duplicate, headers=HEADERS).json()["reason_code"] == "malformed"
    unknown = canonical(env)[:-1] + b',"install":true}'
    assert test_client.post(INTAKE_PATH, content=unknown, headers=HEADERS).json()["reason_code"] == "malformed"
    deep = b"[" * 33 + b"0" + b"]" * 33
    assert test_client.post(INTAKE_PATH, content=deep, headers=HEADERS).json()["reason_code"] == "malformed"
    oversized = b"{" + b" " * (128 * 1024) + b"}"
    assert test_client.post(INTAKE_PATH, content=oversized, headers=HEADERS).json()["reason_code"] == "malformed"


def test_linkage_stale_conflict_and_no_replay(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from .test_service_store import Reader

    mismatched, env, _ = client(tmp_path / "linkage", reader=Reader(changed=True))
    assert post(mismatched, env).json()["reason_code"] == "linkage_mismatch"
    stale, env, _ = client(tmp_path / "stale", now=datetime(2026, 8, 29, 12, 0, 50, tzinfo=UTC))
    assert post(stale, env).json()["reason_code"] == "not_current"
    live, env, _ = client(tmp_path / "replay")
    assert post(live, env).json()["outcome"] == "admitted_for_evidence_only"
    raw = env.model_dump(mode="json")
    raw["idempotency_key_fingerprint"] = idempotency_key_fingerprint(OPERATOR, "changed").model_dump(mode="json")
    raw["envelope_fingerprint"] = envelope_fingerprint(raw).model_dump(mode="json")
    conflict = live.post(INTAKE_PATH, content=canonical(raw), headers=HEADERS)
    assert conflict.json()["reason_code"] == "replay_conflict"
    another_key = post(live, env, headers=HEADERS | {"Idempotency-Key": "another-key"})
    assert another_key.json()["reason_code"] == "replay_conflict"


def test_openapi_is_exact_and_has_no_prohibited_sibling_routes(tmp_path: Path) -> None:
    _, _, app = client(tmp_path)
    schema = app.openapi()
    assert set(schema["paths"]) == {INTAKE_PATH}
    assert set(schema["paths"][INTAKE_PATH]) == {"post"}
    operation = schema["paths"][INTAKE_PATH]["post"]
    assert [parameter["name"] for parameter in operation["parameters"]] == ["Authorization", "Idempotency-Key"]
    assert set(operation["requestBody"]["content"]) == {"application/json"}
    rendered = json.dumps(schema).lower()
    for sibling in ("/execute", "/deploy", "/workflow", "/worker", "/rollback", "/retry", "/resend"):
        assert sibling not in rendered
    assert TOKEN not in rendered and "/run/secrets" not in rendered


def test_mode_0400_authenticator_enforces_file_boundary(tmp_path: Path) -> None:
    token = tmp_path / "token"
    token.write_text(TOKEN, encoding="ascii")
    token.chmod(0o400)
    source = AgentLiveIntakeSourceV1(host="atlas-agent.internal")
    authenticator = Mode0400FileLiveIntakeAuthenticator(
        reference=AgentLiveIntakeAuthenticationReferenceV1(credential_file=str(token)),
        source=source,
    )
    assert authenticator.authenticate(TOKEN).source == source
    with pytest.raises(LiveIntakeAuthenticationError):
        authenticator.authenticate("wrong-secret")
    token.chmod(0o600)
    with pytest.raises(LiveIntakeAuthenticationError):
        authenticator.authenticate(TOKEN)
    target = tmp_path / "target"
    target.write_text(TOKEN, encoding="ascii")
    target.chmod(0o400)
    link = tmp_path / "link"
    os.symlink(target, link)
    symlink_auth = Mode0400FileLiveIntakeAuthenticator(
        reference=AgentLiveIntakeAuthenticationReferenceV1(credential_file=str(link)),
        source=source,
    )
    with pytest.raises(LiveIntakeAuthenticationError):
        symlink_auth.authenticate(TOKEN)


def test_production_registration_is_independently_default_off(
    tmp_path: Path, monkeypatch
) -> None:
    from app import main as main_module

    disabled = Settings(
        repository_root=Path.cwd().resolve(),
        state_dir=tmp_path / "disabled-state",
    )
    monkeypatch.setattr(main_module, "load_settings", lambda: disabled)
    assert INTAKE_PATH not in main_module.create_app().openapi()["paths"]

    token = tmp_path / "token"
    token.write_text(TOKEN, encoding="ascii")
    token.chmod(0o400)
    enabled = Settings(
        repository_root=Path.cwd().resolve(),
        state_dir=tmp_path / "enabled-state",
        agent_live_intake_enabled=True,
        agent_live_intake_credential_file=token,
        agent_live_intake_endpoint_fingerprint="a" * 64,
    )
    monkeypatch.setattr(main_module, "load_settings", lambda: enabled)
    application = main_module.create_app()
    assert INTAKE_PATH in application.openapi()["paths"]
    assert set(application.openapi()["paths"][INTAKE_PATH]) == {"post"}

    invalid = Settings(
        repository_root=Path.cwd().resolve(),
        state_dir=tmp_path / "invalid-state",
        agent_live_intake_enabled=True,
        agent_live_intake_credential_file=token,
        agent_live_intake_endpoint_fingerprint="",
    )
    monkeypatch.setattr(main_module, "load_settings", lambda: invalid)
    with pytest.raises(ValueError):
        main_module.create_app()


def test_live_intake_enablement_environment_is_closed(monkeypatch) -> None:
    monkeypatch.setenv("ATLAS_AGENT_LIVE_INTAKE_ENABLED", "true")
    monkeypatch.setenv("ATLAS_AGENT_LIVE_INTAKE_SOURCE_HOST", "agent.internal")
    monkeypatch.setenv("ATLAS_AGENT_LIVE_INTAKE_CREDENTIAL_FILE", "/run/secrets/intake")
    monkeypatch.setenv("ATLAS_AGENT_LIVE_INTAKE_ENDPOINT_FINGERPRINT", "b" * 64)
    settings = Settings.from_environment()
    assert settings.agent_live_intake_enabled is True
    assert settings.agent_live_intake_source_host == "agent.internal"
    assert settings.agent_live_intake_credential_file == Path("/run/secrets/intake")
    assert settings.agent_live_intake_endpoint_fingerprint == "b" * 64
    monkeypatch.setenv("ATLAS_AGENT_LIVE_INTAKE_ENABLED", "sometimes")
    with pytest.raises(ValueError, match="false, true"):
        Settings.from_environment()
