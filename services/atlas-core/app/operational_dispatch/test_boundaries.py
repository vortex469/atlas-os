from pathlib import Path


def test_dispatch_foundations_have_no_mutation_or_execution_dependencies() -> None:
    directory = Path(__file__).parent
    production_sources = "\n".join(
        (directory / name).read_text(encoding="utf-8")
        for name in (
            "ledger.py",
            "models.py",
            "registry.py",
            "service.py",
            "verification.py",
        )
    )
    for forbidden in (
        "app.actions",
        "app.execution",
        "app.providers.proxmox",
        "execute_action(",
        "subprocess",
        "update_provider_resource_expectation",
        "var/run/docker.sock",
    ):
        assert forbidden not in production_sources


def test_no_operational_dispatch_http_route_exists_without_service_auth() -> None:
    routes = Path(__file__).parents[1] / "routes"
    assert not (routes / "operational_dispatch.py").exists()
