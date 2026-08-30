"""Atlas v0.36 must add no Agent admission consumer or deployment artifact."""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[3]
AGENT_APP = REPOSITORY_ROOT / "services" / "atlas-agent" / "app"


def test_agent_has_no_v036_admission_consumer() -> None:
    markers = (
        "installation_execution_admission",
        "InstallationExecutionAdmissionV1",
        "installation-execution-admission-v1",
        "execution-admissions",
    )
    violations = [
        f"{path.relative_to(REPOSITORY_ROOT)} -> {marker}"
        for path in AGENT_APP.rglob("*.py")
        if "__pycache__" not in path.parts
        for marker in markers
        if marker in path.read_text(encoding="utf-8")
    ]
    assert violations == []


def test_agent_has_no_home_assistant_install_or_deployment_artifact() -> None:
    artifacts = [
        path.relative_to(REPOSITORY_ROOT)
        for root in (REPOSITORY_ROOT / "compose", REPOSITORY_ROOT / "deploy")
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
        and "home-assistant" in path.name.lower()
        and path.suffix.lower() in {".yaml", ".yml", ".json", ".toml"}
    ]
    assert artifacts == []
