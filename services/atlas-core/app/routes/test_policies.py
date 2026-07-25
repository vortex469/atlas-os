from pathlib import Path

import pytest

from app.config import policies as policy_config
from app.routes.policies import policies


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
    assert "/api/v1/policies" in paths
