"""Application dependency container."""

from dataclasses import dataclass

from app.config.settings import Settings


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    """Dependencies shared by the Atlas Agent application."""

    settings: Settings
