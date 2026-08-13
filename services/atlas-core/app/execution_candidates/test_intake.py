from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.execution_candidates.intake import CandidatePlanningIntakeRequest


def test_intake_request_allows_only_expected_fields() -> None:
    with pytest.raises(ValidationError):
        CandidatePlanningIntakeRequest.model_validate(
            {
                "expected_candidate_fingerprint": "candidate-fingerprint-v1:abc",
                "requested_by": "operator",
                "execution_intent": "restart-service",
            }
        )


def test_requested_by_is_informational_only_contract_field() -> None:
    request = CandidatePlanningIntakeRequest(requested_by="operator")

    assert request.requested_by == "operator"
    assert request.expected_candidate_fingerprint is None
