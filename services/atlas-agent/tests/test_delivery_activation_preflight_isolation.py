"""Release-wide Agent isolation locks for Atlas v0.29."""

from __future__ import annotations

from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1] / "app"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_agent_has_no_delivery_activation_preflight_consumer_or_registration() -> None:
    markers = (
        "delivery_activation_preflight",
        "delivery-activation-preflight",
        "DeliveryActivationPreflight",
        "core_delivery_activation_preflight_v1",
        "eligible_for_later_activation",
    )
    assert [
        f"{path.relative_to(REPOSITORY_ROOT)} -> {marker}"
        for path in AGENT_ROOT.rglob("*.py")
        for marker in markers
        if marker in path.read_text(encoding="utf-8")
    ] == []


def test_agent_capabilities_and_home_assistant_remain_unchanged() -> None:
    candidate_source = (AGENT_ROOT / "candidate_planning" / "models.py").read_text(encoding="utf-8")
    status_source = (AGENT_ROOT / "routes" / "status.py").read_text(encoding="utf-8")
    assert 'SUPPORTED_EXECUTION_INTENTS = frozenset({"update-compose-stack"})' in candidate_source
    assert 'OPERATIONAL_EXECUTION_INTENTS = frozenset({"restart-service"})' in candidate_source
    assert "install-container" not in candidate_source
    assert 'capability_status: Literal["unsupported"]' in status_source
    assert [
        path.relative_to(REPOSITORY_ROOT)
        for root in (REPOSITORY_ROOT / "compose", REPOSITORY_ROOT / "deploy")
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
        and "home-assistant" in path.name.lower()
        and path.suffix.lower() in {".yaml", ".yml", ".json", ".toml"}
    ] == []
