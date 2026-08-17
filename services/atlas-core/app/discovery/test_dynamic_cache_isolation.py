from __future__ import annotations

import ast
from pathlib import Path


def test_cache_has_no_adapter_authority_application_or_recovery_coupling():
    path = Path(__file__).with_name("dynamic_cache.py")
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
        "httpx",
        "requests",
        "urlopen",
        "fetch",
    }
    assert not any(any(part in name.lower() for part in forbidden) for name in imports)
    assert not any(any(part in name.lower() for part in forbidden) for name in calls)


def test_cache_module_is_not_wired_into_application_modules():
    app_dir = Path(__file__).parents[1]
    references = []
    for path in app_dir.rglob("*.py"):
        if path.name in {
            "dynamic_cache.py",
            "dynamic_refresh.py",
            "test_dynamic_cache.py",
            "test_dynamic_evaluation_isolation.py",
            "test_dynamic_refresh.py",
            "test_dynamic_refresh_isolation.py",
            "test_dynamic_source_isolation.py",
            Path(__file__).name,
        }:
            continue
        if "dynamic_cache" in path.read_text(encoding="utf-8"):
            references.append(path.relative_to(app_dir).as_posix())
    assert references == []
