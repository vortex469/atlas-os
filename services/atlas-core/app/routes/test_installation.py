from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.installation_assessment.cache import EphemeralAssessmentRetryCache
from app.installation_plan.assembly import default_installation_plan_dependency
from app.installation_targets.contract import InstallationDestinationSelectionV1
from app.installation_targets.resolver import (
    CurrentDestinationIdentity,
    DestinationResolutionError,
)
from app.installation_targets.store import SelectionNotFoundError
from app.operator_auth.audit import OperatorSecurityAuditStore
from app.operator_auth.models import (
    INSTALLATION_DESTINATION_SELECT,
    OPERATIONAL_INTENT_CREATE,
    PROVIDER_INTENT_UPDATE,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.installation import (
    MAX_INSTALLATION_BODY_BYTES,
    AdmissionAssessmentRequest,
    DestinationSelectionRequest,
    router,
)
from app.testing import ASGITestClient

ORIGIN = "https://atlas.test"
NOW = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
PLAN_FP = "34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a"
DEST_FP = "a" * 64
REPLACED_FP = "d" * 64
URL = "/installation/admission-assessments"


def selection(**updates: object) -> InstallationDestinationSelectionV1:
    values = {
        "selection_id": "00000000-0000-4000-8000-000000000001",
        "resource_id": "110",
        "selected_destination_fingerprint": DEST_FP,
        "selected_at": "2026-08-27T11:00:00Z",
        "expires_at": "2026-08-28T11:00:00Z",
        "selected_by": "operator-a",
        "request_digest": "b" * 64,
        "selection_fingerprint": "c" * 64,
        "status": "active",
        "terminated_at": None,
    }
    values.update(updates)
    return InstallationDestinationSelectionV1.model_validate(values)


class FakeSelectionService:
    def __init__(self) -> None:
        self.record = selection()
        self.current = CurrentDestinationIdentity(True, True, DEST_FP)
        self.observed_resource_ids: list[str] = []

    def get_for_assessment(
        self, *, selection_id: str, selected_by: str
    ) -> InstallationDestinationSelectionV1:
        if selection_id != self.record.selection_id or selected_by != self.record.selected_by:
            raise SelectionNotFoundError("private detail")
        return self.record

    async def observe_current_identity(
        self, resource_id: str
    ) -> CurrentDestinationIdentity:
        self.observed_resource_ids.append(resource_id)
        return self.current


class FailingObservationService(FakeSelectionService):
    async def observe_current_identity(
        self, resource_id: str
    ) -> CurrentDestinationIdentity:
        del resource_id
        raise DestinationResolutionError("sanitized dependency failure")


async def _empty_destinations() -> tuple[()]:
    return ()


def app_client(
    tmp_path: Path,
    *,
    operator_id: str = "operator-a",
    permissions: tuple[str, ...] = (INSTALLATION_DESTINATION_SELECT,),
) -> tuple[ASGITestClient, FastAPI, str, str, FakeSelectionService]:
    application = FastAPI()
    application.include_router(router)
    application.state.operator_auth_enabled = True
    application.state.operator_auth_trusted_origins = frozenset({ORIGIN})
    sessions = OperatorSessionStore(tmp_path / "sessions.db", 3600)
    application.state.operator_session_store = sessions
    application.state.operator_security_audit = OperatorSecurityAuditStore(
        tmp_path / "audit.db"
    )
    application.state.operator_mutation_rate_limiter = OperatorRateLimiter(100, 60)
    created = sessions.create(
        OperatorCredential(
            operator_id=operator_id,
            password_hash="unused-test-hash",
            permissions=permissions,
        )
    )
    service = FakeSelectionService()
    application.state.installation_destination_selection_service = service
    application.state.installation_destination_enumerator = _empty_destinations
    application.state.installation_assessment_retry_cache = EphemeralAssessmentRetryCache()
    application.state.installation_assessment_clock = lambda: NOW
    application.state.installation_plan_read_dependency = default_installation_plan_dependency(
        repository_root=Path("/opt/atlas"),
        clock=lambda: datetime(2026, 8, 25, tzinfo=UTC),
    )
    return ASGITestClient(application), application, created.session_token, created.csrf_token, service


def request_body(**updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "item_id": "home-assistant",
        "catalog_entry_id": "d5-home-assistant",
        "plan_fingerprint": PLAN_FP,
        "selection_id": "00000000-0000-4000-8000-000000000001",
    }
    values.update(updates)
    return values


def mutation_headers(csrf: str, key: str = "0123456789abcdef") -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": csrf,
        "Idempotency-Key": key,
    }


def post(client: ASGITestClient, token: str, csrf: str, *, key: str = "0123456789abcdef"):
    return client.post(
        URL,
        cookies={"atlas_operator_session": token},
        headers=mutation_headers(csrf, key),
        json=request_body(),
    )


def test_requests_are_closed_bounded_and_use_exact_plan_id_domain() -> None:
    assert MAX_INSTALLATION_BODY_BYTES == 8_192
    with pytest.raises(ValidationError):
        DestinationSelectionRequest(resource_id="../110", enumeration_token="a" * 64)
    with pytest.raises(ValidationError):
        DestinationSelectionRequest(resource_id="110", enumeration_token="a" * 64, provider={})
    with pytest.raises(ValidationError):
        AdmissionAssessmentRequest(**request_body(), command="install")
    for opaque_id in ("127.0.0.1", "atlas.internal", "a:b_c.d-0"):
        parsed = AdmissionAssessmentRequest(
            **request_body(item_id=opaque_id, catalog_entry_id=opaque_id)
        )
        assert (parsed.item_id, parsed.catalog_entry_id) == (opaque_id, opaque_id)


def test_permission_is_narrow_and_shared_for_read_and_select() -> None:
    credential = OperatorCredential(
        operator_id="installation-operator",
        password_hash="unused",
        permissions=(INSTALLATION_DESTINATION_SELECT,),
    )
    assert credential.permissions == (INSTALLATION_DESTINATION_SELECT,)
    assert OPERATIONAL_INTENT_CREATE not in credential.permissions
    assert PROVIDER_INTENT_UPDATE not in credential.permissions


def test_live_matching_identity_and_home_assistant_golden(tmp_path: Path) -> None:
    client, _app, token, csrf, service = app_client(tmp_path)
    response = post(client, token, csrf)

    assert response.status_code == 200
    body = response.json()
    assert service.observed_resource_ids == ["110"]
    assert body["plan_fingerprint"] == PLAN_FP
    assert body["current_destination_fingerprint"] == DEST_FP
    assert body["reason_codes"] == [
        "installation_plan_missing_deployment_artifact",
        "destination_installation_capability_unknown",
        "agent_install_container_unsupported",
    ]
    assert body["assessment_status"] == "blocked"
    assert body["candidate_eligibility_evaluated"] is False


@pytest.mark.parametrize(
    "current,reason,current_fingerprint",
    [
        (CurrentDestinationIdentity(True, True, REPLACED_FP), "destination_replaced_or_moved", REPLACED_FP),
        (CurrentDestinationIdentity(True, False, None), "destination_identity_unavailable", None),
        (CurrentDestinationIdentity(False, False, None), "destination_unavailable", None),
    ],
)
def test_live_destination_facts_are_independent_of_stored_selection(
    tmp_path: Path,
    current: CurrentDestinationIdentity,
    reason: str,
    current_fingerprint: str | None,
) -> None:
    client, _app, token, csrf, service = app_client(tmp_path)
    service.current = current
    response = post(client, token, csrf)

    assert response.status_code == 200
    body = response.json()
    assert body["current_destination_fingerprint"] == current_fingerprint
    assert reason in body["reason_codes"]
    if current_fingerprint is None:
        assert body["current_destination_fingerprint"] != DEST_FP


def test_provider_observation_failure_is_sanitized_503(tmp_path: Path) -> None:
    client, app, token, csrf, _service = app_client(tmp_path)
    app.state.installation_destination_selection_service = FailingObservationService()
    response = post(client, token, csrf)

    assert response.status_code == 503
    assert response.json()["detail"] == "Installation dependency is unavailable."
    assert "sanitized dependency failure" not in response.text


@pytest.mark.parametrize("status", ["cancelled", "expired", "stale"])
def test_selection_terminal_states_remain_assessment_facts(tmp_path: Path, status: str) -> None:
    client, _app, token, csrf, service = app_client(tmp_path)
    service.record = selection(status=status, terminated_at="2026-08-27T12:00:00Z")
    response = post(client, token, csrf)

    assert response.status_code == 200
    reasons = response.json()["reason_codes"]
    if status == "expired":
        assert "destination_selection_expired" in reasons
    elif status == "stale":
        assert "destination_replaced_or_moved" in reasons
    else:
        assert "destination_unavailable" in reasons


def test_idempotency_replay_and_live_fact_conflict(tmp_path: Path) -> None:
    client, _app, token, csrf, service = app_client(tmp_path)
    first = post(client, token, csrf)
    replay = post(client, token, csrf)
    assert first.status_code == replay.status_code == 200
    assert first.content == replay.content

    service.current = CurrentDestinationIdentity(True, True, REPLACED_FP)
    conflict = post(client, token, csrf)
    assert conflict.status_code == 409
    assert "private" not in conflict.text


def test_cross_operator_selection_is_indistinguishable_404(tmp_path: Path) -> None:
    client, _app, token, csrf, _service = app_client(tmp_path, operator_id="operator-b")
    response = post(client, token, csrf)
    assert response.status_code == 404
    assert response.json()["detail"] == "Installation selection was not found."


def test_auth_get_and_mutation_security_semantics(tmp_path: Path) -> None:
    client, _app, token, csrf, _service = app_client(tmp_path / "allowed")
    assert client.get("/installation/destinations").status_code == 401
    assert client.get(
        "/installation/destinations", cookies={"atlas_operator_session": token}
    ).status_code == 200
    assert client.post(URL, json=request_body()).status_code == 403
    assert client.post(
        URL,
        cookies={"atlas_operator_session": token},
        headers={**mutation_headers(csrf), "Origin": "https://evil.test"},
        json=request_body(),
    ).status_code == 403
    assert client.post(
        URL,
        cookies={"atlas_operator_session": token},
        headers={**mutation_headers(csrf), "X-Atlas-CSRF-Token": "wrong"},
        json=request_body(),
    ).status_code == 403

    denied, _app, denied_token, denied_csrf, _service = app_client(
        tmp_path / "denied", permissions=()
    )
    assert post(denied, denied_token, denied_csrf).status_code == 403


@pytest.mark.parametrize(
    "content",
    [
        b'{"item_id":"home-assistant","item_id":"other"}',
        b'{"item_id":',
        b'{"item_id":"\xff"}',
        b'{"a":{"b":{"c":{"d":{"e":1}}}}}',
        (b"[" * 1_500) + b"0" + (b"]" * 1_500),
    ],
)
def test_hostile_json_is_sanitized_without_internal_error(tmp_path: Path, content: bytes) -> None:
    client, _app, token, csrf, _service = app_client(tmp_path)
    response = client.post(
        URL,
        cookies={"atlas_operator_session": token},
        headers=mutation_headers(csrf),
        content=content,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Installation request is invalid."


def test_oversized_json_is_413(tmp_path: Path) -> None:
    client, _app, token, csrf, _service = app_client(tmp_path)
    response = client.post(
        URL,
        cookies={"atlas_operator_session": token},
        headers=mutation_headers(csrf),
        content=b" " * (MAX_INSTALLATION_BODY_BYTES + 1),
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Installation request is too large."


def test_route_surface_and_authority_isolation() -> None:
    methods = {(route.path, tuple(sorted(route.methods))) for route in router.routes}
    assert methods == {
        ("/installation/destinations", ("GET",)),
        ("/installation/destination-selections", ("POST",)),
        ("/installation/destination-selections/{selection_id}", ("GET",)),
        ("/installation/destination-selections/{selection_id}", ("DELETE",)),
        (
            "/installation/destination-selections/{selection_id}",
            ("HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"),
        ),
        ("/installation/admission-assessments", ("POST",)),
    }
    source = Path(__file__).with_name("installation.py").read_text(encoding="utf-8")
    imports = {
        alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = (
        "execution_candidates",
        "candidate_planning",
        "atlas_agent",
        "workflow",
        "approval",
        "operational_dispatch",
        "worker",
        "provider_intents",
        "repository_execution",
    )
    assert not any(term in imported for imported in imports for term in forbidden)
    assert "assess_installation_request" in source
    assert "assess_installation_admission" not in source


@pytest.mark.parametrize(
    ("path", "supported", "unsupported"),
    [
        ("/installation/destinations", {"GET"}, "POST"),
        ("/installation/destination-selections", {"POST"}, "PUT"),
        (
            "/installation/destination-selections/00000000-0000-4000-8000-000000000001",
            {"DELETE", "GET"},
            "PUT",
        ),
        ("/installation/admission-assessments", {"POST"}, "PUT"),
    ],
)
def test_live_unsupported_methods_have_precise_allow(
    tmp_path: Path, path: str, supported: set[str], unsupported: str
) -> None:
    client, _app, _token, _csrf, _service = app_client(tmp_path)
    response = client.request(unsupported, path)

    assert response.status_code == 405
    assert {method.strip() for method in response.headers["allow"].split(",")} == supported
