class ProviderActionError(RuntimeError):
    """Base exception for provider-action failures."""


class ProviderActionNotFoundError(ProviderActionError):
    """Raised when a provider does not advertise an action."""

    def __init__(self, provider_id: str, action_id: str) -> None:
        self.provider_id = provider_id
        self.action_id = action_id

        super().__init__(
            f"Provider '{provider_id}' does not advertise action "
            f"'{action_id}'."
        )


class ProviderActionDisabledError(ProviderActionError):
    """Raised when an advertised action is currently disabled."""

    def __init__(self, provider_id: str, action_id: str) -> None:
        self.provider_id = provider_id
        self.action_id = action_id

        super().__init__(
            f"Action '{action_id}' is disabled for provider "
            f"'{provider_id}'."
        )


class ProviderActionConfirmationRequiredError(ProviderActionError):
    """Raised when an action requires explicit confirmation."""

    def __init__(self, provider_id: str, action_id: str) -> None:
        self.provider_id = provider_id
        self.action_id = action_id

        super().__init__(
            f"Action '{action_id}' requires confirmation for provider "
            f"'{provider_id}'."
        )
