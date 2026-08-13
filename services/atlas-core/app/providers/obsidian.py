from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from app.config.policies import get_obsidian_policy
from app.config.policy_models import (
    ObsidianPolicy,
    PolicySeverity,
)
from app.context import AtlasContext
from app.intelligence.findings import Finding, Severity
from app.providers import (
    Provider,
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderPriority,
    ProviderWorkspace,
)
from app.providers.context_helpers import (
    context_from_legacy_service,
    legacy_service,
    metadata_from_context,
)


class ObsidianProvider(Provider):
    """Read-only metadata provider for a local Obsidian vault."""

    def __init__(
        self,
        service: AtlasContext | dict[str, Any],
        *,
        policy_getter: Callable[[], ObsidianPolicy] = (
            get_obsidian_policy
        ),
    ) -> None:
        # Temporary compatibility seam for direct legacy constructors.
        self.atlas_context = (
            service
            if isinstance(service, AtlasContext)
            else context_from_legacy_service("obsidian", service)
        )
        service_config = legacy_service(self.atlas_context)
        connection = self.atlas_context.connection
        self._vault_path = Path(
            str(
                (connection.path if connection is not None else None)
                or service_config.get("vault_path", ""),
            ),
        )
        self._max_scan_files = self._positive_int(
            service_config.get("max_scan_files", 10_000),
            "max_scan_files",
        )
        self._policy_getter = policy_getter
        excluded = service_config.get(
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

        self._metadata = metadata_from_context(
            self.atlas_context,
            default_description=(
                "Local Obsidian vault availability and metadata provider."
            ),
            default_workspace=ProviderWorkspace.KNOWLEDGE,
            default_icon="notebook-tabs",
            default_priority=ProviderPriority.NORMAL,
            default_capabilities=frozenset(
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
        policy = self._policy_getter()
        note_count = int(health.details.get("note_count") or 0)
        if note_count < policy.minimum_note_count:
            severity = self._severity(
                policy.insufficient_notes_severity
            )
            findings.append(
                Finding(
                    id="obsidian-vault-insufficient-notes",
                    severity=severity,
                    category="knowledge",
                    source="obsidian",
                    component=self.metadata.name,
                    title="Obsidian vault has insufficient notes",
                    message=(
                        f"Atlas found {note_count} Markdown note(s); "
                        f"policy requires at least "
                        f"{policy.minimum_note_count}."
                    ),
                    recommendation=(
                        "Confirm the vault path and verify that the "
                        "vault has been mounted with its note data."
                    ),
                    affects_health=severity != Severity.INFO,
                    score_penalty=self._score_penalty(severity),
                    metric={
                        "note_count": note_count,
                        "minimum_note_count": (
                            policy.minimum_note_count
                        ),
                    },
                ),
            )

        if health.details.get("scan_truncated"):
            severity = self._severity(
                policy.scan_truncated_severity
            )
            findings.append(
                Finding(
                    id="obsidian-vault-scan-truncated",
                    severity=severity,
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
                    affects_health=severity != Severity.INFO,
                    score_penalty=self._score_penalty(severity),
                    details={
                        "max_scan_files": self._max_scan_files,
                    },
                ),
            )

        if (
            policy.stale_after_days is not None
            and self._is_stale(
                health.details.get("latest_note_modified_at"),
                policy.stale_after_days,
            )
        ):
            severity = self._severity(policy.stale_severity)
            findings.append(
                Finding(
                    id="obsidian-vault-stale",
                    severity=severity,
                    category="knowledge",
                    source="obsidian",
                    component=self.metadata.name,
                    title="Obsidian vault has no recent note changes",
                    message=(
                        "The newest note exceeds the configured "
                        f"{policy.stale_after_days}-day freshness "
                        "window."
                    ),
                    recommendation=(
                        "Confirm the vault is still active and that "
                        "synchronization is current."
                    ),
                    affects_health=severity != Severity.INFO,
                    score_penalty=self._score_penalty(severity),
                    details={
                        "stale_after_days": policy.stale_after_days,
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
            raise ValueError(f"{field} must be a positive integer.")  # noqa: TRY004
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"{field} must be a positive integer."
            ) from error
        if parsed < 1:
            raise ValueError(f"{field} must be a positive integer.")
        return parsed

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

    @staticmethod
    def _severity(value: PolicySeverity) -> Severity:
        return {
            "info": Severity.INFO,
            "warning": Severity.WARNING,
            "critical": Severity.CRITICAL,
        }[value]

    @staticmethod
    def _score_penalty(severity: Severity) -> int:
        return {
            Severity.INFO: 0,
            Severity.WARNING: 5,
            Severity.CRITICAL: 15,
        }[severity]
