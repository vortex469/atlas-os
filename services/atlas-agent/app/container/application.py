"""Application dependency container."""

from dataclasses import dataclass

from app.config.settings import Settings
from app.context.engine import ContextEngine
from app.core_client.client import AtlasCoreClient
from app.repository.inspector import GitInspector
from app.workflow.state import WorkflowStateStore


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    """Dependencies shared by the Atlas Agent application."""

    settings: Settings
    core_client: AtlasCoreClient
    context_engine: ContextEngine
    repository_inspector: GitInspector
    workflow_state: WorkflowStateStore
