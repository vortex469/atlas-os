"""Fail-closed Provider Intent activation validation for Core startup."""

from __future__ import annotations

import os
from pathlib import Path

from app.config.settings import ProviderIntentActivation, ProviderIntentSettings
from app.provider_intents.legacy_import import (
    ActivatedProviderIntentImportCompletionError,
    ActivatedProviderIntentImportMismatchError,
    validate_activated_provider_intent_store,
)
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
        assert settings.expected_legacy_import_id is not None
        return validate_activated_provider_intent_store(
            database,
            policy_path,
            settings.expected_legacy_import_id,
        )
    except ActivatedProviderIntentImportMismatchError as error:
        raise ProviderIntentActivationError(
            "configured legacy import ID does not match the validated policy"
        ) from error
    except ActivatedProviderIntentImportCompletionError as error:
        raise ProviderIntentActivationError(
            "configured legacy import completion evidence is missing"
        ) from error
    except ProviderIntentActivationError:
        raise
    except (OSError, TypeError, ValueError, RuntimeError) as error:
        raise ProviderIntentActivationError(
            "activated Provider Intent state failed validation"
        ) from error
