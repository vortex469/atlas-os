from pathlib import Path

import pytest

from app.config import policies as policy_config
from app.config.policies import (
    PolicyLoadError,
    get_expected_container_state,
    get_expected_guest_state,
    get_ignored_entities,
    load_policies,
)


def write_policy(policy_file: Path, content: str) -> None:
    policy_file.write_text(content, encoding="utf-8")


def test_policy_changes_reload_without_process_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy_file = tmp_path / "policies.yaml"
    monkeypatch.setattr(
        policy_config,
        "POLICY_FILE",
        policy_file,
    )
    write_policy(
        policy_file,
        """
docker:
  containers:
    atlas-core:
      expected: running
proxmox:
  guests:
    "101":
      expected: stopped
homeassistant:
  ignored_entities:
    - sensor.intentional_offline
""",
    )

    assert get_expected_container_state("atlas-core") == "running"
    assert get_expected_guest_state(101) == "stopped"
    assert get_ignored_entities() == [
        "sensor.intentional_offline",
    ]

    write_policy(
        policy_file,
        """
docker:
  containers:
    atlas-core:
      expected: stopped
homeassistant:
  ignored_entities: []
""",
    )

    assert get_expected_container_state("atlas-core") == "stopped"
    assert get_expected_guest_state(101) is None
    assert get_ignored_entities() == []


@pytest.mark.parametrize(
    "content",
    [
        "docker: [",
        """
docker:
  containers:
    atlas-core:
      expected: paused
""",
    ],
)
def test_invalid_policy_reload_has_stable_error(
    tmp_path: Path,
    content: str,
) -> None:
    policy_file = tmp_path / "policies.yaml"
    write_policy(policy_file, content)

    with pytest.raises(
        PolicyLoadError,
        match="Atlas policy reload failed",
    ):
        load_policies(policy_file)


def test_missing_policy_file_uses_safe_defaults(
    tmp_path: Path,
) -> None:
    policies = load_policies(tmp_path / "missing.yaml")

    assert policies.docker.containers == {}
    assert policies.proxmox.guests == {}
    assert policies.homeassistant.ignored_entities == []
