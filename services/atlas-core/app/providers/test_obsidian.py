import asyncio
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path

import pytest

from app.config.policy_models import ObsidianPolicy
from app.providers import loader
from app.providers.obsidian import ObsidianProvider
from app.providers.registry import ProviderRegistry


def service(vault_path: Path, **overrides) -> dict:
    return {
        "name": "Obsidian",
        "vault_path": str(vault_path),
        "critical": False,
        **overrides,
    }


def test_obsidian_health_scans_metadata_without_note_contents(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "daily").mkdir(parents=True)
    (vault / "daily" / "today.md").write_text(
        "private note content",
        encoding="utf-8",
    )
    (vault / "diagram.png").write_bytes(b"image")
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "workspace.json").write_text(
        "{}",
        encoding="utf-8",
    )
    provider = ObsidianProvider(service(vault))

    health = asyncio.run(provider.get_health())

    assert health.status == "online"
    assert health.details["vault_name"] == "vault"
    assert health.details["note_count"] == 1
    assert health.details["attachment_count"] == 1
    assert health.details["scanned_file_count"] == 2
    assert "private note content" not in str(health.model_dump())


def test_missing_critical_vault_produces_critical_finding(
    tmp_path: Path,
) -> None:
    provider = ObsidianProvider(
        service(tmp_path / "missing", critical=True),
    )

    findings = asyncio.run(provider.get_findings())

    assert len(findings) == 1
    assert findings[0].id == "obsidian-vault-offline"
    assert findings[0].severity == "critical"
    assert findings[0].score_penalty == 20


def test_empty_vault_is_degraded(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    provider = ObsidianProvider(service(vault))

    health = asyncio.run(provider.get_health())

    findings = asyncio.run(provider.get_findings())

    assert health.status == "degraded"
    assert findings[0].id == (
        "obsidian-vault-insufficient-notes"
    )
    assert findings[0].severity == "warning"


def test_scan_limit_is_reported(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    for index in range(3):
        (vault / f"{index}.md").write_text(
            "note",
            encoding="utf-8",
        )
    provider = ObsidianProvider(
        service(vault, max_scan_files=2),
    )

    health = asyncio.run(provider.get_health())
    findings = asyncio.run(provider.get_findings())

    assert health.details["scanned_file_count"] == 2
    assert health.details["scan_truncated"] is True
    assert findings[0].id == "obsidian-vault-scan-truncated"


def test_stale_vault_finding_is_advisory(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "old.md"
    note.write_text("old note", encoding="utf-8")
    old_timestamp = (
        datetime.now(UTC) - timedelta(days=31)
    ).timestamp()
    os.utime(note, (old_timestamp, old_timestamp))
    provider = ObsidianProvider(
        service(vault),
        policy_getter=lambda: ObsidianPolicy(
            stale_after_days=30,
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert len(findings) == 1
    assert findings[0].id == "obsidian-vault-stale"
    assert findings[0].severity == "info"
    assert findings[0].affects_health is False


def test_obsidian_note_threshold_and_severity_follow_policy(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "one.md").write_text("note", encoding="utf-8")
    provider = ObsidianProvider(
        service(vault),
        policy_getter=lambda: ObsidianPolicy(
            minimum_note_count=2,
            insufficient_notes_severity="critical",
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert findings[0].severity == "critical"
    assert findings[0].affects_health is True
    assert findings[0].score_penalty == 15
    assert findings[0].metric == {
        "note_count": 1,
        "minimum_note_count": 2,
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_scan_files": 0},
        {"exclude_directories": ".obsidian"},
    ],
)
def test_invalid_obsidian_configuration_is_rejected(
    tmp_path: Path,
    overrides: dict,
) -> None:
    with pytest.raises(ValueError):
        ObsidianProvider(service(tmp_path, **overrides))


def test_loader_selects_obsidian_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry = ProviderRegistry()
    monkeypatch.setattr(loader, "provider_registry", registry)
    monkeypatch.setattr(
        loader,
        "load_inventory",
        lambda: {
            "services": {
                "obsidian": service(tmp_path),
            },
        },
    )

    loader.load_provider_registry()

    assert isinstance(
        registry.get("obsidian"),
        ObsidianProvider,
    )
