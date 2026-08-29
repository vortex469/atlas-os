"""P5 release-wide authority, no-replay, and production-isolation locks."""

from __future__ import annotations

import ast
import inspect
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pytest
from app.real_agent_intake_boundary import (
    INTAKE_PATH,
    AgentInstallationIntakeAdmissionV1,
    AgentInstallationIntakeAuditEvidenceV1,
    AgentInstallationIntakeAuthenticationContextV1,
    AgentInstallationIntakeRequestV1,
    AgentRealIntakeEvidenceService,
    AgentRealIntakeEvidenceStore,
    create_dormant_real_intake_router,
)
from app.real_agent_intake_boundary.store import RealIntakeStoreError
from fastapi import FastAPI
from tests.real_agent_intake_boundary.test_dormant_real_intake_route import (
    Authenticator,
)
from tests.real_agent_intake_boundary.test_real_agent_intake_models import (
    OPERATOR,
    request_dict,
)
from tests.real_agent_intake_boundary.test_real_agent_intake_service import (
    EvidenceReader,
)

AGENT_ROOT = Path(__file__).parents[2]
APP_ROOT = AGENT_ROOT / "app"
PACKAGE_ROOT = APP_ROOT / "real_agent_intake_boundary"
REPOSITORY_ROOT = AGENT_ROOT.parents[1]


def clock() -> datetime:
    return datetime(2026, 8, 29, 12, 0, 25, tzinfo=UTC)


def values(tmp_path: Path):
    reader = EvidenceReader()
    store = AgentRealIntakeEvidenceStore(
        tmp_path / "closure.sqlite3",
        clock=clock,
        id_factory=lambda: uuid.UUID("00000000-0000-4000-8000-000000000703"),
    )
    service = AgentRealIntakeEvidenceService(
        store=store, evidence_reader=reader, enabled=True
    )
    request = AgentInstallationIntakeRequestV1.model_validate(request_dict())
    authentication = AgentInstallationIntakeAuthenticationContextV1()
    return service, store, reader, request, authentication


def preserve(service, request, authentication, key: str = "closure-key"):
    return service.preserve(
        request,
        authentication=authentication,
        idempotency_key=key,
        correlation_id="release-closure-1",
    )


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_exact_concurrent_retry_preserves_one_byte_identical_admission(
    tmp_path: Path,
) -> None:
    service, store, _, request, authentication = values(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                lambda _: preserve(service, request, authentication),
                range(2),
            )
        )
    assert results[0] == results[1]
    assert results[0].admission is not None
    with sqlite3.connect(store.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM agent_real_intake_admissions"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM agent_real_intake_idempotency"
        ).fetchone()[0] == 1


def test_expired_exact_retry_never_revalidates_or_releases_reservation(
    tmp_path: Path,
) -> None:
    service, store, reader, request, authentication = values(tmp_path)
    first = preserve(service, request, authentication)
    assert first.admission is not None
    store._clock = lambda: datetime(2026, 8, 29, 12, 2, 0, tzinfo=UTC)
    reader.resolve = lambda **_: (_ for _ in ()).throw(AssertionError("no reread"))  # type: ignore[method-assign]
    second = preserve(service, request, authentication)
    assert second == first
    assert store.lifecycle(operator_id=OPERATOR, admission_id=first.admission.admission_id) == "expired"


def test_incomplete_reservation_and_corruption_fail_closed_without_replay(
    tmp_path: Path,
) -> None:
    service, store, _, request, authentication = values(tmp_path)
    first = preserve(service, request, authentication)
    assert first.admission is not None
    with sqlite3.connect(store.database_path) as connection:
        connection.execute("DELETE FROM agent_real_intake_admissions")
    retry = preserve(service, request, authentication)
    assert retry.outcome == "rejected"
    assert retry.reason_code == "unavailable"
    assert retry.admission is None
    with sqlite3.connect(store.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM agent_real_intake_idempotency"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM agent_real_intake_admissions"
        ).fetchone()[0] == 0


def test_owned_readback_is_direct_and_foreign_owner_is_indistinguishable(
    tmp_path: Path,
) -> None:
    service, _, _, request, authentication = values(tmp_path)
    admission = preserve(service, request, authentication).admission
    assert admission is not None
    assert service.get(operator_id=OPERATOR, admission_id=admission.admission_id) == admission
    with pytest.raises(RealIntakeStoreError, match="unavailable"):
        service.get(operator_id="operator-b", admission_id=admission.admission_id)
    assert not hasattr(service, "list")
    assert not hasattr(service, "consume")
    assert not hasattr(service, "execute")


def test_factory_and_all_evidence_authority_remain_default_disabled_or_fixed_false() -> None:
    assert inspect.signature(AgentRealIntakeEvidenceService).parameters[
        "enabled"
    ].default is False
    assert inspect.signature(create_dormant_real_intake_router).parameters[
        "enabled"
    ].default is False
    for model, fields in (
        (
            AgentInstallationIntakeAdmissionV1,
            (
                "execution_admission_granted",
                "execution_authorized",
                "worker_allowed",
                "mutation_allowed",
                "replay_allowed",
            ),
        ),
        (
            AgentInstallationIntakeAuditEvidenceV1,
            (
                "default_enabled",
                "execution_admission_granted",
                "execution_authorized",
                "worker_allowed",
                "mutation_allowed",
                "replay_allowed",
            ),
        ),
    ):
        for field in fields:
            assert model.model_fields[field].annotation == Literal[False]


def test_dormant_factory_has_one_route_and_no_authority_sibling(tmp_path: Path) -> None:
    service, _, _, _, _ = values(tmp_path)
    application = FastAPI()
    application.include_router(
        create_dormant_real_intake_router(
            service=service,
            authenticator=Authenticator(),
            correlation_id_factory=lambda: "release-closure-1",
        )
    )
    paths = application.openapi()["paths"]
    assert {path: set(operations) for path, operations in paths.items()} == {
        INTAKE_PATH: {"post"}
    }
    for prohibited in (
        "run",
        "execute",
        "deploy",
        "dispatch",
        "deliver",
        "start-workflow",
        "runtime",
        "rollback",
    ):
        assert prohibited not in paths


def test_zero_production_registration_or_consumer_dependency() -> None:
    production_files = (
        APP_ROOT / "main.py",
        APP_ROOT / "container" / "application.py",
        APP_ROOT / "config" / "settings.py",
        APP_ROOT / "core_client" / "client.py",
    )
    for path in production_files:
        source = path.read_text(encoding="utf-8")
        assert "real_agent_intake_boundary" not in source
        assert "installation-intake" not in source
        assert "AgentRealIntake" not in source

    forbidden_dependencies = (
        "app.approval",
        "app.candidate_planning",
        "app.container",
        "app.core_client",
        "app.execution",
        "app.model_providers",
        "app.repository",
        "app.routes",
        "app.workflow",
        "asyncio",
        "docker",
        "httpx",
        "podman",
        "requests",
        "shlex",
        "socket",
        "subprocess",
        "urllib",
    )
    violations = [
        f"{path.name} -> {imported}"
        for path in PACKAGE_ROOT.glob("*.py")
        for imported in _imports(path)
        if imported.startswith(forbidden_dependencies)
    ]
    assert violations == []


def test_capability_parity_and_home_assistant_deployment_remain_blocked() -> None:
    candidate_source = (APP_ROOT / "candidate_planning" / "models.py").read_text(
        encoding="utf-8"
    )
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
