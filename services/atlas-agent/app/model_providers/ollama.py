"""Ollama model provider implementation."""


import httpx

from .models import ModelResponse


class OllamaProviderError(RuntimeError):
    """Raised when Ollama generation fails."""


class OllamaProvider:
    """Ollama model provider implementation."""

    def __init__(self, base_url: str, timeout_seconds: float = 10.0):
        """Initialize the Ollama provider.

        Args:
            base_url: The base URL of the Ollama service
            timeout_seconds: The timeout for requests in seconds
        """
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    @property
    def provider_id(self) -> str:
        """Get the provider identifier."""
        return "ollama"

    def health_check(self) -> bool:
        """Check if the Ollama service is healthy.

        Returns:
            True if the service is healthy, False otherwise
        """
        try:
            # Create a new client for each request and close it immediately
            with httpx.Client() as client:
                response = client.get(
                    f"{self._base_url}/api/version",
                    timeout=self._timeout_seconds,
                )
            return response.status_code == 200
        except httpx.RequestError:
            # Catch only the specific HTTP client exception
            return False

    def generate(
        self,
        *,
        model: str,
        prompt: str,
    ) -> ModelResponse:
        """Generate a response using the Ollama API.

        Args:
            model: The model to use for generation
            prompt: The prompt to send to the model

        Returns:
            ModelResponse containing the generated text, model name, and provider ID

        Raises:
            OllamaProviderError: If the generation fails
        """
        try:
            # Create a new client for each request and close it immediately
            with httpx.Client() as client:
                response = client.post(
                    f"{self._base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                    },
                    timeout=self._timeout_seconds,
                )

            # Check if the request was successful
            response.raise_for_status()

            # Parse the JSON response
            data = response.json()

            # Validate that the payload is a dict
            if not isinstance(data, dict):
                raise OllamaProviderError("Response must be a dictionary")

            # Extract text from the response
            text = data.get("response")

            # Validate response field
            if not isinstance(text, str):
                raise OllamaProviderError("Response must be a non-empty string")

            if not text:
                raise OllamaProviderError("Response cannot be empty")

            return ModelResponse(
                text=text,
                model=model,
                provider_id=self.provider_id,
            )
        except httpx.RequestError as e:
            # Re-raise HTTP request errors
            raise OllamaProviderError("HTTP request failed") from e
        except httpx.HTTPStatusError as e:
            raise OllamaProviderError("HTTP status error") from e
        except ValueError as e:
            # Handle invalid JSON response
            raise OllamaProviderError("Invalid JSON response from Ollama") from e
