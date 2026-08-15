"""Fail-closed Provider Intent activation validation for Core startup."""

from __future__ import annotations

import os
from pathlib import Path

from app.config.settings import ProviderIntentActivation, ProviderIntentSettings
from app.provider_intents.legacy_import import load_legacy_policy_import
from app.provider_intents.store import (
    ProviderIntentStore,
)


class ProviderIntentActivationError(RuntimeError):
    """Activation configuration and durable state do not agree."""


def validate_provider_intent_activation(
    settings: ProviderIntentSettings,
    *,
    policy_path: Path = Path("/opt/atlas/data/config/policies.yaml"),
) -> ProviderIntentStore | None:
    """Validate the configured startup authority without mutating durable state."""

    database = Path(settings.database)
    if settings.activation is ProviderIntentActivation.NOT_ACTIVATED:
        if os.path.lexists(database):
            raise ProviderIntentActivationError(
                "inactive Provider Intent configuration contradicts managed store"
            )
        return None

    try:
        store = ProviderIntentStore.open_existing(database)
        expected_import = load_legacy_policy_import(policy_path)
        if expected_import.import_id != settings.expected_legacy_import_id:
            raise ProviderIntentActivationError(
                "configured legacy import ID does not match the validated policy"
            )
        if store.get_import_completion(expected_import) is None:
            raise ProviderIntentActivationError(
                "configured legacy import completion evidence is missing"
            )
        return store
    except ProviderIntentActivationError:
        raise
    except (OSError, TypeError, ValueError, RuntimeError) as error:
        raise ProviderIntentActivationError(
            "activated Provider Intent state failed validation"
        ) from error
