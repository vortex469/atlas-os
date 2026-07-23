from __future__ import annotations

from app.catalog.models import Application


class CatalogRepository:
    """Simple in-memory catalog."""

    def __init__(self) -> None:
        self._applications: dict[str, Application] = {}

    def add(
        self,
        application: Application,
    ) -> None:
        self._applications[
            application.id
        ] = application

    def get(
        self,
        application_id: str,
    ) -> Application | None:
        return self._applications.get(
            application_id
        )

    def list(self) -> list[Application]:
        return sorted(
            self._applications.values(),
            key=lambda app: app.name,
        )