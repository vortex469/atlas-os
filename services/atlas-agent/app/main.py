"""Atlas Agent FastAPI application."""

import logging

from fastapi import FastAPI

from app.config.settings import Settings, load_settings
from app.container.application import ApplicationContainer
from app.repository.inspector import GitInspector
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

    container = ApplicationContainer(
        settings=settings,
        repository_inspector=GitInspector(
            repository_root=settings.repository_root,
        ),
        workflow_state=WorkflowStateStore(),
    )

    application = FastAPI(
        title=settings.app_name,
        version=AGENT_VERSION,
    )
    application.state.container = container
    application.include_router(health_router)
    application.include_router(status_router)

    return application


app = create_app()
