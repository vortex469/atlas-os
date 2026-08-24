from __future__ import annotations

import ast
import importlib
from pathlib import Path

from app.discovery import image_grounding_projection as projection_module
from app.discovery.image_grounding import ImageGroundingResult, ImageGroundingStatus
from app.discovery.models import CatalogProvenance
from app.main import app
from app.routes import discovery as route_module
from app.services import discovery_image_grounding as dependency_module
from app.services.discovery_image_grounding import ImageGroundingReadModel
from app.testing import ASGITestClient

PATH = "/api/v1/discovery/items/frigate/image-grounding"
client = ASGITestClient(app)


def minimal_model() -> ImageGroundingReadModel:
    return ImageGroundingReadModel(
        grounding=ImageGroundingResult(
            status=ImageGroundingStatus.NO_DEPLOYMENT_BINDING,
            catalog_item_id="frigate",
            reason="internal",
        ),
        catalog_provenance=CatalogProvenance(source="internal"),
    )


def test_dependency_construction_is_inert_and_uses_fixed_absolute_root(
    monkeypatch,
) -> None:
    calls = []

    class Service:
        def __init__(self, root):
            calls.append(root)

    monkeypatch.setattr(
        dependency_module,
        "BindingDrivenImageGroundingService",
        Service,
    )
    service = dependency_module.get_discovery_image_grounding_service()
    assert isinstance(service, Service)
    assert calls == [dependency_module.ATLAS_ROOT]
    assert dependency_module.ATLAS_ROOT == Path("/opt/atlas")
    assert dependency_module.ATLAS_ROOT.is_absolute()


def test_get_calls_p1_exactly_once(monkeypatch) -> None:
    calls = []

    class Service:
        def get(self, item_id):
            calls.append(item_id)
            return minimal_model()

    monkeypatch.setattr(
        route_module,
        "get_discovery_image_grounding_service",
        Service,
    )
    assert client.get(PATH).status_code == 200
    assert calls == ["frigate"]


def test_get_does_not_write_files_or_start_forbidden_work(
    monkeypatch, tmp_path
) -> None:
    compose = tmp_path / "compose/home-assistant.yaml"
    compose.parent.mkdir()
    compose.write_text(
        "services:\n"
        "  home-assistant:\n"
        "    image: ghcr.io/home-assistant/home-assistant@"
        "sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe\n",
        encoding="utf-8",
    )

    def snapshot(root: Path) -> dict[str, tuple[bytes, int, int]]:
        return {
            str(path.relative_to(root)): (
                path.read_bytes(),
                path.stat().st_mode,
                path.stat().st_mtime_ns,
            )
            for path in root.rglob("*")
            if path.is_file()
        }

    before = snapshot(tmp_path)
    forbidden_calls = []
    reader_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append((args, kwargs))
        raise AssertionError("forbidden request-time side effect")

    ghcr_prefix = "app.discovery.home_assistant_ghcr_"
    sigstore_prefix = "app.discovery.home_assistant_sigstore_"
    verify_prefix = "verify_home_assistant_"
    collector_prefix = "app.discovery.image_release_"
    ghcr_acquire = f"{ghcr_prefix}acquisition._HomeAssistantGHCRAcquirer.acquire"
    sigstore_verify = f"{sigstore_prefix}verifier.{verify_prefix}2026_8_3_bundle"
    collector_collect = f"{collector_prefix}collector.ImageReleaseCollector.collect"
    collector_collect_async = (
        f"{collector_prefix}collector.ImageReleaseCollector.collect_async"
    )
    service_globals = (
        dependency_module.BindingDrivenImageGroundingService.get.__globals__
    )
    catalog_loader = service_globals["YamlCatalogLoader"]
    evidence_loader = service_globals["ImageReleaseEvidenceLoader"]
    compose_observer = service_globals["RepositoryComposeImageObservationAcquirer"]
    original_catalog_load = catalog_loader.load
    original_evidence_load = evidence_loader.load
    original_compose_observe = compose_observer.observe

    def track_reader(name, reader):
        def tracked(*args, **kwargs):
            reader_calls.append(name)
            return reader(*args, **kwargs)

        return tracked

    monkeypatch.setattr(
        catalog_loader,
        "load",
        track_reader("catalog", original_catalog_load),
    )
    monkeypatch.setattr(
        evidence_loader,
        "load",
        track_reader("accepted-evidence", original_evidence_load),
    )
    monkeypatch.setattr(
        compose_observer,
        "observe",
        track_reader("compose-observer", original_compose_observe),
    )
    for target in (
        "subprocess.run",
        "subprocess.Popen",
        "httpx.get",
        "httpx.post",
        "socket.socket.connect",
        ghcr_acquire,
        sigstore_verify,
        collector_collect,
        collector_collect_async,
    ):
        monkeypatch.setattr(target, forbidden)
    for target in (
        "pathlib.Path.write_bytes",
        "pathlib.Path.write_text",
        "os.replace",
        "os.rename",
    ):
        monkeypatch.setattr(target, forbidden)
    monkeypatch.setattr(dependency_module, "ATLAS_ROOT", tmp_path)
    monkeypatch.setattr(
        route_module,
        "get_discovery_image_grounding_service",
        dependency_module.get_discovery_image_grounding_service,
    )
    assert client.get(PATH.replace("frigate", "home-assistant")).status_code == 200
    assert forbidden_calls == []
    assert reader_calls == ["accepted-evidence", "catalog", "compose-observer"]
    assert snapshot(tmp_path) == before


def test_p2_module_imports_do_not_invoke_local_readers(monkeypatch) -> None:
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("import-time I/O")

    service_globals = (
        dependency_module.BindingDrivenImageGroundingService.get.__globals__
    )
    monkeypatch.setattr(service_globals["YamlCatalogLoader"], "load", forbidden)
    monkeypatch.setattr(
        service_globals["ImageReleaseEvidenceLoader"], "load", forbidden
    )
    monkeypatch.setattr(
        service_globals["RepositoryComposeImageObservationAcquirer"],
        "observe",
        forbidden,
    )

    importlib.reload(dependency_module)
    importlib.reload(projection_module)

    assert calls == []
    dependency_module.get_discovery_image_grounding_service()
    assert calls == []


def test_p2_modules_have_only_reviewed_import_surface() -> None:
    root = Path(__file__).parents[1]
    paths = (
        root / "routes/discovery.py",
        root / "services/discovery_image_grounding.py",
        root / "discovery/image_grounding_projection.py",
    )
    forbidden = (
        "agent",
        "provider",
        "proposal",
        "candidate",
        "workflow",
        "approval",
        "dispatch",
        "execution",
        "backup",
        "restore",
        "collector",
        "acquisition",
        "verifier",
        "home_assistant_" + "image_grounding",
    )
    new_modules = paths[1:]
    for path in new_modules:
        imports = []
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
        assert not any(marker in name for marker in forbidden for name in imports)


def test_route_has_no_startup_or_lifespan_wiring() -> None:
    source = Path(route_module.__file__).read_text(encoding="utf-8")
    assert "on_event" not in source
    assert "lifespan" not in source
