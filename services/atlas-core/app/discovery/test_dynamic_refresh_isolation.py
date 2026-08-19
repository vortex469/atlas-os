from __future__ import annotations

import ast
from pathlib import Path


def test_refresh_has_no_direct_filesystem_clock_route_or_authority_coupling():
    path = Path(__file__).with_name("dynamic_refresh.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
            elif isinstance(node.func, ast.Name):
                calls.add(node.func.id)
    forbidden_imports = {
        "pathlib",
        "os",
        "socket",
        "httpx",
        "requests",
        "routes",
        "startup",
        "providers",
        "provider_intents",
        "operational",
        "execution",
        "planning",
        "approvals",
        "proposals",
        "backup",
        "restore",
        "recovery",
        "mission_control",
    }
    forbidden_calls = {
        "open",
        "read_text",
        "write_text",
        "unlink",
        "replace",
        "rename",
        "chmod",
        "chown",
        "initialize",
        "now",
        "utcnow",
    }
    assert not any(
        any(part in name.lower() for part in forbidden_imports) for name in imports
    )
    assert not (calls & forbidden_calls)
    assert "datetime.now" not in source
    assert "/opt/atlas/data/cache/discovery" not in source


def test_refresh_module_is_not_wired_into_application_modules():
    app_dir = Path(__file__).parents[1]
    references = []
    for path in app_dir.rglob("*.py"):
        if path.name in {
            "dynamic_refresh.py",
            "test_dynamic_cache_isolation.py",
            "test_dynamic_evaluation_isolation.py",
            "test_dynamic_projection_isolation.py",
            "test_dynamic_refresh.py",
            "test_dynamic_source_isolation.py",
            "test_discovery_evidence.py",
            "test_discovery_evidence_isolation.py",
            Path(__file__).name,
        }:
            continue
        if "dynamic_refresh" in path.read_text(encoding="utf-8"):
            references.append(path.relative_to(app_dir).as_posix())
    assert references == ["services/discovery_dynamic_activation.py"]
