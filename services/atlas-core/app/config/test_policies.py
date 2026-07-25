from pathlib import Path

import pytest

from app.config import policies as policy_config
from app.config.policies import (
    PolicyLoadError,
    get_expected_container_state,
    get_expected_guest_state,
    get_frigate_policy,
    get_ignored_entities,
    get_opnsense_policy,
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
opnsense:
  pending_update_warning_threshold: 3
  reboot_required_severity: critical
frigate:
  stalled_camera_severity: critical
  cameras:
    front:
      expected: active
      minimum_camera_fps: 4
      minimum_process_fps: 3
""",
    )

    assert get_expected_container_state("atlas-core") == "running"
    assert get_expected_guest_state(101) == "stopped"
    assert get_ignored_entities() == [
        "sensor.intentional_offline",
    ]
    assert (
        get_opnsense_policy().pending_update_warning_threshold
        == 3
    )
    assert (
        get_opnsense_policy().reboot_required_severity
        == "critical"
    )
    assert get_frigate_policy().cameras[
        "front"
    ].minimum_camera_fps == 4
    assert get_frigate_policy().stalled_camera_severity == "critical"

    write_policy(
        policy_file,
        """
docker:
  containers:
    atlas-core:
      expected: stopped
homeassistant:
  ignored_entities: []
opnsense:
  pending_update_warning_threshold: 5
  reboot_required_severity: info
""",
    )

    assert get_expected_container_state("atlas-core") == "stopped"
    assert get_expected_guest_state(101) is None
    assert get_ignored_entities() == []
    assert (
        get_opnsense_policy().pending_update_warning_threshold
        == 5
    )
    assert get_opnsense_policy().reboot_required_severity == "info"
    assert get_frigate_policy().cameras == {}


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
        """
opnsense:
  pending_update_warning_threshold: 0
""",
        """
frigate:
  cameras:
    front:
      expected: unavailable
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
    assert (
        policies.opnsense.pending_update_warning_threshold
        is None
    )
    assert policies.frigate.cameras == {}
