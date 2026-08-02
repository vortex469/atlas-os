"""Development-only deterministic execution-candidate fixture.

The fixture emits a single fixed Orion finding when explicitly enabled.
It is intentionally constrained to a strict, deterministic shape and is
guarded behind environment flags to avoid production misuse.
"""

from __future__ import annotations

import os

from app.core.logging import get_logger
from app.intelligence.findings import Finding, Severity

logger = get_logger("atlas.development_fixture")


DEVELOPMENT_FIXTURE_ENABLED_ENV = "ATLAS_ENABLE_DEVELOPMENT_CANDIDATE_FIXTURE"
DEVELOPMENT_FIXTURE_ACK_ENV = "ATLAS_CONFIRM_DEVELOPMENT_CANDIDATE_FIXTURE"
ATLAS_ENVIRONMENT_ENV = "ATLAS_CORE_ENVIRONMENT"

DEVELOPMENT_FIXTURE_ID = "orion-dev-update-compose-stack"
DEVELOPMENT_FIXTURE_EVIDENCE_ID = "orion-development-evidence-0001"
DEVELOPMENT_FIXTURE_RECOMMENDATION_CLASS = "update_compose_stack"
DEVELOPMENT_FIXTURE_TARGET_ID = "atlas-compose"
DEVELOPMENT_FIXTURE_TARGET_TYPE = "repository"
DEVELOPMENT_FIXTURE_RATIONALE = "Validate Atlas Agent compose-stack planning with a deterministic fixture."


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def _is_development_environment() -> bool:
    environment = os.getenv(ATLAS_ENVIRONMENT_ENV, "").strip().lower()
    return environment in {
        "development",
        "dev",
        "test",
        "testing",
        "local",
    }


def is_fixture_enabled() -> bool:
    """Return whether the fixture is explicitly enabled."""

    return _env_bool(DEVELOPMENT_FIXTURE_ENABLED_ENV, default=False)


def fixture_evidence_ids() -> tuple[str, ...]:
    """Return deterministic evidence IDs used by the fixture."""

    if not is_fixture_enabled():
        return ()
    return (DEVELOPMENT_FIXTURE_EVIDENCE_ID,)


def development_fixture_enabled_and_validated() -> None:
    """Validate production-safety gating for the development fixture.

    The fixture must be explicitly disabled unless enabled in a development/test
    environment or with a second acknowledgement flag.
    """

    if not is_fixture_enabled():
        return

    if not _is_development_environment() and not _env_bool(
        DEVELOPMENT_FIXTURE_ACK_ENV,
        default=False,
    ):
        raise RuntimeError(
            "Development execution-candidate fixture is blocked in this environment. "
            "Set ATLAS_CONFIRM_DEVELOPMENT_CANDIDATE_FIXTURE=true to enable "
            "only intentionally and with explicit acknowledgement."
        )

    logger.warning(
        "Development execution-candidate fixture is enabled; synthetic findings "
        "will be included in candidate collection."
    )


def collect_development_candidate_findings() -> tuple[Finding, ...]:
    """Return a deterministic synthetic finding when development fixture is enabled."""

    if not is_fixture_enabled():
        return ()

    return (
        Finding(
            id=DEVELOPMENT_FIXTURE_ID,
            severity=Severity.INFO,
            category="development",
            source="orion",
            title="Update Atlas compose stack",
            message=DEVELOPMENT_FIXTURE_RATIONALE,
            recommendation="Generate a deterministic compose-stack candidate for development exercise.",
            component="atlas-core",
            details={
                "source_subsystem": "orion",
                "recommendation_class": DEVELOPMENT_FIXTURE_RECOMMENDATION_CLASS,
                "target_id": DEVELOPMENT_FIXTURE_TARGET_ID,
                "target_type": DEVELOPMENT_FIXTURE_TARGET_TYPE,
                "evidence_ids": fixture_evidence_ids(),
            },
            affects_health=False,
            score_penalty=0,
        ),
    )
