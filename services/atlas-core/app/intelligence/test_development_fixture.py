from __future__ import annotations

import pytest

from app.intelligence import development_fixture as fixture


def test_development_fixture_validation_blocks_production_when_disabled_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_ENABLE_DEVELOPMENT_CANDIDATE_FIXTURE", "true")
    monkeypatch.setenv("ATLAS_CORE_ENVIRONMENT", "production")
    monkeypatch.delenv("ATLAS_CONFIRM_DEVELOPMENT_CANDIDATE_FIXTURE", raising=False)

    with pytest.raises(RuntimeError):
        fixture.development_fixture_enabled_and_validated()


def test_development_fixture_validation_allows_development_without_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_ENABLE_DEVELOPMENT_CANDIDATE_FIXTURE", "true")
    monkeypatch.setenv("ATLAS_CORE_ENVIRONMENT", "development")
    monkeypatch.delenv("ATLAS_CONFIRM_DEVELOPMENT_CANDIDATE_FIXTURE", raising=False)

    fixture.development_fixture_enabled_and_validated()


def test_development_fixture_validation_allows_prod_with_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_ENABLE_DEVELOPMENT_CANDIDATE_FIXTURE", "true")
    monkeypatch.setenv("ATLAS_CORE_ENVIRONMENT", "production")
    monkeypatch.setenv("ATLAS_CONFIRM_DEVELOPMENT_CANDIDATE_FIXTURE", "true")

    fixture.development_fixture_enabled_and_validated()

