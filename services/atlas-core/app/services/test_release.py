from app.api.v1.router import api_discovery
from app.config.settings import settings
from app.main import root as root_status
from app.routes.status import root as legacy_status
from app.services import summary_service


def test_release_identifier_comes_from_settings(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        summary_service,
        "get_health",
        dict,
    )
    monkeypatch.setattr(
        summary_service,
        "get_system_status",
        dict,
    )
    monkeypatch.setattr(
        summary_service,
        "get_docker_status",
        dict,
    )
    monkeypatch.setattr(
        summary_service,
        "get_proxmox_status",
        dict,
    )
    monkeypatch.setattr(
        summary_service,
        "get_proxmox_guests",
        dict,
    )
    monkeypatch.setattr(
        summary_service,
        "get_homeassistant_status",
        dict,
    )

    expected = settings.atlas.release

    assert expected == "Foundry"
    assert api_discovery().release == expected
    assert root_status()["release"] == expected
    assert legacy_status()["release"] == expected
    assert summary_service.get_ops_summary()["release"] == expected
