"""P3 transport contract for installation capability assessments."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI

from app.installation_plan.assembly import default_installation_plan_dependency
from app.installation_targets.contract import InstallationDestinationSelectionV1
from app.installation_targets.fingerprint import build_destination_fingerprint
from app.installation_targets.store import SelectionNotFoundError
from app.models.resources import (
    ProviderResource,
    ProviderResourceExpectation,
    ProviderResourceIdentity,
)
from app.operator_auth.models import INSTALLATION_DESTINATION_SELECT, OperatorCredential
from app.operator_auth.sessions import OperatorSessionStore
from app.providers.models import ProviderMetadata
from app.routes.installation_capability import router
from app.services.provider_resource_identity import ResolvedOperationalTarget
from app.testing import ASGITestClient

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
SELECTION_ID = "00000000-0000-4000-8000-000000000001"
URL = f"/installation/capability-assessments/home-assistant/{SELECTION_ID}"


def _target() -> ResolvedOperationalTarget:
    return ResolvedOperationalTarget(
        provider=ProviderMetadata(
            id="proxmox", name="private-provider-name", workspace="operations"
        ),
        resource=ProviderResource(
            provider_id="proxmox",
            resource_id="101",
            display_name="secret-hostname",
            resource_type="qemu",
            current_state="running",
            identity=ProviderResourceIdentity(token="raw-vmgenid", token_version="v1"),
            expectation=ProviderResourceExpectation(),
            configured=False,
            metadata={
                "template": False,
                "lock": None,
                "migrating": False,
                "installation_capability": {
                    "cpu_cores": {"state": "observed", "value": 4},
                    "memory_bytes": {"state": "observed", "value": 8 * 1024**3},
                    "disk_capacity_bytes": {
                        "state": "observed",
                        "value": 64 * 1024**3,
                    },
                    "guest_agent_configured": {
                        "state": "observed",
                        "value": False,
                    },
                },
                "token": "provider-secret",
                "address": "10.0.0.1",
            },
        ),
        resource_fingerprint="a" * 64,
    )


def _selection(operator_id: str = "operator-a") -> InstallationDestinationSelectionV1:
    fingerprint = build_destination_fingerprint(
        resource_id="101", operational_fingerprint="a" * 64
    )
    return InstallationDestinationSelectionV1.model_validate(
        {
            "selection_id": SELECTION_ID,
            "resource_id": "101",
            "selected_destination_fingerprint": fingerprint,
            "selected_at": "2026-08-27T11:00:00Z",
            "expires_at": "2026-08-28T11:00:00Z",
            "selected_by": operator_id,
            "request_digest": "b" * 64,
            "selection_fingerprint": "c" * 64,
            "status": "active",
            "terminated_at": None,
        }
    )


class _Selections:
    def __init__(self) -> None:
        self.record = _selection()
        self.requests: list[tuple[str, str]] = []

    def get_for_assessment(
        self, *, selection_id: str, selected_by: str
    ) -> InstallationDestinationSelectionV1:
        self.requests.append((selection_id, selected_by))
        if selection_id != self.record.selection_id or selected_by != self.record.selected_by:
            raise SelectionNotFoundError("must-not-leak")
        return self.record


def _application(tmp_path: Path) -> tuple[ASGITestClient, str, FastAPI, _Selections]:
    application = FastAPI()
    application.include_router(router)
    application.state.operator_auth_enabled = True
    sessions = OperatorSessionStore(tmp_path / "sessions.db", 3600)
    application.state.operator_session_store = sessions
    created = sessions.create(
        OperatorCredential(
            operator_id="operator-a",
            password_hash="unused",
            permissions=(INSTALLATION_DESTINATION_SELECT,),
        )
    )
    selections = _Selections()
    application.state.installation_destination_selection_service = selections
    application.state.installation_plan_read_dependency = (
        default_installation_plan_dependency(
            repository_root=Path("/opt/atlas"),
            clock=lambda: datetime(2026, 8, 25, tzinfo=UTC),
        )
    )
    application.state.installation_capability_clock = lambda: NOW

    async def resolve(provider: str, resource_id: str, resource_type: str):
        assert (provider, resource_id, resource_type) == ("proxmox", "101", "qemu")
        return _target()

    application.state.installation_capability_target_resolver = resolve
    return (
        ASGITestClient(application),
        created.session_token,
        application,
        selections,
    )


def test_auth_get_only_openapi_and_no_mutation_sibling(tmp_path: Path) -> None:
    client, token, application, _ = _application(tmp_path)
    assert client.get(URL).status_code == 401
    response = client.get(URL, cookies={"atlas_operator_session": token})
    assert response.status_code == 200
    for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
        rejected = client.request(
            method,
            URL, cookies={"atlas_operator_session": token}
        )
        assert rejected.status_code == 405
        assert rejected.headers["allow"] == "GET"
    paths = {
        path: set(methods)
        for path, methods in application.openapi()["paths"].items()
    }
    assert paths == {
        "/installation/capability-assessments/{item_id}/{selection_id}": {"get"}
    }
    prohibited = {"install", "approve", "plan", "execute", "dispatch", "candidate"}
    assert not any(
        segment in prohibited
        for path in paths
        for segment in path.removeprefix("/installation/").split("/")
    )


def test_closed_bounded_redacted_home_assistant_assessment(tmp_path: Path) -> None:
    client, token, _, _ = _application(tmp_path)
    response = client.get(URL, cookies={"atlas_operator_session": token})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "schema_version",
        "plan",
        "selection",
        "current_destination",
        "provider_facts",
        "comparisons",
        "assessment_status",
        "reason_codes",
        "evaluated_at",
        "candidate_eligibility_evaluated",
        "candidate_creation_allowed",
        "agent_execution_supported",
        "provider_mutation_allowed",
        "assessment_fingerprint",
    }
    assert len(body["comparisons"]) <= 64
    assert body["assessment_status"] == "blocked"
    assert "installation_plan_blocked" in body["reason_codes"]
    assert body["candidate_eligibility_evaluated"] is False
    assert body["candidate_creation_allowed"] is False
    assert body["agent_execution_supported"] is False
    assert body["provider_mutation_allowed"] is False
    serialized = response.text
    for secret in (
        "secret-hostname",
        "raw-vmgenid",
        "provider-secret",
        "10.0.0.1",
        "private-provider-name",
    ):
        assert secret not in serialized


def test_selection_ownership_and_server_owned_input_validation(tmp_path: Path) -> None:
    client, token, _, selections = _application(tmp_path)
    selections.record = _selection("operator-b")
    response = client.get(URL, cookies={"atlas_operator_session": token})
    assert response.status_code == 404
    assert response.json() == {"detail": "Installation selection was not found."}
    assert selections.requests == [(SELECTION_ID, "operator-a")]
    assert client.get(
        f"{URL}?cpu=999", cookies={"atlas_operator_session": token}
    ).status_code == 422
    assert client.request(
        "GET",
        URL,
        content=b'{"plan":{}}',
        cookies={"atlas_operator_session": token},
    ).status_code == 422


def test_dependency_errors_are_sanitized(tmp_path: Path) -> None:
    client, token, application, _ = _application(tmp_path)

    async def fail(*args: object):
        del args
        raise RuntimeError("https://root:secret@private.invalid/raw")

    application.state.installation_capability_target_resolver = fail
    response = client.get(URL, cookies={"atlas_operator_session": token})
    assert response.status_code == 500
    assert response.json() == {"detail": "An unexpected internal error occurred."}
    assert "secret" not in response.text


def test_route_has_no_authority_imports_or_calls() -> None:
    path = Path(__file__).with_name("installation_capability.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    source = path.read_text(encoding="utf-8")
    forbidden = (
        "approval",
        "candidate",
        "dispatch",
        "execution_worker",
        "provider_intents",
        "repository",
        "workflow",
        "subprocess",
        "paramiko",
        "sqlite3",
    )
    assert not any(value in source for value in forbidden)
    calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    assert not calls & {"open", "write", "execute", "dispatch", "create_candidate"}
