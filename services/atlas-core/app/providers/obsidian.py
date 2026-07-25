from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from app.intelligence.findings import Finding, Severity
from app.providers import (
    Provider,
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderPriority,
    ProviderWorkspace,
)


class ObsidianProvider(Provider):
    """Read-only metadata provider for a local Obsidian vault."""

    def __init__(self, service: dict[str, Any]) -> None:
        self._service = service
        self._vault_path = Path(
            str(service.get("vault_path", "")),
        )
        self._max_scan_files = self._positive_int(
            service.get("max_scan_files", 10_000),
            "max_scan_files",
        )
        self._stale_after_days = self._optional_positive_int(
            service.get("stale_after_days"),
            "stale_after_days",
        )
        excluded = service.get(
            "exclude_directories",
            [".obsidian", ".trash"],
        )
        if not isinstance(excluded, list) or not all(
            isinstance(value, str) and value
            for value in excluded
        ):
            raise ValueError(
                "exclude_directories must be a list of names."
            )
        self._excluded_directories = frozenset(excluded)

        self._metadata = ProviderMetadata(
            id="obsidian",
            name=service.get("name", "Obsidian"),
            version="1.0.0",
            description=(
                "Local Obsidian vault availability and metadata "
                "provider."
            ),
            workspace=ProviderWorkspace.KNOWLEDGE,
            icon="notebook-tabs",
            priority=(
                ProviderPriority.CRITICAL
                if service.get("critical", False)
                else ProviderPriority.NORMAL
            ),
            capabilities=frozenset(
                {
                    ProviderCapability.HEALTH,
                    ProviderCapability.FINDINGS,
                    ProviderCapability.ACTIONS,
                    ProviderCapability.METRICS,
                    ProviderCapability.CONFIGURATION,
                },
            ),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    async def get_health(self) -> ProviderHealth:
        started_at = perf_counter()

        try:
            details = self._scan_vault()
        except (OSError, ValueError) as error:
            return ProviderHealth(
                status="offline",
                latency_ms=self._elapsed_ms(started_at),
                message="Obsidian vault is unavailable.",
                details={
                    "vault_name": self._vault_name,
                    "error": str(error),
                },
            )

        note_count = int(details["note_count"])
        return ProviderHealth(
            status="online" if note_count > 0 else "degraded",
            latency_ms=self._elapsed_ms(started_at),
            message=(
                "Obsidian vault metadata scan completed."
                if note_count > 0
                else "Obsidian vault contains no Markdown notes."
            ),
            details=details,
        )

    async def get_findings(self) -> list[Finding]:
        health = await self.get_health()

        if health.status == "offline":
            critical = (
                self.metadata.priority
                == ProviderPriority.CRITICAL
            )
            return [
                Finding(
                    id="obsidian-vault-offline",
                    severity=(
                        Severity.CRITICAL
                        if critical
                        else Severity.WARNING
                    ),
                    category="knowledge",
                    source="obsidian",
                    component=self.metadata.name,
                    title="Obsidian vault unavailable",
                    message=(
                        health.message
                        or "Atlas cannot access the Obsidian vault."
                    ),
                    recommendation=(
                        "Review the configured vault path, mount, and "
                        "Atlas filesystem permissions."
                    ),
                    score_penalty=20 if critical else 10,
                    details={
                        "vault_name": health.details.get(
                            "vault_name"
                        ),
                    },
                ),
            ]

        findings: list[Finding] = []
        if health.details.get("note_count") == 0:
            findings.append(
                Finding(
                    id="obsidian-vault-empty",
                    severity=Severity.WARNING,
                    category="knowledge",
                    source="obsidian",
                    component=self.metadata.name,
                    title="Obsidian vault contains no notes",
                    message=(
                        "Atlas found no Markdown notes in the "
                        "configured Obsidian vault."
                    ),
                    recommendation=(
                        "Confirm the vault path and verify that the "
                        "vault has been mounted with its note data."
                    ),
                    score_penalty=5,
                ),
            )

        if health.details.get("scan_truncated"):
            findings.append(
                Finding(
                    id="obsidian-vault-scan-truncated",
                    severity=Severity.WARNING,
                    category="knowledge",
                    source="obsidian",
                    component=self.metadata.name,
                    title="Obsidian vault scan truncated",
                    message=(
                        "The vault exceeded the configured metadata "
                        "scan file limit."
                    ),
                    recommendation=(
                        "Increase max_scan_files or exclude large "
                        "non-note directories."
                    ),
                    score_penalty=5,
                    details={
                        "max_scan_files": self._max_scan_files,
                    },
                ),
            )

        if (
            self._stale_after_days is not None
            and self._is_stale(
                health.details.get("latest_note_modified_at"),
                self._stale_after_days,
            )
        ):
            findings.append(
                Finding(
                    id="obsidian-vault-stale",
                    severity=Severity.INFO,
                    category="knowledge",
                    source="obsidian",
                    component=self.metadata.name,
                    title="Obsidian vault has no recent note changes",
                    message=(
                        "The newest note exceeds the configured "
                        f"{self._stale_after_days}-day freshness window."
                    ),
                    recommendation=(
                        "Confirm the vault is still active and that "
                        "synchronization is current."
                    ),
                    affects_health=False,
                    score_penalty=0,
                    details={
                        "stale_after_days": self._stale_after_days,
                        "latest_note_modified_at": health.details.get(
                            "latest_note_modified_at"
                        ),
                    },
                ),
            )

        return findings

    @property
    def _vault_name(self) -> str:
        return self._vault_path.name or "unconfigured"

    def _scan_vault(self) -> dict[str, Any]:
        if not self._vault_path.is_absolute():
            raise ValueError("Obsidian vault_path must be absolute.")
        if not self._vault_path.exists():
            raise OSError("Configured Obsidian vault does not exist.")
        if not self._vault_path.is_dir():
            raise OSError("Configured Obsidian vault is not a directory.")

        note_count = 0
        attachment_count = 0
        scanned_file_count = 0
        latest_note_mtime: float | None = None
        scan_truncated = False

        def record_error(error: OSError) -> None:
            raise error

        for root, directories, files in os.walk(
            self._vault_path,
            topdown=True,
            onerror=record_error,
            followlinks=False,
        ):
            directories[:] = [
                name
                for name in directories
                if name not in self._excluded_directories
                and not Path(root, name).is_symlink()
            ]

            for filename in files:
                if scanned_file_count >= self._max_scan_files:
                    scan_truncated = True
                    directories.clear()
                    break

                path = Path(root, filename)
                if path.is_symlink():
                    continue

                scanned_file_count += 1
                if path.suffix.casefold() == ".md":
                    note_count += 1
                    modified_at = path.stat().st_mtime
                    if (
                        latest_note_mtime is None
                        or modified_at > latest_note_mtime
                    ):
                        latest_note_mtime = modified_at
                else:
                    attachment_count += 1

            if scan_truncated:
                break

        return {
            "vault_name": self._vault_name,
            "note_count": note_count,
            "attachment_count": attachment_count,
            "scanned_file_count": scanned_file_count,
            "scan_truncated": scan_truncated,
            "max_scan_files": self._max_scan_files,
            "latest_note_modified_at": (
                datetime.fromtimestamp(
                    latest_note_mtime,
                    tz=UTC,
                ).isoformat()
                if latest_note_mtime is not None
                else None
            ),
        }

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return round((perf_counter() - started_at) * 1000, 2)

    @staticmethod
    def _positive_int(value: object, field: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field} must be a positive integer.")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"{field} must be a positive integer."
            ) from error
        if parsed < 1:
            raise ValueError(f"{field} must be a positive integer.")
        return parsed

    @classmethod
    def _optional_positive_int(
        cls,
        value: object,
        field: str,
    ) -> int | None:
        if value is None:
            return None
        return cls._positive_int(value, field)

    @staticmethod
    def _is_stale(
        modified_at: object,
        stale_after_days: int,
    ) -> bool:
        if not isinstance(modified_at, str):
            return False
        modified = datetime.fromisoformat(modified_at)
        age = datetime.now(UTC) - modified
        return age.total_seconds() > stale_after_days * 86_400
