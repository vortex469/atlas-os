from __future__ import annotations

from collections.abc import Mapping

from app.context import MetadataContext, SecretContext

_SECRET_ENVIRONMENT: dict[str, dict[str, str]] = {
    "proxmox": {
        "user": "PROXMOX_USER",
        "token_name": "PROXMOX_TOKEN_NAME",
        "token_value": "PROXMOX_TOKEN_VALUE",
    },
    "home_assistant": {
        "token": "HASS_TOKEN",
    },
    "opnsense": {
        "api_key": "OPNSENSE_API_KEY",
        "api_secret": "OPNSENSE_API_SECRET",
    },
    "frigate": {
        "api_token": "FRIGATE_API_TOKEN",
    },
    "n8n": {
        "api_key": "N8N_API_KEY",
    },
    "qdrant": {
        "api_key": "QDRANT_API_KEY",
    },
}


class SecretContextResolver:
    """Resolve Atlas secret contexts from runtime placeholders or env vars."""

    def __init__(
        self,
        environ: Mapping[str, str] | None = None,
        runtime_secrets: Mapping[str, Mapping[str, str]] | None = None,
    ) -> None:
        self._environ = environ
        self._runtime_secrets = runtime_secrets or {}

    def resolve_secrets(
        self,
        metadata: MetadataContext,
    ) -> Mapping[str, SecretContext]:
        schema = _SECRET_ENVIRONMENT.get(metadata.consumer_id, {})
        return {
            name: self._resolve_secret(metadata.consumer_id, name, variable)
            for name, variable in schema.items()
        }

    def _resolve_secret(
        self,
        provider_id: str,
        name: str,
        variable: str,
    ) -> SecretContext:
        runtime_value = self._runtime_secrets.get(provider_id, {}).get(name)
        if runtime_value:
            return SecretContext(
                name=name,
                source="runtime",
                configured=True,
                redacted="********",
                value=runtime_value,
            )

        value = self._environment().get(variable)
        if value:
            return SecretContext(
                name=name,
                source="environment",
                configured=True,
                redacted="********",
                value=value,
            )

        return SecretContext(
            name=name,
            source="missing",
            configured=False,
            redacted=None,
        )

    def _environment(self) -> Mapping[str, str]:
        if self._environ is not None:
            return self._environ

        import os

        return os.environ


def secret_names_for_provider(provider_id: str) -> tuple[str, ...]:
    """Return logical secret names expected for one provider."""

    return tuple(_SECRET_ENVIRONMENT.get(provider_id, {}))
