from __future__ import annotations

import ast
from pathlib import Path
from typing import Literal

import pytest
from pydantic import ValidationError

from app.end_to_end_inert_delivery_receipt.contract import linkage_fingerprint
from app.end_to_end_inert_delivery_receipt.test_contract import (
    _evidence as v033_evidence,
)
from app.installation_readiness_review import contract
from app.installation_readiness_review.contract import (
    BLOCKER_ORDER,
    EVIDENCE_ORDER,
    InstallationReadinessEvidenceSummaryV1,
    InstallationReadinessReviewAuditEvidenceV1,
    InstallationReadinessReviewEvidenceV1,
    InstallationReadinessReviewLinkageV1,
    InstallationReadinessReviewRedactedErrorV1,
    InstallationReadinessReviewResponseV1,
    InstallationReadinessReviewResultV1,
    InstallationReadinessReviewV1,
    StrictContractError,
    _expected_summary_identities,
    audit_evidence_fingerprint,
    canonical_json,
    create_installation_readiness_review,
    operator_fingerprint,
    parse_response_json,
    review_fingerprint,
)

OPERATOR = "operator-a"
OBSERVED_AT = "2026-08-27T12:00:16Z"
CORRELATION_ID = "readiness-review-1"
_UNSET = object()


def _fp(character: str):
    from app.installation_dispatch_handoff.contract import FingerprintV1

    return FingerprintV1(
        algorithm="sha256",
        canonicalization="atlas-jcs-nfc-v1",
        value=character * 64,
    )


def _linkage(tmp_path: Path) -> InstallationReadinessReviewLinkageV1:
    _, _, verification, v033_linkage, receipt = v033_evidence(tmp_path)
    return InstallationReadinessReviewLinkageV1(
        **v033_linkage.model_dump(mode="python"),
        v033_receipt_id=receipt.receipt_id,
        v033_receipt_fingerprint=receipt.receipt_fingerprint,
        v033_verification_fingerprint=verification.verification_fingerprint,
        v033_linkage_fingerprint=linkage_fingerprint(v033_linkage),
    )


def _summaries(
    linkage: InstallationReadinessReviewLinkageV1,
    *,
    state: Literal["current", "missing", "expired", "terminal", "unavailable"] = "current",
    valid_until: str | None = None,
) -> tuple[InstallationReadinessEvidenceSummaryV1, ...]:
    identities = _expected_summary_identities(linkage)
    return tuple(
        InstallationReadinessEvidenceSummaryV1(
            release=release,
            evidence_kind=kind,
            evidence_id=(None if state in {"missing", "unavailable"} else identity),
            evidence_fingerprint=(
                None if state in {"missing", "unavailable"} else fingerprint
            ),
            evidence_state=state,
            valid_until=valid_until,
        )
        for (release, kind), (identity, fingerprint) in zip(
            EVIDENCE_ORDER, identities, strict=True
        )
    )


def _input(
    tmp_path: Path,
    *,
    summaries: tuple[InstallationReadinessEvidenceSummaryV1, ...] | None = None,
    linkage: InstallationReadinessReviewLinkageV1 | None | object = _UNSET,
    **changes,
) -> InstallationReadinessReviewEvidenceV1:
    exact_linkage = _linkage(tmp_path)
    selected_linkage = exact_linkage if linkage is _UNSET else linkage
    values = {
        "operator_id": OPERATOR,
        "authenticated_operator_id": OPERATOR,
        "candidate_record_id": exact_linkage.candidate_record_id,
        "observed_at": OBSERVED_AT,
        "evidence": summaries or _summaries(exact_linkage),
        "linkage": selected_linkage,
    }
    values.update(changes)
    return InstallationReadinessReviewEvidenceV1.model_validate(values)


def _response(tmp_path: Path) -> InstallationReadinessReviewResponseV1:
    return create_installation_readiness_review(
        _input(tmp_path), correlation_id=CORRELATION_ID
    )


def test_valid_readiness_gated_review_is_deterministic_and_non_authorizing(
    tmp_path: Path,
) -> None:
    first = _response(tmp_path)
    second = _response(tmp_path)
    assert first == second
    review = first.review
    assert review.readiness == "readiness_gated"
    assert review.blockers == ("execution_admission_not_defined",)
    assert tuple((item.release, item.evidence_kind) for item in review.evidence) == (
        EVIDENCE_ORDER
    )
    assert review.review_fingerprint == review_fingerprint(review)
    assert first.audit_evidence.evidence_fingerprint == audit_evidence_fingerprint(
        first.audit_evidence
    )
    assert first.audit_evidence.operator_fingerprint == operator_fingerprint(OPERATOR)
    false_fields = (
        "execution_admission_granted",
        "execution_authorized",
        "installation_allowed",
        "dispatch_allowed",
        "worker_allowed",
        "workflow_allowed",
        "deployment_allowed",
        "mutation_allowed",
        "retry_allowed",
        "replay_allowed",
    )
    assert review.read_only and review.evidence_only
    assert not any(getattr(review, field) for field in false_fields)
    with pytest.raises(ValidationError):
        review.readiness = "blocked"  # type: ignore[misc]


def test_valid_missing_and_expired_reviews_are_blocked(tmp_path: Path) -> None:
    exact_linkage = _linkage(tmp_path)
    missing = list(_summaries(exact_linkage))
    missing[5] = InstallationReadinessEvidenceSummaryV1(
        release="v0.25",
        evidence_kind="agent_intake_simulation",
        evidence_id=None,
        evidence_fingerprint=None,
        evidence_state="missing",
        valid_until=None,
    )
    missing_response = create_installation_readiness_review(
        _input(tmp_path, summaries=tuple(missing), linkage=None),
        correlation_id=CORRELATION_ID,
    )
    assert missing_response.review.readiness == "blocked"
    assert missing_response.review.blockers == ("missing_evidence",)

    expired = list(_summaries(exact_linkage))
    identity, fingerprint = _expected_summary_identities(exact_linkage)[9]
    expired[9] = InstallationReadinessEvidenceSummaryV1(
        release="v0.29",
        evidence_kind="delivery_activation_preflight",
        evidence_id=identity,
        evidence_fingerprint=fingerprint,
        evidence_state="expired",
        valid_until="2026-08-27T12:00:15Z",
    )
    expired_response = create_installation_readiness_review(
        _input(tmp_path, summaries=tuple(expired)), correlation_id=CORRELATION_ID
    )
    assert expired_response.review.readiness == "blocked"
    assert expired_response.review.blockers == ("expired_evidence",)


def test_home_assistant_is_always_blocked_golden(tmp_path: Path) -> None:
    response = create_installation_readiness_review(
        _input(tmp_path, home_assistant=True, installation_capability_supported=False),
        correlation_id=CORRELATION_ID,
    )
    assert response.review.readiness == "blocked"
    assert response.review.blockers == ("installation_capability_unsupported",)
    assert not response.review.installation_allowed
    assert not response.review.execution_authorized


def test_linkage_fingerprint_summary_and_owner_mismatch_fail(tmp_path: Path) -> None:
    exact = _linkage(tmp_path)
    raw = exact.model_dump(mode="json")
    raw["v033_linkage_fingerprint"] = _fp("f").model_dump(mode="json")
    with pytest.raises(ValidationError, match="linkage fingerprint"):
        InstallationReadinessReviewLinkageV1.model_validate(raw)

    response = _response(tmp_path)
    raw_review = response.review.model_dump(mode="python")
    raw_review["evidence"][0]["evidence_fingerprint"] = _fp("e").model_dump(
        mode="json"
    )
    raw_review["review_fingerprint"] = review_fingerprint(raw_review).model_dump(
        mode="json"
    )
    with pytest.raises(ValidationError, match="summary linkage"):
        InstallationReadinessReviewV1.model_validate(raw_review)

    raw_input = _input(tmp_path).model_dump(mode="python")
    raw_input["authenticated_operator_id"] = "operator-b"
    with pytest.raises(ValidationError, match="ownership"):
        InstallationReadinessReviewEvidenceV1.model_validate(raw_input)


def test_stale_inputs_unsupported_states_and_blocker_order_fail(tmp_path: Path) -> None:
    exact = _linkage(tmp_path)
    stale = _summaries(exact, valid_until=OBSERVED_AT)
    with pytest.raises(ValidationError, match="stale|expired"):
        create_installation_readiness_review(
            _input(tmp_path, summaries=stale), correlation_id=CORRELATION_ID
        )

    raw = _response(tmp_path).review.model_dump(mode="python")
    raw["readiness"] = "ready"
    with pytest.raises(ValidationError):
        InstallationReadinessReviewV1.model_validate(raw)
    raw = _response(tmp_path).review.model_dump(mode="python")
    raw["readiness"] = "blocked"
    raw["blockers"] = ("expired_evidence", "missing_evidence")
    raw["review_fingerprint"] = review_fingerprint(raw)
    with pytest.raises(ValidationError, match="ordered"):
        InstallationReadinessReviewV1.model_validate(raw)
    assert BLOCKER_ORDER[-1] == "execution_admission_not_defined"


def test_closed_duplicate_unknown_redaction_and_bounds(tmp_path: Path) -> None:
    response = _response(tmp_path)
    payload = canonical_json(response)
    assert parse_response_json(payload) == response
    with pytest.raises(StrictContractError):
        parse_response_json(payload[:-1] + b',"review":"duplicate"}')
    raw = response.model_dump(mode="python")
    raw["token"] = "secret"
    with pytest.raises(ValidationError):
        InstallationReadinessReviewResponseV1.model_validate(raw)
    with pytest.raises(StrictContractError, match="128 KiB"):
        parse_response_json(b" " * (contract.MAX_RESPONSE_BYTES + 1))

    error = InstallationReadinessReviewRedactedErrorV1(
        error_code="not_found", correlation_id=CORRELATION_ID
    )
    rendered = error.model_dump_json()
    for forbidden in ("candidate_record_id", "fingerprint", "credential", "token"):
        assert forbidden not in rendered
    assert not error.retryable


def test_audit_binding_result_union_and_missing_fingerprints_fail(tmp_path: Path) -> None:
    response = _response(tmp_path)
    result = InstallationReadinessReviewResultV1(
        disposition="reviewed", response=response, error=None
    )
    assert result.read_only and not result.mutation_allowed
    with pytest.raises(ValidationError, match="union"):
        InstallationReadinessReviewResultV1(
            disposition="reviewed",
            response=None,
            error=InstallationReadinessReviewRedactedErrorV1(
                error_code="unavailable", correlation_id=CORRELATION_ID
            ),
        )
    raw = response.audit_evidence.model_dump(mode="json")
    raw.pop("evidence_fingerprint")
    with pytest.raises(ValidationError):
        InstallationReadinessReviewAuditEvidenceV1.model_validate(raw)
    raw = response.model_dump(mode="python")
    raw["audit_evidence"]["review_id"] = "00000000-0000-5000-8000-000000000001"
    raw["audit_evidence"]["evidence_fingerprint"] = audit_evidence_fingerprint(
        raw["audit_evidence"]
    )
    with pytest.raises(ValidationError, match="binding"):
        InstallationReadinessReviewResponseV1.model_validate(raw)


def test_contract_has_no_forbidden_imports_or_effect_calls() -> None:
    path = Path(contract.__file__)
    source = path.read_text(encoding="utf-8")
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
            "routes", "service", "store", "transport", "http", "requests",
            "subprocess", "docker", "workflow", "worker", "provider_intents",
            "repository",
        )
    )
    lowered = source.lower()
    for marker in (
        "agent_invoked", "network_attempted", "start_workflow", "dispatch_worker",
        "subprocess.run", "docker ", "podman ", "install_container(", "deploy(",
    ):
        assert marker not in lowered


def test_fixed_authority_annotations_are_literal_false() -> None:
    for model in (InstallationReadinessReviewV1, InstallationReadinessReviewResultV1):
        for field in (
            "execution_admission_granted", "execution_authorized",
            "installation_allowed", "dispatch_allowed", "worker_allowed",
            "workflow_allowed", "deployment_allowed", "mutation_allowed",
            "retry_allowed", "replay_allowed",
        ):
            assert model.model_fields[field].annotation == Literal[False]
