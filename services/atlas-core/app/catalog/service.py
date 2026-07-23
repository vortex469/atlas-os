from app.catalog.models import Application
from app.catalog.repository import CatalogRepository


class CatalogService:

    def __init__(
        self,
        repository: CatalogRepository,
    ) -> None:
        self.repository = repository

    def register(
        self,
        application: Application,
    ) -> None:

        self.repository.add(application)

    def get(
        self,
        application_id: str,
    ) -> Application | None:

        return self.repository.get(
            application_id
        )

    def list(self):

        return self.repository.list()