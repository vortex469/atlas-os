from __future__ import annotations

import ast
from pathlib import Path


def test_dynamic_source_has_no_authority_persistence_or_activation_coupling():
    path = Path(__file__).with_name("dynamic_sources.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    forbidden = {
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
        "routes",
        "cache",
        "database",
        "sqlite",
    }
    assert not any(any(part in name.lower() for part in forbidden) for name in imports)


def test_dynamic_source_is_not_wired_into_application_modules():
    app_dir = Path(__file__).parents[1]
    references = []
    for path in app_dir.rglob("*.py"):
        if path.name in {
            "dynamic_cache.py",
            "dynamic_evaluation.py",
            "dynamic_projection.py",
            "dynamic_refresh.py",
            "dynamic_sources.py",
            "test_dynamic_cache.py",
            "test_dynamic_cache_isolation.py",
            "test_dynamic_evaluation.py",
            "test_dynamic_evaluation_isolation.py",
            "test_dynamic_projection.py",
            "test_dynamic_projection_isolation.py",
            "test_dynamic_refresh.py",
            "test_dynamic_refresh_isolation.py",
            "test_dynamic_sources.py",
            "test_discovery_evidence.py",
            "test_discovery_evidence_isolation.py",
            Path(__file__).name,
        }:
            continue
        if "dynamic_sources" in path.read_text(encoding="utf-8"):
            references.append(path.relative_to(app_dir).as_posix())
    assert references == []
