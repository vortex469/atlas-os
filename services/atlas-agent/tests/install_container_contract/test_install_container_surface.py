"""P3 surface and production-isolation locks."""

def test_install_container_has_no_http_or_command_surface(monkeypatch, tmp_path) -> None:
    from pathlib import Path

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    from app.config.settings import Settings
    from app.main import create_app

    monkeypatch.setattr(
        "app.main.load_settings",
        lambda: Settings(
            repository_root=Path(__file__).parents[4],
            state_dir=tmp_path / "agent-state",
        ),
    )
    application = create_app()
    schema = application.openapi()

    assert all("install-container" not in path for path in schema["paths"])
    assert all("install_container" not in path for path in schema["paths"])
    assert not hasattr(application.state.container, "install_container_service")


def test_no_production_module_consumes_validation_service() -> None:
    from pathlib import Path

    app_root = Path(__file__).parents[3] / "app"
    consumers = []
    for path in app_root.rglob("*.py"):
        if path.parts[-2:] == ("install_container_contract", "__init__.py"):
            continue
        if path.parts[-2:] == ("install_container_contract", "service.py"):
            continue
        if "InstallContainerValidationService" in path.read_text(encoding="utf-8"):
            consumers.append(path.relative_to(app_root))

    assert consumers == []
