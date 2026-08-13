from collections.abc import Iterable

from app.providers.base import Provider


class ProviderAlreadyRegisteredError(ValueError):
    """Raised when a provider ID is registered more than once."""


class ProviderNotFoundError(KeyError):
    """Raised when a requested provider does not exist."""


class ProviderRegistry:
    """In-memory source of truth for registered Atlas providers."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, provider: Provider) -> None:
        provider_id = provider.metadata.id

        if provider_id in self._providers:
            raise ProviderAlreadyRegisteredError(
                f"Provider '{provider_id}' is already registered.",
            )

        self._providers[provider_id] = provider

    def replace(self, provider: Provider) -> None:
        """Atomically replace or insert one provider."""

        providers = dict(self._providers)
        providers[provider.metadata.id] = provider
        self._providers = providers

    def unregister(self, provider_id: str) -> Provider:
        providers = dict(self._providers)
        try:
            removed = providers.pop(provider_id)
        except KeyError as exc:
            raise ProviderNotFoundError(
                f"Provider '{provider_id}' is not registered.",
            ) from exc
        self._providers = providers
        return removed

    def get(self, provider_id: str) -> Provider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise ProviderNotFoundError(
                f"Provider '{provider_id}' is not registered.",
            ) from exc

    def contains(self, provider_id: str) -> bool:
        return provider_id in self._providers

    def all(self) -> tuple[Provider, ...]:
        return tuple(
            sorted(
                self._providers.values(),
                key=lambda provider: (
                    provider.metadata.workspace.value,
                    provider.metadata.priority.value,
                    provider.metadata.name.casefold(),
                ),
            ),
        )

    def register_many(
        self,
        providers: Iterable[Provider],
    ) -> None:
        for provider in providers:
            self.register(provider)

    def replace_all(
        self,
        providers: Iterable[Provider],
    ) -> None:
        """Atomically replace registry contents after duplicate validation."""

        replacement: dict[str, Provider] = {}
        for provider in providers:
            provider_id = provider.metadata.id
            if provider_id in replacement:
                raise ProviderAlreadyRegisteredError(
                    f"Provider '{provider_id}' is already registered.",
                )
            replacement[provider_id] = provider

        self._providers = replacement

    def clear(self) -> None:
        self._providers = {}

    def __len__(self) -> int:
        return len(self._providers)

    def ids(self) -> tuple[str, ...]:
        return tuple(self._providers.keys())


provider_registry = ProviderRegistry()
