from __future__ import annotations

import ast
from pathlib import Path


def test_evaluation_has_no_io_network_cache_authority_or_application_coupling():
    path = Path(__file__).with_name("dynamic_evaluation.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
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
    forbidden = {
        "pathlib",
        "os",
        "open",
        "write",
        "unlink",
        "replace",
        "rename",
        "dynamic_cache",
        "publish",
        "fetch",
        "httpx",
        "requests",
        "socket",
        "routes",
        "startup",
        "lifespan",
        "provider_intents",
        "providers",
        "operational",
        "execution",
        "candidates",
        "planning",
        "approvals",
        "policies",
        "proposals",
        "agent",
        "migration",
        "backup",
        "restore",
        "recovery",
        "mission_control",
        "utcnow",
    }
    assert not any(any(part in name.lower() for part in forbidden) for name in imports)
    assert not any(any(part in name.lower() for part in forbidden) for name in calls)
    source = path.read_text(encoding="utf-8")
    assert "datetime.now" not in source


def test_evaluation_module_is_not_wired_into_application_modules():
    app_dir = Path(__file__).parents[1]
    references = []
    for path in app_dir.rglob("*.py"):
        if path.name in {
            "dynamic_evaluation.py",
            "dynamic_projection.py",
            "dynamic_refresh.py",
            "test_dynamic_cache_isolation.py",
            "test_dynamic_evaluation.py",
            "test_dynamic_projection.py",
            "test_dynamic_projection_isolation.py",
            "test_dynamic_refresh.py",
            "test_dynamic_refresh_isolation.py",
            "test_dynamic_source_isolation.py",
            "test_discovery_evidence.py",
            "test_discovery_evidence_isolation.py",
            Path(__file__).name,
        }:
            continue
        if "dynamic_evaluation" in path.read_text(encoding="utf-8"):
            references.append(path.relative_to(app_dir).as_posix())
    assert references == []
