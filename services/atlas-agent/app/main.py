"""Atlas Agent FastAPI application."""

import logging

from fastapi import FastAPI

from app.config.settings import Settings, load_settings
from app.container.application import ApplicationContainer
from app.routes.health import router as health_router


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

    container = ApplicationContainer(settings=settings)

    application = FastAPI(title=settings.app_name)
    application.state.container = container
    application.include_router(health_router)

    return application


app = create_app()
