"""Ollama model provider implementation."""


import httpx


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
