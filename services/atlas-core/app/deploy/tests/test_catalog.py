from app.catalog.models import (
    Application,
    ApplicationCategory,
)
from app.catalog.repository import (
    CatalogRepository,
)
from app.catalog.service import (
    CatalogService,
)


def test_register_application():

    repository = CatalogRepository()

    service = CatalogService(repository)

    app = Application(
        id="immich",
        name="Immich",
        category=ApplicationCategory.MEDIA,
    )

    service.register(app)

    assert service.get("immich") == app


def test_catalog_sorted():

    repository = CatalogRepository()

    service = CatalogService(repository)

    service.register(
        Application(
            id="z",
            name="Z App",
        )
    )

    service.register(
        Application(
            id="a",
            name="A App",
        )
    )

    apps = service.list()

    assert apps[0].name == "A App"