from pathlib import Path

import pytest

from app.config import policies as policy_config
from app.routes.policies import policies, policy_status


def test_policy_route_returns_live_validated_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy_file = tmp_path / "policies.yaml"
    monkeypatch.setattr(
        policy_config,
        "POLICY_FILE",
        policy_file,
    )
    policy_file.write_text(
        """
qdrant:
  expected_collections:
    - memory
n8n:
  expected_active_workflows:
    - Knowledge sync
""",
        encoding="utf-8",
    )

    snapshot = policies()

    assert snapshot.qdrant.expected_collections == ["memory"]
    assert snapshot.n8n.expected_active_workflows == [
        "Knowledge sync",
    ]


def test_policy_routes_are_versioned_and_legacy() -> None:
    from app.main import app

    paths = set(app.openapi()["paths"])

    assert "/policies" in paths
    assert "/policies/status" in paths
    assert "/api/v1/policies" in paths
    assert "/api/v1/policies/status" in paths


def test_policy_status_reports_validation_failure_without_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy_file = tmp_path / "policies.yaml"
    policy_file.write_text("qdrant: [", encoding="utf-8")
    monkeypatch.setattr(
        policy_config,
        "POLICY_FILE",
        policy_file,
    )

    health = policy_status()

    assert health.status == "degraded"
    assert health.source_exists is True
    assert health.loaded_at is None
    assert health.duration_ms >= 0
    assert health.error is not None
    assert str(policy_file) not in health.error


def test_missing_policy_source_is_healthy_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        policy_config,
        "POLICY_FILE",
        tmp_path / "missing.yaml",
    )

    health = policy_status()

    assert health.status == "healthy"
    assert health.source_exists is False
    assert health.loaded_at is not None
    assert health.error is None
