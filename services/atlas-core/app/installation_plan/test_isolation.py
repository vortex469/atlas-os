from __future__ import annotations

import ast
import asyncio
import builtins
import importlib
import importlib.abc
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI

from app.testing import ASGITestClient

APP = Path(__file__).parents[1]
ROOTS = (
    "app.routes.installation_plan",
)
FORBIDDEN = (
    "app.actions", "app.deploy", "app.planning", "app.application",
    "app.execution_candidates", "app.provider_intents", "app.operational_dispatch",
    "app.routes.analysis", "app.routes.execution_candidate_intake",
    "app.routes.execution_candidates", "app.routes.internal_operational_actions",
    "app.routes.provider_intent_mutation", "app.services.execution_candidate_intake",
    "app.services.execution_candidates", "app.core.restore_interlock",
    "app.discovery.image_release_collector", "app.discovery.image_release_collector_transport",
    "app.discovery.home_assistant_ghcr_acquisition",
    "app.discovery.home_assistant_sigstore_verifier", "app.routes.discovery",
    "app.services.discovery", "app.services.discovery_compatibility",
    "app.services.discovery_image_grounding", "app.services.home_assistant_image_grounding",
    "app.services.image_grounding_read_model",
    "app.services.home_assistant_image_evidence_provenance", "atlas_execution_worker",
    "app.approval", "app.repository", "app.workflow",
)


def _module_path(module: str) -> Path | None:
    if not module.startswith("app."):
        return None
    relative = module.removeprefix("app.").replace(".", "/")
    file_path = APP / f"{relative}.py"
    if file_path.is_file():
        return file_path
    init_path = APP / relative / "__init__.py"
    return init_path if init_path.is_file() else None


def _analyze_import_graph(roots: tuple[str, ...], resolver: object) -> set[str]:
    pending = list(roots)
    visited: set[str] = set()
    while pending:
        module = pending.pop()
        if module in visited:
            continue
        visited.add(module)
        path = resolver(module)  # type: ignore[operator]
        assert path is not None
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    package = module.split(".")[:-node.level]
                    suffix = tuple(node.module.split(".")) if node.module else ()
                    base = ".".join((*package, *suffix))
                    imports = [base]
                    imports.extend(
                        f"{base}.{alias.name}" for alias in node.names if alias.name != "*"
                    )
                else:
                    imports = [node.module or ""]
            else:
                imports = []
            for name in imports:
                assert not any(
                    name == prefix or name.startswith(prefix + ".")
                    for prefix in FORBIDDEN
                )
                if resolver(name) is not None:  # type: ignore[operator]
                    pending.append(name)
            assert not (
                isinstance(node, ast.Call)
                and (
                    isinstance(node.func, ast.Name)
                    and node.func.id in {"eval", "exec", "__import__"}
                    or isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"import_module", "exec_module"}
                )
            )
    return visited


def test_recursive_local_import_graph_has_no_forbidden_or_dynamic_imports() -> None:
    assert set(ROOTS) <= _analyze_import_graph(ROOTS, _module_path)


@pytest.mark.parametrize(
    ("root_source", "child_source"),
    [
        ("import app.actions", ""),
        ("import middle", "import app.actions"),
        ("__import__('safe')", ""),
        ("importlib.import_module('safe')", ""),
        ("eval('1')", ""),
        ("exec('pass')", ""),
        ("from . import actions", ""),
    ],
)
def test_import_graph_hostile_synthetic_cases(
    tmp_path: Path, root_source: str, child_source: str
) -> None:
    root_name = "pkg.root" if root_source.startswith("from .") else "root"
    files = {
        "root": tmp_path / "root.py", "middle": tmp_path / "middle.py",
        "pkg.root": tmp_path / "root.py", "pkg.actions": tmp_path / "actions.py",
    }
    files["root"].write_text(root_source)
    files["middle"].write_text(child_source)
    files["pkg.actions"].write_text("import app.actions")
    with pytest.raises(AssertionError):
        _analyze_import_graph((root_name,), files.get)


def test_runtime_side_effect_sentinels(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("side effect attempted")

    # Event-loop and ASGI transport construction may legitimately allocate an
    # internal wakeup socket.  Complete that framework setup before arming the
    # production request sentinels.
    event_loop = asyncio.new_event_loop()
    test_app = FastAPI()

    real_open = builtins.open

    def guarded_open(file: object, mode: str = "r", *args: object, **kwargs: object):
        if any(flag in mode for flag in "wax+"):
            forbidden()
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    real_os_open = os.open

    def guarded_os_open(path: object, flags: int, *args: object, **kwargs: object):
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        if flags & write_flags:
            forbidden()
        return real_os_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", guarded_os_open)
    real_socket = socket.socket
    monkeypatch.setattr(real_socket, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, forbidden)
    for method in ("write_text", "write_bytes", "touch", "mkdir", "unlink", "rename", "replace"):
        monkeypatch.setattr(Path, method, forbidden)

    class ForbiddenAuthorityFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname: str, path: object, target: object = None):
            if any(
                fullname == prefix or fullname.startswith(prefix + ".")
                for prefix in FORBIDDEN
            ):
                forbidden()

    finder = ForbiddenAuthorityFinder()
    monkeypatch.setattr(sys, "meta_path", [finder, *sys.meta_path])

    # Resolve first, then evict the complete production graph only after every
    # runtime sentinel is armed.  The following import therefore exercises
    # import-time as well as request-time reachability through fresh modules.
    scoped_graph = _analyze_import_graph(ROOTS, _module_path)
    for module_name in sorted(scoped_graph, key=lambda value: value.count("."), reverse=True):
        sys.modules.pop(module_name, None)
    route_module = importlib.import_module("app.routes.installation_plan")
    assembly = importlib.import_module("app.installation_plan.assembly")
    datetime_module = importlib.import_module("datetime")
    dependency = assembly.default_installation_plan_dependency(
        repository_root=Path("/opt/atlas"),
        clock=lambda: datetime_module.datetime(
            2026, 8, 25, tzinfo=datetime_module.UTC
        ),
    )

    # These authority families are unreachable from the transitive production
    # graph.  The import trap remains armed during a real assembly so a lazy
    # collector, persistence, approval, action, workflow, queue, repository,
    # dispatch, execution-candidate, Provider Intent, or worker import fails.
    visited = _analyze_import_graph(ROOTS, _module_path)
    assert visited == scoped_graph
    assert not {
        module for module in visited
        if any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN)
    }
    assert {
        "app.actions", "app.execution_candidates", "app.provider_intents",
        "app.operational_dispatch", "app.approval", "app.repository",
        "app.workflow", "atlas_execution_worker",
    } <= set(FORBIDDEN)

    monkeypatch.setattr(
        route_module,
        "get_installation_plan_read_dependency",
        lambda: dependency,
    )
    test_app.include_router(route_module.router, prefix="/api/v1")
    client = ASGITestClient(test_app)
    original_run = asyncio.run
    monkeypatch.setattr(asyncio, "run", event_loop.run_until_complete)
    try:
        response = client.get(
            "/api/v1/discovery/items/home-assistant/installation-plan"
        )
    finally:
        monkeypatch.setattr(asyncio, "run", original_run)
        event_loop.close()
    assert response.status_code == 200
    assert response.json()["application"]["item_id"] == "home-assistant"
