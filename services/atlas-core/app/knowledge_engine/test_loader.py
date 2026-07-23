from app.knowledge_engine import (
    KnowledgeCatalogLoader,
)


def test_loads_nginx_application_definition() -> None:
    loader = KnowledgeCatalogLoader()

    applications = loader.load_applications()

    nginx = next(
        application
        for application in applications
        if application.id == "nginx"
    )

    assert nginx.name == "NGINX"
    assert nginx.category == (
        "Web Server / Reverse Proxy"
    )
    assert "nginx" in nginx.images
    assert nginx.resources.cpu_cores == 1
    assert nginx.resources.ram_mb == 512