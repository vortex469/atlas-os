"""Atlas Agent FastAPI application."""

import logging

from fastapi import FastAPI

from app.approval.repository import ApprovalRepository
from app.config.settings import Settings, load_settings
from app.container.application import ApplicationContainer
from app.context.engine import ContextEngine
from app.core_client.client import AtlasCoreClient
from app.repository.inspector import GitInspector
from app.routes.approval import router as approval_router
from app.routes.health import router as health_router
from app.routes.status import router as status_router
from app.version import AGENT_VERSION
from app.workflow.state import WorkflowStateStore

logger = logging.getLogger("atlas-agent")


def configure_logging(settings: Settings) -> None:
    """Configure standard console logging."""

    log_level = getattr(
        logging,
        settings.log_level.upper(),
        logging.INFO,
    )

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app() -> FastAPI:
    """Create and configure the Atlas Agent application."""

    settings = load_settings()
    configure_logging(settings)

    logger.info(
        "Starting %s version=%s environment=%s host=%s port=%s "
        "repository_root=%s",
        settings.app_name,
        AGENT_VERSION,
        settings.environment,
        settings.host,
        settings.port,
        settings.repository_root,
    )

    # Create a single core client instance
    core_client = AtlasCoreClient(
        settings=settings,
    )

    container = ApplicationContainer(
        settings=settings,
        repository_inspector=GitInspector(
            repository_root=settings.repository_root,
        ),
        workflow_state=WorkflowStateStore(),
        core_client=core_client,
        context_engine=ContextEngine(core_client),
        approval_repository=ApprovalRepository(),
    )

    application = FastAPI(
        title=settings.app_name,
        version=AGENT_VERSION,
    )
    application.state.container = container
    application.include_router(health_router)
    application.include_router(status_router)
    application.include_router(approval_router)

    return application


app = create_app()
