from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI

from app.installation_readiness_review.contract import (
    InstallationReadinessEvidenceSummaryV1,
    InstallationReadinessReviewEvidenceV1,
)
from app.installation_readiness_review.service import InstallationReadinessReviewService
from app.installation_readiness_review.test_contract import (
    OPERATOR,
    _input,
    _linkage,
    _summaries,
)
from app.operator_auth.models import INSTALLATION_DESTINATION_SELECT, OperatorCredential
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.installation_readiness_review import router
from app.testing import ASGITestClient

URL = "/api/v1/installation/candidate-records/{}/readiness-review"


@dataclass
class Reader:
    evidence: InstallationReadinessReviewEvidenceV1 | None
    calls: int = 0

    def read_owned(self, *, operator_id, candidate_record_id, observed_at):
        self.calls += 1
        return self.evidence


def _application(tmp_path: Path, evidence=None):
    exact = evidence or _input(tmp_path)
    reader = Reader(exact)
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.state.operator_auth_enabled = True
    sessions = OperatorSessionStore(tmp_path / "sessions.db", 3600)
    allowed = sessions.create(
        OperatorCredential(
            operator_id=OPERATOR,
            password_hash="unused",
            permissions=(INSTALLATION_DESTINATION_SELECT,),
        )
    )
    denied = sessions.create(
        OperatorCredential(
            operator_id="operator-denied",
            password_hash="unused",
            permissions=(),
        )
    )
    foreign = sessions.create(
        OperatorCredential(
            operator_id="operator-foreign",
            password_hash="unused",
            permissions=(INSTALLATION_DESTINATION_SELECT,),
        )
    )
    application.state.operator_session_store = sessions
    application.state.installation_readiness_review_service = (
        InstallationReadinessReviewService(
            evidence_reader=reader,
            clock=lambda: datetime(2026, 8, 27, 12, 0, 16, tzinfo=UTC),
        )
    )
    return ASGITestClient(application), application, reader, allowed, denied, foreign, exact


def _cookies(session) -> dict[str, str]:
    return {"atlas_operator_session": session.session_token}


def _url(evidence) -> str:
    return URL.format(evidence.candidate_record_id)


def test_auth_permission_owner_isolation_and_redacted_errors(tmp_path: Path) -> None:
    client, _, reader, allowed, denied, foreign, evidence = _application(tmp_path)
    anonymous = client.get(_url(evidence))
    forbidden = client.get(_url(evidence), cookies=_cookies(denied))
    concealed = client.get(_url(evidence), cookies=_cookies(foreign))

    assert anonymous.status_code == 401
    assert forbidden.status_code == 403
    assert concealed.status_code == 404
    assert reader.calls == 1
    for response, code in (
        (anonymous, "unauthenticated"),
        (forbidden, "unauthorized"),
        (concealed, "not_found"),
    ):
        assert response.json() == {
            "schema": "installation-readiness-review-error-v1",
            "error_code": code,
            "safe_message": "Installation readiness review is unavailable.",
            "correlation_id": "unknown",
            "redacted": True,
            "retryable": False,
            "execution_authorized": False,
            "installation_allowed": False,
            "mutation_allowed": False,
        }
        assert evidence.candidate_record_id not in response.text
    assert client.get(_url(evidence), cookies=_cookies(allowed)).status_code == 200


def test_success_readiness_gated_and_fixed_authority(tmp_path: Path) -> None:
    client, _, reader, allowed, _, _, evidence = _application(tmp_path)
    first = client.get(_url(evidence), cookies=_cookies(allowed))
    second = client.get(_url(evidence), cookies=_cookies(allowed))
    assert first.status_code == 200 and first.json() == second.json()
    review = first.json()["review"]
    assert review["readiness"] == "readiness_gated"
    assert review["blockers"] == ["execution_admission_not_defined"]
    assert len(review["evidence"]) == 14
    assert review["read_only"] and review["evidence_only"]
    for field in (
        "execution_admission_granted", "execution_authorized",
        "installation_allowed", "dispatch_allowed", "worker_allowed",
        "workflow_allowed", "deployment_allowed", "mutation_allowed",
        "retry_allowed", "replay_allowed",
    ):
        assert review[field] is False
    assert reader.calls == 2


def test_blocked_missing_stale_and_home_assistant_states(tmp_path: Path) -> None:
    linkage = _linkage(tmp_path)
    summaries = list(_summaries(linkage))
    summaries[4] = InstallationReadinessEvidenceSummaryV1(
        release="v0.24",
        evidence_kind="dispatch_handoff",
        evidence_id=None,
        evidence_fingerprint=None,
        evidence_state="missing",
        valid_until=None,
    )
    missing = _input(tmp_path / "missing", summaries=tuple(summaries), linkage=None)
    client, app, _, allowed, _, _, _ = _application(tmp_path / "app", missing)
    response = client.get(_url(missing), cookies=_cookies(allowed))
    assert response.status_code == 200
    assert response.json()["review"]["blockers"] == ["missing_evidence"]

    stale = _input(tmp_path / "stale", blockers=("stale_evidence",))
    app.state.installation_readiness_review_service._reader.evidence = stale
    response = client.get(_url(stale), cookies=_cookies(allowed))
    assert response.json()["review"]["blockers"] == ["stale_evidence"]

    home_assistant = _input(
        tmp_path / "ha",
        home_assistant=True,
        installation_capability_supported=False,
    )
    app.state.installation_readiness_review_service._reader.evidence = home_assistant
    response = client.get(_url(home_assistant), cookies=_cookies(allowed))
    assert response.json()["review"]["readiness"] == "blocked"
    assert response.json()["review"]["blockers"] == [
        "installation_capability_unsupported"
    ]


def test_mismatched_evidence_and_reader_failure_are_sanitized(tmp_path: Path) -> None:
    client, app, reader, allowed, _, _, evidence = _application(tmp_path)
    raw = evidence.model_dump(mode="python")
    raw["evidence"][0]["evidence_fingerprint"] = None
    reader.evidence = InstallationReadinessReviewEvidenceV1.model_construct(**raw)
    response = client.get(_url(evidence), cookies=_cookies(allowed))
    assert response.status_code == 503
    assert response.json()["error_code"] == "unavailable"
    assert "fingerprint" not in response.text

    class ExplodingService:
        def review(self, **kwargs):
            raise RuntimeError("super-secret-token")

    app.state.installation_readiness_review_service = ExplodingService()
    response = client.get(_url(evidence), cookies=_cookies(allowed))
    assert response.status_code == 503
    assert "super-secret-token" not in response.text


def test_no_body_query_csrf_or_mutation_semantics(tmp_path: Path) -> None:
    client, _, reader, allowed, _, _, evidence = _application(tmp_path)
    cookies = _cookies(allowed)
    assert client.get(_url(evidence), cookies=cookies).status_code == 200
    assert client.get(
        _url(evidence), cookies=cookies, headers={"X-Atlas-CSRF-Token": "invalid"}
    ).status_code == 200
    assert client.get(_url(evidence) + "?refresh=true", cookies=cookies).status_code == 422
    malformed = client.get(
        "/api/v1/installation/candidate-records/NOT-A-UUID/readiness-review",
        cookies=cookies,
    )
    assert malformed.status_code == 422
    assert malformed.json()["error_code"] == "malformed"
    assert client.request(
        "GET", _url(evidence), cookies=cookies, content=b"{}"
    ).status_code == 422
    assert reader.calls == 2
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = client.request(method, _url(evidence), cookies=cookies)
        assert response.status_code == 405
        assert response.headers["allow"] == "GET"


def test_openapi_is_exact_single_get_without_body_query_or_action_siblings() -> None:
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    document = application.openapi()
    path = "/api/v1/installation/candidate-records/{candidate_record_id}/readiness-review"
    assert set(document["paths"]) == {path}
    assert set(document["paths"][path]) == {"get"}
    operation = document["paths"][path]["get"]
    assert "requestBody" not in operation
    assert [(item["name"], item["in"], item["required"]) for item in operation["parameters"]] == [
        ("candidate_record_id", "path", True)
    ]
    assert operation["parameters"][0]["schema"]["pattern"] == (
        "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    )
    assert set(operation["responses"]) == {"200", "401", "403", "404", "422", "503"}
