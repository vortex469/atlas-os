from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.config.policies import PolicyLoadError, load_policies
from app.config.resource_policies import (
    ResourcePolicyValidationError,
    update_proxmox_guest_expectation,
)


def read_policy(policy_file: Path) -> dict:
    with policy_file.open("r", encoding="utf-8") as policy_stream:
        return yaml.safe_load(policy_stream)


def write_policy(policy_file: Path, content: str) -> None:
    policy_file.parent.mkdir(parents=True, exist_ok=True)
    policy_file.write_text(content, encoding="utf-8")


def test_policy_update_preserves_unrelated_yaml_sections(
    tmp_path: Path,
) -> None:
    policy_file = tmp_path / "policies.yaml"
    policy_file.write_text(
        """
proxmox:
  guests:
    "101":
      expected: running
docker:
  containers:
    atlas-core:
      expected: running
homeassistant:
  ignored_entities:
    - sensor.noisy
opnsense:
  reboot_required_severity: critical
""".lstrip(),
        encoding="utf-8",
    )

    update_proxmox_guest_expectation("109", "stopped", policy_file)

    policy = read_policy(policy_file)
    assert policy["proxmox"]["guests"]["101"] == {"expected": "running"}
    assert policy["proxmox"]["guests"]["109"] == {"expected": "stopped"}
    assert policy["docker"]["containers"]["atlas-core"] == {
        "expected": "running"
    }
    assert policy["homeassistant"]["ignored_entities"] == ["sensor.noisy"]
    assert policy["opnsense"]["reboot_required_severity"] == "critical"


def test_policy_update_rejects_invalid_expectation(tmp_path: Path) -> None:
    policy_file = tmp_path / "policies.yaml"
    policy_file.write_text("proxmox: {}\n", encoding="utf-8")

    with pytest.raises(ResourcePolicyValidationError):
        update_proxmox_guest_expectation("109", "paused", policy_file)

    assert read_policy(policy_file) == {"proxmox": {}}


def test_policy_update_uses_atomic_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy_file = tmp_path / "policies.yaml"
    policy_file.write_text("proxmox:\n  guests: {}\n", encoding="utf-8")
    replacements: list[tuple[Path, Path]] = []

    from app.config import resource_policies

    actual_replace = resource_policies.os.replace

    def record_replace(source: Path, target: Path) -> None:
        replacements.append((Path(source), Path(target)))
        actual_replace(source, target)

    monkeypatch.setattr(resource_policies.os, "replace", record_replace)

    update_proxmox_guest_expectation("109", "ignored", policy_file)

    assert len(replacements) == 1
    source, target = replacements[0]
    assert target == policy_file
    assert source.parent == policy_file.parent
    assert not source.exists()
    assert read_policy(policy_file)["proxmox"]["guests"]["109"] == {
        "expected": "ignored"
    }


def test_invalid_existing_policy_blocks_write(tmp_path: Path) -> None:
    policy_file = tmp_path / "policies.yaml"
    original_policy = "docker:\n  containers:\n    atlas-core:\n      expected: paused\n"
    policy_file.write_text(original_policy, encoding="utf-8")

    with pytest.raises(PolicyLoadError):
        update_proxmox_guest_expectation("109", "stopped", policy_file)

    assert policy_file.read_text(encoding="utf-8") == original_policy


def test_missing_policy_file_can_be_created(tmp_path: Path) -> None:
    policy_file = tmp_path / "policies.yaml"

    update_proxmox_guest_expectation(109, "running", policy_file)

    assert read_policy(policy_file)["proxmox"]["guests"]["109"] == {
        "expected": "running"
    }


def test_runtime_policy_update_is_immediately_visible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_policy = tmp_path / "runtime" / "config" / "policies.yaml"
    template_policy = tmp_path / "config" / "policies.yaml"
    monkeypatch.setenv("ATLAS_POLICY_FILE", str(runtime_policy))
    monkeypatch.setenv("ATLAS_POLICY_TEMPLATE_FILE", str(template_policy))
    write_policy(template_policy, "proxmox:\n  guests: {}\n")

    update_proxmox_guest_expectation("109", "stopped")

    assert load_policies().proxmox.guests["109"].expected == "stopped"


def test_runtime_policy_update_preserves_template_sections(
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
    "101":
      expected: running
docker:
  containers:
    atlas-core:
      expected: running
homeassistant:
  ignored_entities:
    - sensor.noisy
""".lstrip(),
    )

    update_proxmox_guest_expectation("109", "ignored")

    policy = read_policy(runtime_policy)
    assert policy["proxmox"]["guests"]["101"] == {"expected": "running"}
    assert policy["proxmox"]["guests"]["109"] == {"expected": "ignored"}
    assert policy["docker"]["containers"]["atlas-core"] == {
        "expected": "running",
    }
    assert policy["homeassistant"]["ignored_entities"] == ["sensor.noisy"]
