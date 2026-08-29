"""V0.32 P5 release-wide authority, no-replay, and isolation locks."""

from __future__ import annotations

import ast
import inspect
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from app.agent_live_intake_admission.contract import (
    INTAKE_PATH,
    AgentLiveIntakeAcknowledgementV1,
    AgentLiveIntakeAdmissionV1,
    AgentLiveIntakeAuditEvidenceV1,
    AgentLiveIntakeReceiptV1,
)
from app.agent_live_intake_admission.route import create_agent_live_intake_router
from app.agent_live_intake_admission.service import AgentLiveIntakeAdmissionService
from app.agent_live_intake_admission.store import AgentLiveIntakeAdmissionStore
from fastapi import FastAPI

from .test_contract import OPERATOR, envelope
from .test_route import Authenticator
from .test_service_store import NOW, Reader, authentication

AGENT_ROOT = Path(__file__).parents[2]
APP_ROOT = AGENT_ROOT / "app"
PACKAGE_ROOT = APP_ROOT / "agent_live_intake_admission"
REPOSITORY_ROOT = AGENT_ROOT.parents[1]


def closure(tmp_path: Path):
    env = envelope()
    store = AgentLiveIntakeAdmissionStore(
        tmp_path / "closure.sqlite3",
        clock=lambda: NOW,
        id_factory=uuid.uuid4,
    )
    service = AgentLiveIntakeAdmissionService(
        store=store,
        evidence_reader=Reader(),
        expected_source=authentication().source,
        endpoint_fingerprint=env.endpoint_fingerprint,
        enabled=True,
    )
    return service, store, env


def submit(service, env, *, key: str = "release-once", correlation: str = "closure-1"):
    return service.admit(
        env,
        authentication=authentication(),
        idempotency_key=key,
        correlation_id=correlation,
    )


def test_default_off_exact_route_and_fixed_false_authority(tmp_path: Path) -> None:
    _, store, env = closure(tmp_path)
    disabled = AgentLiveIntakeAdmissionService(
        store=store,
        evidence_reader=Reader(),
        expected_source=authentication().source,
        endpoint_fingerprint=env.endpoint_fingerprint,
    )
    assert inspect.signature(AgentLiveIntakeAdmissionService).parameters[
        "enabled"
    ].default is False
    assert submit(disabled, env).reason_code == "unavailable"

    application = FastAPI(docs_url=None, redoc_url=None)
    application.include_router(
        create_agent_live_intake_router(
            service=disabled,
            authenticator=Authenticator(),
            expected_source=authentication().source,
            correlation_id_factory=lambda: "closure-route-1",
        )
    )
    assert {path: set(methods) for path, methods in application.openapi()["paths"].items()} == {
        INTAKE_PATH: {"post"}
    }
    main_source = (APP_ROOT / "main.py").read_text(encoding="utf-8")
    assert "if settings.agent_live_intake_enabled:" in main_source
    assert 'agent_live_intake_enabled: bool = False' in (
        APP_ROOT / "config" / "settings.py"
    ).read_text(encoding="utf-8")

    for model in (
        AgentLiveIntakeAdmissionV1,
        AgentLiveIntakeAcknowledgementV1,
        AgentLiveIntakeReceiptV1,
        AgentLiveIntakeAuditEvidenceV1,
    ):
        for field in (
            "execution_admission_granted",
            "execution_authorized",
            "installation_allowed",
            "worker_allowed",
            "workflow_allowed",
            "deployment_allowed",
            "mutation_allowed",
            "replay_allowed",
        ):
            assert model.model_fields[field].annotation == Literal[False]


def test_concurrent_one_envelope_admits_once_and_reservation_is_permanent(
    tmp_path: Path,
) -> None:
    service, store, env = closure(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(
            executor.map(
                lambda correlation: submit(
                    service, env, correlation=correlation
                ),
                ("concurrent-1", "concurrent-2"),
            )
        )
    assert outcomes[0] == outcomes[1]
    assert outcomes[0].outcome == "admitted_for_evidence_only"
    with sqlite3.connect(store.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM agent_live_intake_reservations"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM agent_live_intake_admissions"
        ).fetchone()[0] == 1
        connection.execute("DELETE FROM agent_live_intake_admissions")
    assert submit(service, env).reason_code == "unavailable"
    with sqlite3.connect(store.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM agent_live_intake_reservations"
        ).fetchone()[0] == 1


def test_append_only_evidence_is_restart_safe_secret_free_and_redacted(
    tmp_path: Path, caplog
) -> None:
    service, store, env = closure(tmp_path)
    result = submit(service, env)
    assert result.admission is not None
    restarted = AgentLiveIntakeAdmissionStore(store.database_path, clock=lambda: NOW)
    record = restarted.get(
        operator_id=OPERATOR, admission_id=result.admission.admission_id
    )
    assert record.admission == result.admission
    assert restarted.get_audit(
        operator_id=OPERATOR, admission_id=result.admission.admission_id
    ).admission_fingerprint == result.admission.admission_fingerprint

    persisted = b"".join(
        path.read_bytes()
        for path in tmp_path.glob("closure.sqlite3*")
        if path.is_file()
    )
    for secret in (
        b"dedicated-live-intake-token",
        b"Bearer ",
        b"Authorization",
        b"super-secret",
    ):
        assert secret not in persisted
    store_source = (PACKAGE_ROOT / "store.py").read_text(encoding="utf-8")
    assert "UPDATE agent_live_intake_admissions" not in store_source
    assert "DELETE FROM agent_live_intake_admissions" not in store_source

    failed = AgentLiveIntakeAdmissionService(
        store=AgentLiveIntakeAdmissionStore(tmp_path / "failed.sqlite3", clock=lambda: NOW),
        evidence_reader=Reader(fail=True),
        expected_source=authentication().source,
        endpoint_fingerprint=env.endpoint_fingerprint,
        enabled=True,
    )
    rejected = submit(failed, env)
    serialized = rejected.model_dump_json()
    assert rejected.reason_code == "unavailable"
    assert "secret" not in serialized and "/provider/path" not in serialized
    assert "secret" not in caplog.text and "/provider/path" not in caplog.text


def test_no_admission_evidence_authority_consumer_or_forbidden_dependency() -> None:
    authority_roots = (
        APP_ROOT / "approval",
        APP_ROOT / "candidate_planning",
        APP_ROOT / "container",
        APP_ROOT / "execution",
        APP_ROOT / "model_providers",
        APP_ROOT / "repository",
        APP_ROOT / "routes",
        APP_ROOT / "workflow",
    )
    markers = (
        "agent_live_intake_admission",
        "AgentLiveIntakeAdmissionV1",
        "AgentLiveIntakeAcknowledgementV1",
        "AgentLiveIntakeReceiptV1",
        "agent-live-intake-admission-v1",
    )
    violations = [
        f"{path.relative_to(APP_ROOT)} -> {marker}"
        for root in authority_roots
        for path in root.rglob("*.py")
        for marker in markers
        if marker in path.read_text(encoding="utf-8")
    ]
    assert violations == []

    forbidden_imports = {
        "asyncio", "docker", "httpx", "podman", "requests", "shlex",
        "socket", "subprocess", "urllib",
    }
    forbidden_calls = {"exec", "eval", "open", "system", "run", "Popen"}
    for path in PACKAGE_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert imports.isdisjoint(forbidden_imports)
        assert calls.isdisjoint(forbidden_calls)


def test_capability_parity_and_home_assistant_remain_blocked_without_artifact() -> None:
    candidate_source = (
        APP_ROOT / "candidate_planning" / "models.py"
    ).read_text(encoding="utf-8")
    assert 'SUPPORTED_EXECUTION_INTENTS = frozenset({"update-compose-stack"})' in candidate_source
    assert 'OPERATIONAL_EXECUTION_INTENTS = frozenset({"restart-service"})' in candidate_source
    assert "install-container" not in candidate_source
    artifacts = [
        path.relative_to(REPOSITORY_ROOT)
        for root in (REPOSITORY_ROOT / "compose", REPOSITORY_ROOT / "deploy")
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
        and "home-assistant" in path.name.lower()
        and path.suffix.lower() in {".yaml", ".yml", ".json", ".toml"}
    ]
    assert artifacts == []
