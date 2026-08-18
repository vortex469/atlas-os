from __future__ import annotations

import ast
from pathlib import Path

ROUTE = Path(__file__).with_name("discovery.py")
DEPENDENCY = Path(__file__).parents[1] / "services" / "discovery_dynamic_projection.py"


def test_evidence_route_has_no_authority_or_side_effect_dependencies() -> None:
    source = ROUTE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = {
        "provider_intents",
        "policies",
        "provider_actions",
        "operational_dispatch",
        "execution_candidates",
        "planning",
        "approvals",
        "agents",
        "backup",
        "restore",
        "recovery",
        "dynamic_refresh",
        "dynamic_sources",
    }
    assert not any(token in name for name in imports for token in forbidden)


def test_route_and_dependency_construction_are_read_only() -> None:
    route_source = ROUTE.read_text(encoding="utf-8")
    dependency_source = DEPENDENCY.read_text(encoding="utf-8")
    forbidden_route_tokens = (
        ".initialize(",
        ".publish(",
        ".refresh(",
        ".fetch(",
        "open(",
        "os.open",
        ".rename(",
        ".unlink(",
        ".chmod(",
        ".chown(",
        "flock",
    )
    assert not any(token in route_source for token in forbidden_route_tokens)
    assert "datetime.now(UTC)" in dependency_source
    assert "DiscoveryCacheStore(DISCOVERY_CACHE_ROOT)" in dependency_source
    assert not any(
        token in dependency_source
        for token in (".initialize(", ".publish(", ".refresh(", ".fetch(")
    )


def test_production_mapping_and_cache_root_remain_fixed() -> None:
    projection = (ROUTE.parents[1] / "discovery" / "dynamic_projection.py").read_text(
        encoding="utf-8"
    )
    dependency = DEPENDENCY.read_text(encoding="utf-8")
    assert '{"frigate": (FRIGATE_ADAPTER_ID,)}' in projection
    assert 'Path("/opt/atlas/data/cache/discovery")' in dependency
    assert "Query(" not in dependency
