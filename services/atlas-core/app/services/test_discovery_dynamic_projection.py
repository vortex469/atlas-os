from app.discovery.dynamic_curation import CatalogCuratedReleaseClaimProvider
from app.discovery.dynamic_health import DynamicSourceHealthRegistry
from app.discovery.dynamic_sources import FRIGATE_ADAPTER_ID, DynamicSourceHealth
from app.services import discovery_dynamic_projection as production
from app.services.discovery import get_discovery_service


def test_production_projection_wires_read_only_health_and_curated_claim_providers(
    monkeypatch,
    tmp_path,
) -> None:
    registry = DynamicSourceHealthRegistry()
    monkeypatch.setattr(production, "DISCOVERY_CACHE_ROOT", tmp_path / "cache")
    monkeypatch.setattr(production, "dynamic_source_health_registry", registry)

    service = production.get_discovery_projection_service()

    assert service._health_provider is registry
    assert isinstance(
        service._curated_claim_provider,
        CatalogCuratedReleaseClaimProvider,
    )
    assert service._curated_claim_provider._catalog is get_discovery_service()
    assert service._read_health(FRIGATE_ADAPTER_ID) is None
    registry.record(FRIGATE_ADAPTER_ID, DynamicSourceHealth.UNAVAILABLE)
    assert (
        service._read_health(FRIGATE_ADAPTER_ID)
        is DynamicSourceHealth.UNAVAILABLE
    )
    assert service._read_curated_claim("frigate") is None
