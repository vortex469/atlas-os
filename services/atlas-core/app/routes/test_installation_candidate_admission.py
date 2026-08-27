"""P3 transport contract for installation candidate admissions."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI

from app.installation_candidate_admission.assembly import (
    InstallationCandidateAdmissionInputMissing,
    InstallationCandidateAdmissionInputUnavailable,
)
from app.installation_candidate_admission.test_admission import admit
from app.installation_capability.test_assessment import assess, plan
from app.operator_auth.models import INSTALLATION_DESTINATION_SELECT, OperatorCredential
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.installation_candidate_admission import router
from app.testing import ASGITestClient

SELECTION_ID = "00000000-0000-4000-8000-000000000001"
URL = f"/api/v1/installation/candidate-admissions/example/{SELECTION_ID}"


@dataclass
class _ReadDependency:
    value: object
    error: Exception | None = None
    request: tuple[str, str, str] | None = None

    async def assemble(self, *, item_id: str, selection_id: str, principal_id: str):
        self.request = (item_id, selection_id, principal_id)
        if self.error is not None:
            raise self.error
        return self.value


def _application(tmp_path: Path, value=None):
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
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
    dependency = _ReadDependency(value or admit())
    application.state.installation_candidate_admission_read_dependency = dependency
    return ASGITestClient(application), created.session_token, application, dependency


def test_auth_get_only_openapi_and_no_mutation_sibling(tmp_path: Path) -> None:
    client, token, application, _ = _application(tmp_path)
    assert client.get(URL).status_code == 401
    assert client.get(URL, cookies={"atlas_operator_session": token}).status_code == 200
    for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"):
        response = client.request(
            method, URL, cookies={"atlas_operator_session": token}
        )
        assert response.status_code == 405
        assert response.headers["allow"] == "GET"

    paths = {
        path: set(methods) for path, methods in application.openapi()["paths"].items()
    }
    assert paths == {
        "/api/v1/installation/candidate-admissions/{item_id}/{selection_id}": {
            "get"
        }
    }
    prohibited = {"install", "approve", "execute", "dispatch", "workflow"}
    assert not any(
        segment in prohibited
        for path in paths
        for segment in path.removeprefix("/api/v1/installation/").split("/")
    )


def test_success_is_closed_redacted_and_non_authorizing(tmp_path: Path) -> None:
    client, token, _, dependency = _application(tmp_path)
    response = client.get(URL, cookies={"atlas_operator_session": token})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "schema",
        "plan_fingerprint",
        "selection_fingerprint",
        "selected_destination_fingerprint",
        "current_destination_fingerprint",
        "capability_assessment_fingerprint",
        "provider_fact_set_fingerprint",
        "evaluated_at",
        "status",
        "reason_codes",
        "candidate_record",
        "approved",
        "executable",
        "deployable",
        "dispatchable",
        "agent_execution_supported",
        "candidate_creation_allowed",
        "admission_fingerprint",
    }
    assert body["status"] == "admitted_but_non_executable"
    assert body["candidate_record"] is not None
    assert not any(
        body[name]
        for name in (
            "approved",
            "executable",
            "deployable",
            "dispatchable",
            "agent_execution_supported",
            "candidate_creation_allowed",
        )
    )
    assert dependency.request == ("example", SELECTION_ID, "operator-a")
    for secret in ("password", "token", "hostname", "address", "operator-a"):
        assert secret not in response.text


def test_home_assistant_is_not_admitted(tmp_path: Path) -> None:
    home = plan(ready=False)
    result = admit(plan=home, capability_assessment=assess(home))
    client, token, _, _ = _application(tmp_path, result)
    response = client.get(URL, cookies={"atlas_operator_session": token})
    assert response.status_code == 200
    assert response.json()["status"] == "not_admitted"
    assert response.json()["candidate_record"] is None


def test_missing_unavailable_and_ownership_errors_are_sanitized(tmp_path: Path) -> None:
    client, token, _, dependency = _application(tmp_path)
    dependency.error = InstallationCandidateAdmissionInputMissing("secret owner")
    missing = client.get(URL, cookies={"atlas_operator_session": token})
    assert missing.status_code == 404
    assert missing.json() == {
        "detail": "Installation candidate admission input was not found."
    }
    assert "secret" not in missing.text

    dependency.error = InstallationCandidateAdmissionInputMissing("missing selection")
    ownership = client.get(URL, cookies={"atlas_operator_session": token})
    assert ownership.status_code == missing.status_code
    assert ownership.json() == missing.json()

    dependency.error = InstallationCandidateAdmissionInputUnavailable(
        "https://root:secret@private.invalid/raw"
    )
    unavailable = client.get(URL, cookies={"atlas_operator_session": token})
    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "detail": "Installation candidate admission input is unavailable."
    }
    assert "secret" not in unavailable.text


def test_server_owned_inputs_and_route_authority_isolation(tmp_path: Path) -> None:
    client, token, _, _ = _application(tmp_path)
    cookies = {"atlas_operator_session": token}
    assert client.get(f"{URL}?approved=true", cookies=cookies).status_code == 422
    assert client.request("GET", URL, content=b"{}", cookies=cookies).status_code == 422

    path = Path(__file__).with_name("installation_candidate_admission.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(
        term in imported
        for imported in imports
        for term in (
            "execution_candidates",
            "operational_dispatch",
            "provider_intents",
            "workflow",
            "repository",
        )
    )
    calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    assert not calls & {
        "create",
        "approve",
        "execute",
        "dispatch",
        "write",
        "commit",
        "add",
        "delete",
        "update",
    }
