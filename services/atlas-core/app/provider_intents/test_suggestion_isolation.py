from __future__ import annotations

import ast
from pathlib import Path

SUGGESTION_MODULES = (
    Path(__file__).parents[1] / "models/provider_intent_suggestions.py",
    Path(__file__).with_name("suggestions.py"),
    Path(__file__).parents[1] / "routes/provider_intent_suggestions.py",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "app.actions",
    "app.approvals",
    "app.discovery",
    "app.execution_candidates",
    "app.intelligence.findings",
    "app.operational_dispatch",
    "app.planning",
    "app.provider_intents.migration",
    "app.provider_intents.mutation",
    "app.routes.provider_intent_mutation",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_suggestion_modules_have_no_mutation_execution_or_proposal_dependencies() -> None:
    for path in SUGGESTION_MODULES:
        imports = _imports(path)
        assert not {
            module
            for module in imports
            if module.startswith(FORBIDDEN_IMPORT_PREFIXES)
        }, path


def test_projector_does_not_parse_ace_or_legacy_policy_payloads() -> None:
    source = SUGGESTION_MODULES[1].read_text(encoding="utf-8")
    for forbidden in (
        "recommendation",
        ".metric",
        ".details",
        "intent_hint",
        "DiscoveryProposal",
        "policies.yaml",
        "POLICY_FILE",
        "legacy_expectation.value",
    ):
        assert forbidden not in source
