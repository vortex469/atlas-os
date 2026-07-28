"""Application dependency container."""

from dataclasses import dataclass

from app.config.settings import Settings
from app.repository.inspector import GitInspector
from app.workflow.state import WorkflowStateStore


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    """Dependencies shared by the Atlas Agent application."""

    settings: Settings
    repository_inspector: GitInspector
    workflow_state: WorkflowStateStore
