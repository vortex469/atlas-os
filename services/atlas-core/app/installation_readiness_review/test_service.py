from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.installation_readiness_review import service as service_module
from app.installation_readiness_review.contract import (
    InstallationReadinessEvidenceSummaryV1,
    InstallationReadinessReviewEvidenceV1,
    _expected_summary_identities,
)
from app.installation_readiness_review.service import (
    InstallationReadinessReviewService,
)
from app.installation_readiness_review.test_contract import (
    CORRELATION_ID,
    OPERATOR,
    _input,
    _linkage,
    _summaries,
)


@dataclass
class Reader:
    evidence: InstallationReadinessReviewEvidenceV1 | None
    calls: int = 0
    error: Exception | None = None

    def read_owned(self, *, operator_id, candidate_record_id, observed_at):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.evidence


def _service(tmp_path: Path, **evidence_changes):
    evidence = _input(tmp_path, **evidence_changes)
    reader = Reader(evidence)
    service = InstallationReadinessReviewService(
        evidence_reader=reader,
        clock=lambda: datetime(2026, 8, 27, 12, 0, 16, tzinfo=UTC),
    )
    return evidence, reader, service


def _review(service, evidence, *, operator=OPERATOR, permission=True):
    return service.review(
        candidate_record_id=evidence.candidate_record_id,
        authenticated_operator_id=operator,
        read_permission_verified=permission,
        correlation_id=CORRELATION_ID,
    )


def test_readiness_gated_review_is_deterministic_ephemeral_and_non_authorizing(
    tmp_path: Path,
) -> None:
    evidence, reader, service = _service(tmp_path)
    first = _review(service, evidence)
    second = _review(service, evidence)

    assert first == second
    assert first.response is not None
    assert first.response.review.readiness == "readiness_gated"
    assert first.response.review.blockers == ("execution_admission_not_defined",)
    assert reader.calls == 2
    assert first.read_only and first.evidence_only
    assert not first.installation_allowed
    assert not first.execution_authorized
    assert not first.retry_allowed
    assert not first.replay_allowed


def test_missing_expired_and_stale_evidence_are_blocked(tmp_path: Path) -> None:
    linkage = _linkage(tmp_path)
    missing = list(_summaries(linkage))
    missing[5] = InstallationReadinessEvidenceSummaryV1(
        release="v0.25",
        evidence_kind="agent_intake_simulation",
        evidence_id=None,
        evidence_fingerprint=None,
        evidence_state="missing",
        valid_until=None,
    )
    evidence, _, service = _service(
        tmp_path / "missing", summaries=tuple(missing), linkage=None
    )
    missing_result = _review(service, evidence)
    assert missing_result.response is not None
    assert missing_result.response.review.readiness == "blocked"
    assert missing_result.response.review.blockers == ("missing_evidence",)

    linkage = _linkage(tmp_path / "expired")
    expired = list(_summaries(linkage))
    evidence_id, fingerprint = _expected_summary_identities(linkage)[9]
    expired[9] = InstallationReadinessEvidenceSummaryV1(
        release="v0.29",
        evidence_kind="delivery_activation_preflight",
        evidence_id=evidence_id,
        evidence_fingerprint=fingerprint,
        evidence_state="expired",
        valid_until="2026-08-27T12:00:15Z",
    )
    evidence, _, service = _service(
        tmp_path / "expired-service", summaries=tuple(expired), linkage=linkage
    )
    expired_result = _review(service, evidence)
    assert expired_result.response is not None
    assert expired_result.response.review.blockers == ("expired_evidence",)

    evidence, _, service = _service(
        tmp_path / "stale-service", blockers=("stale_evidence",)
    )
    stale_result = _review(service, evidence)
    assert stale_result.response is not None
    assert stale_result.response.review.readiness == "blocked"
    assert stale_result.response.review.blockers == ("stale_evidence",)


def test_ownership_authentication_and_permission_are_isolated(tmp_path: Path) -> None:
    evidence, reader, service = _service(tmp_path)
    unauthenticated = _review(service, evidence, operator=None)
    forbidden = _review(service, evidence, permission=False)
    foreign = _review(service, evidence, operator="operator-b")

    assert unauthenticated.error is not None
    assert unauthenticated.error.error_code == "unauthenticated"
    assert forbidden.error is not None and forbidden.error.error_code == "unauthorized"
    assert foreign.error is not None and foreign.error.error_code == "not_found"
    assert reader.calls == 1
    assert evidence.candidate_record_id not in foreign.error.model_dump_json()


def test_mismatched_and_unavailable_evidence_errors_are_fully_redacted(
    tmp_path: Path,
) -> None:
    evidence, reader, service = _service(tmp_path)
    raw = evidence.model_dump(mode="python")
    summaries = list(raw["evidence"])
    summaries[0]["evidence_fingerprint"] = None
    raw["evidence"] = tuple(summaries)
    reader.evidence = InstallationReadinessReviewEvidenceV1.model_construct(**raw)
    mismatch = _review(service, evidence)
    assert mismatch.disposition == "unavailable"
    assert mismatch.error is not None and mismatch.error.error_code == "unavailable"

    secret = "super-secret-token"
    reader.error = RuntimeError(secret)
    unavailable = _review(service, evidence)
    rendered = unavailable.model_dump_json()
    assert secret not in rendered
    assert evidence.candidate_record_id not in rendered
    assert unavailable.error is not None and not unavailable.error.retryable


def test_home_assistant_is_blocked_golden(tmp_path: Path) -> None:
    evidence, _, service = _service(
        tmp_path,
        home_assistant=True,
        installation_capability_supported=False,
    )
    result = _review(service, evidence)
    assert result.response is not None
    review = result.response.review
    assert review.readiness == "blocked"
    assert review.blockers == ("installation_capability_unsupported",)
    assert not review.installation_allowed
    assert not review.execution_authorized


def test_service_has_no_persistence_reservation_or_forbidden_effect_surface() -> None:
    source = Path(service_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not any(
        marker in name
        for name in imported
        for marker in (
            "store", "sqlite", "routes", "transport", "http", "requests",
            "subprocess", "docker", "agent", "workflow", "worker", "provider",
            "repository",
        )
    )
    lowered = source.lower()
    for marker in (
        ".reserve(", ".append(", ".create(", ".update(", ".delete(",
        ".consume(", ".retry(", ".replay(", "uuid4(", "subprocess",
        "docker", "podman", "install(", "execute(", "dispatch(", "deploy(",
    ):
        assert marker not in lowered
