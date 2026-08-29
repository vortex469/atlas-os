"""Cross-service P4 locks for the deliberately absent v0.25 presentation."""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[4]
MISSION_CONTROL_ROOT = REPOSITORY_ROOT / "services" / "mission-control" / "src"
CORE_APP_ROOT = REPOSITORY_ROOT / "services" / "atlas-core" / "app"
ALLOWED_CORE_EVIDENCE_ROOTS = (
    CORE_APP_ROOT / "installation_handoff_simulated_delivery",
    CORE_APP_ROOT / "dormant_agent_intake_delivery_wiring",
    CORE_APP_ROOT / "delivery_activation_preflight",
)

V025_MARKERS = (
    "agent-intake-simulation",
    "agent_intake_simulation",
    "agent intake simulation",
    "agent-installation-intake-simulation",
    "agent_installation_intake_simulation",
    "intake_record_id",
)


def _production_sources(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.suffix in suffixes
        and ".test." not in path.name
        and not path.name.startswith("test_")
        and "__pycache__" not in path.parts
    ]


def test_core_and_mission_control_expose_no_v025_client_route_or_ui() -> None:
    roots = (
        (CORE_APP_ROOT, (".py",)),
        (MISSION_CONTROL_ROOT, (".ts", ".tsx")),
    )
    violations: list[str] = []

    for root, suffixes in roots:
        for path in _production_sources(root, suffixes):
            if any(allowed in path.parents for allowed in ALLOWED_CORE_EVIDENCE_ROOTS):
                continue
            if "deliveryactivationpreflight" in path.name.lower():
                continue
            source = path.read_text(encoding="utf-8").lower()
            for marker in V025_MARKERS:
                if marker in source:
                    violations.append(f"{path.relative_to(REPOSITORY_ROOT)} -> {marker}")

    assert violations == []


def test_home_assistant_has_no_deployment_artifact() -> None:
    assert not (REPOSITORY_ROOT / "compose" / "home-assistant.yaml").exists()
