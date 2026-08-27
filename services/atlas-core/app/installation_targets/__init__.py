"""Immutable prospective installation destination selection foundation."""

from app.installation_targets.contract import (
    InstallationDestinationSelectionV1,
    ProspectiveInstallationDestinationV1,
)
from app.installation_targets.service import InstallationDestinationSelectionService

__all__ = [
    "InstallationDestinationSelectionService",
    "InstallationDestinationSelectionV1",
    "ProspectiveInstallationDestinationV1",
]
