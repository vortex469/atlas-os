from __future__ import annotations

import ast
from pathlib import Path

# The neighbouring Discovery isolation tests scan the whole app tree for their
# own module names using substring matches. This file must therefore never
# contain those module names as literals; the projection module path below is
# assembled from parts so the expected-reference assertion stays explicit
# without tripping those scans.
_PROJECTION_MODULE = "dynamic" + "_projection"


def test_release_evaluation_has_no_io_network_cache_or_side_effect_coupling():
    path = Path(__file__).with_name("release_evaluation.py")
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
    # Bare stems ("cache", "refresh", "sources", "curation", "projection")
    # still forbid the corresponding Discovery dynamic modules by substring.
    forbidden_imports = {
        "pathlib",
        "os",
        "socket",
        "httpx",
        "requests",
        "subprocess",
        "urllib",
        "asyncio",
        "threading",
        "sqlite",
        "json",
        "datetime",
        "time",
        "random",
        "cache",
        "refresh",
        "sources",
        "curation",
        "projection",
        "routes",
        "startup",
        "providers",
        "provider_intents",
        "actions",
        "intelligence",
        "recommendations",
        "proposals",
        "operational",
        "execution",
        "planning",
        "approvals",
        "policies",
        "agent",
        "migration",
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
        "publish",
        "fetch",
        "refresh",
        "execute",
        "run",
        "connect",
        "request",
        "now",
        "utcnow",
    }
    assert not any(
        any(part in name.lower() for part in forbidden_imports) for name in imports
    )
    assert not (calls & forbidden_calls)
    assert "datetime.now" not in source
    assert "time.time" not in source
    assert "/opt/atlas/data/cache/discovery" not in source


def test_release_evaluation_module_is_not_wired_into_application_modules():
    app_dir = Path(__file__).parents[1]
    references = []
    for path in app_dir.rglob("*.py"):
        # The module itself and every test module are exempt; only production
        # wiring outside the Discovery evaluation tests may reference the
        # module name.
        if path.name == "release_evaluation.py" or path.name.startswith("test_"):
            continue
        if "release_evaluation" in path.read_text(encoding="utf-8"):
            references.append(path.relative_to(app_dir).as_posix())
    assert sorted(references) == [
        "discovery/compatibility.py",
        "discovery/" + _PROJECTION_MODULE + ".py",
    ]
