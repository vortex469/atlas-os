from pathlib import Path

import pytest

from app.config import policies as policy_config
from app.config.policies import (
    DEFAULT_POLICY_FILE,
    DEFAULT_POLICY_TEMPLATE_FILE,
    PolicyLoadError,
    get_expected_container_state,
    get_expected_guest_state,
    get_frigate_policy,
    get_ignored_entities,
    get_intelligence_policy,
    get_n8n_policy,
    get_obsidian_policy,
    get_opnsense_policy,
    get_policy_file,
    get_policy_template_file,
    get_qdrant_policy,
    load_policies,
)


def write_policy(policy_file: Path, content: str) -> None:
    policy_file.parent.mkdir(parents=True, exist_ok=True)
    policy_file.write_text(content, encoding="utf-8")


def test_default_runtime_and_template_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ATLAS_POLICY_FILE", raising=False)
    monkeypatch.delenv("ATLAS_POLICY_TEMPLATE_FILE", raising=False)

    assert get_policy_file() == DEFAULT_POLICY_FILE
    assert get_policy_template_file() == DEFAULT_POLICY_TEMPLATE_FILE


def test_policy_path_environment_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_policy = tmp_path / "runtime" / "policies.yaml"
    template_policy = tmp_path / "templates" / "policies.yaml"
    monkeypatch.setenv("ATLAS_POLICY_FILE", str(runtime_policy))
    monkeypatch.setenv("ATLAS_POLICY_TEMPLATE_FILE", str(template_policy))

    assert get_policy_file() == runtime_policy
    assert get_policy_template_file() == template_policy


def test_first_run_initializes_runtime_policy_from_valid_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_policy = tmp_path / "runtime" / "config" / "policies.yaml"
    template_policy = tmp_path / "config" / "policies.yaml"
    monkeypatch.setenv("ATLAS_POLICY_FILE", str(runtime_policy))
    monkeypatch.setenv("ATLAS_POLICY_TEMPLATE_FILE", str(template_policy))
    write_policy(
        template_policy,
        """
proxmox:
  guests:
    "109":
      expected: stopped
docker:
  containers:
    atlas-core:
      expected: running
""".lstrip(),
    )

    policies = load_policies()

    assert runtime_policy.exists()
    assert runtime_policy.read_text(encoding="utf-8") == template_policy.read_text(
        encoding="utf-8",
    )
    assert policies.proxmox.guests["109"].expected == "stopped"
    assert policies.docker.containers["atlas-core"].expected == "running"


def test_existing_runtime_policy_is_not_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_policy = tmp_path / "runtime" / "config" / "policies.yaml"
    template_policy = tmp_path / "config" / "policies.yaml"
    monkeypatch.setenv("ATLAS_POLICY_FILE", str(runtime_policy))
    monkeypatch.setenv("ATLAS_POLICY_TEMPLATE_FILE", str(template_policy))
    write_policy(
        runtime_policy,
        """
proxmox:
  guests:
    "109":
      expected: running
""".lstrip(),
    )
    write_policy(
        template_policy,
        """
proxmox:
  guests:
    "109":
      expected: stopped
""".lstrip(),
    )

    policies = load_policies()

    assert policies.proxmox.guests["109"].expected == "running"
    assert "expected: running" in runtime_policy.read_text(encoding="utf-8")


def test_runtime_parent_directory_is_created(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_policy = tmp_path / "missing" / "nested" / "policies.yaml"
    template_policy = tmp_path / "config" / "policies.yaml"
    monkeypatch.setenv("ATLAS_POLICY_FILE", str(runtime_policy))
    monkeypatch.setenv("ATLAS_POLICY_TEMPLATE_FILE", str(template_policy))
    write_policy(template_policy, "homeassistant:\n  ignored_entities: []\n")

    load_policies()

    assert runtime_policy.parent.is_dir()
    assert runtime_policy.exists()


def test_invalid_template_blocks_runtime_initialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_policy = tmp_path / "runtime" / "policies.yaml"
    template_policy = tmp_path / "config" / "policies.yaml"
    monkeypatch.setenv("ATLAS_POLICY_FILE", str(runtime_policy))
    monkeypatch.setenv("ATLAS_POLICY_TEMPLATE_FILE", str(template_policy))
    write_policy(template_policy, "docker:\n  containers:\n    atlas-core:\n      expected: paused\n")

    with pytest.raises(PolicyLoadError, match="policy initialization failed"):
        load_policies()

    assert not runtime_policy.exists()


def test_invalid_runtime_policy_blocks_loading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_policy = tmp_path / "runtime" / "policies.yaml"
    template_policy = tmp_path / "config" / "policies.yaml"
    monkeypatch.setenv("ATLAS_POLICY_FILE", str(runtime_policy))
    monkeypatch.setenv("ATLAS_POLICY_TEMPLATE_FILE", str(template_policy))
    write_policy(runtime_policy, "docker:\n  containers:\n    atlas-core:\n      expected: paused\n")
    write_policy(template_policy, "docker:\n  containers: {}\n")

    with pytest.raises(PolicyLoadError, match="policy reload failed"):
        load_policies()

    assert "expected: paused" in runtime_policy.read_text(encoding="utf-8")


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
obsidian:
  minimum_note_count: 10
  stale_after_days: 14
  insufficient_notes_severity: critical
  stale_severity: warning
  scan_truncated_severity: info
qdrant:
  expected_collections:
    - memory
    - documents
  missing_collection_severity: critical
  empty_instance_severity: warning
n8n:
  expected_active_workflows:
    - Daily backup
    - Knowledge sync
  inactive_workflow_severity: critical
  scan_truncated_severity: info
  empty_instance_severity: warning
intelligence:
  providers:
    qdrant:
      maximum_collection_duration_ms: 250
      severity: critical
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
    assert get_obsidian_policy().minimum_note_count == 10
    assert get_obsidian_policy().stale_after_days == 14
    assert (
        get_obsidian_policy().insufficient_notes_severity
        == "critical"
    )
    assert get_qdrant_policy().expected_collections == [
        "memory",
        "documents",
    ]
    assert (
        get_qdrant_policy().missing_collection_severity
        == "critical"
    )
    assert get_n8n_policy().expected_active_workflows == [
        "Daily backup",
        "Knowledge sync",
    ]
    assert (
        get_n8n_policy().inactive_workflow_severity
        == "critical"
    )
    assert (
        get_intelligence_policy()
        .providers["qdrant"]
        .maximum_collection_duration_ms
        == 250
    )

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
    assert get_obsidian_policy().minimum_note_count == 1
    assert get_obsidian_policy().stale_after_days is None
    assert get_qdrant_policy().expected_collections == []
    assert get_n8n_policy().expected_active_workflows == []
    assert get_intelligence_policy().providers == {}


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
        """
obsidian:
  stale_after_days: 0
""",
        """
qdrant:
  expected_collections:
    - memory
    - memory
""",
        """
qdrant:
  expected_collections:
    - ""
""",
        """
qdrant:
  missing_collection_severity: emergency
""",
        """
n8n:
  expected_active_workflows:
    - Sync
    - Sync
""",
        """
n8n:
  expected_active_workflows:
    - ""
""",
        """
n8n:
  scan_truncated_severity: urgent
""",
        """
intelligence:
  providers:
    qdrant:
      maximum_collection_duration_ms: 0
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
    assert policies.obsidian.minimum_note_count == 1
    assert policies.qdrant.expected_collections == []
    assert policies.n8n.expected_active_workflows == []
    assert policies.intelligence.providers == {}
