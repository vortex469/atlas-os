"""Model service that wraps a provider and default model."""

from ..model_providers.interface import ModelProvider
from ..model_providers.models import ModelResponse


class ModelService:
    """Service that wraps a model provider and default model."""

    def __init__(
        self,
        *,
        provider: ModelProvider,
        default_model: str,
    ) -> None:
        """Initialize the model service.

        Args:
            provider: The model provider to use
            default_model: The default model to use for generation
        """
        self._provider = provider
        self._default_model = default_model

    def generate(self, *, prompt: str) -> ModelResponse:
        """Generate a response using the configured provider and default model.

        Args:
            prompt: The prompt to send to the model

        Returns:
            ModelResponse from the provider
        """
        return self._provider.generate(
            model=self._default_model,
            prompt=prompt,
        )
