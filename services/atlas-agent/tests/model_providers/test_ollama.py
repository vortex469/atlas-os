"""Tests for the Ollama model provider."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.model_providers.models import ModelResponse
from app.model_providers.ollama import OllamaProvider, OllamaProviderError


def test_ollama_provider_identity():
    """Test that Ollama provider has correct identity."""
    provider = OllamaProvider("http://localhost:11434")
    assert provider.provider_id == "ollama"


def test_ollama_provider_health_check_healthy():
    """Test that Ollama provider health check works with healthy response."""
    provider = OllamaProvider("http://localhost:11434")

    # Mock the HTTP client to return a successful response
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch('httpx.Client') as mock_client_class:
        mock_http_client = MagicMock()
        mock_http_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_http_client

        result = provider.health_check()

        assert result is True
        mock_http_client.get.assert_called_once_with(
            "http://localhost:11434/api/version",
            timeout=10.0
        )


def test_ollama_provider_health_check_unhealthy():
    """Test that Ollama provider health check works with unhealthy response."""
    provider = OllamaProvider("http://localhost:11434")

    # Mock the HTTP client to return an unsuccessful response
    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch('httpx.Client') as mock_client_class:
        mock_http_client = MagicMock()
        mock_http_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_http_client

        result = provider.health_check()

        assert result is False
        mock_http_client.get.assert_called_once_with(
            "http://localhost:11434/api/version",
            timeout=10.0
        )


def test_ollama_provider_health_check_exception():
    """Test that Ollama provider health check handles exceptions."""
    provider = OllamaProvider("http://localhost:11434")

    with patch('httpx.Client') as mock_client_class:
        # Mock the HTTP client to raise a RequestError
        mock_http_client = MagicMock()
        mock_http_client.get.side_effect = httpx.RequestError("Network error")
        mock_client_class.return_value.__enter__.return_value = mock_http_client

        result = provider.health_check()

        assert result is False
        mock_http_client.get.assert_called_once_with(
            "http://localhost:11434/api/version",
            timeout=10.0
        )


def test_ollama_provider_with_custom_timeout():
    """Test that Ollama provider accepts custom timeout."""
    provider = OllamaProvider("http://localhost:11434", timeout_seconds=5.0)

    assert provider.provider_id == "ollama"

    # Test that health check still works
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch('httpx.Client') as mock_client_class:
        mock_http_client = MagicMock()
        mock_http_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_http_client

        result = provider.health_check()

        assert result is True
        mock_http_client.get.assert_called_once_with(
            "http://localhost:11434/api/version",
            timeout=5.0
        )


def test_ollama_provider_trailing_slash():
    """Test that trailing slashes in base_url are normalized."""
    provider = OllamaProvider("http://localhost:11434/")

    # Test that the health check call uses the normalized URL without double slashes
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch('httpx.Client') as mock_client_class:
        mock_http_client = MagicMock()
        mock_http_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_http_client

        result = provider.health_check()

        assert result is True
        # Verify the URL doesn't contain double slashes
        mock_http_client.get.assert_called_once_with(
            "http://localhost:11434/api/version",
            timeout=10.0
        )


def test_ollama_provider_generate_success():
    """Test that Ollama provider generate works with successful response."""
    provider = OllamaProvider("http://localhost:11434")

    # Mock the HTTP client to return a successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "Hello, world!"}

    with patch('httpx.Client') as mock_client_class:
        mock_http_client = MagicMock()
        mock_http_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_http_client

        result = provider.generate(model="test-model", prompt="Hello")

        assert isinstance(result, ModelResponse)
        assert result.text == "Hello, world!"
        assert result.model == "test-model"
        assert result.provider_id == "ollama"

        mock_http_client.post.assert_called_once_with(
            "http://localhost:11434/api/generate",
            json={
                "model": "test-model",
                "prompt": "Hello",
                "stream": False,
            },
            timeout=10.0
        )


def test_ollama_provider_generate_request_failure():
    """Test that Ollama provider generate handles request failures."""
    provider = OllamaProvider("http://localhost:11434")

    with patch('httpx.Client') as mock_client_class:
        mock_http_client = MagicMock()
        mock_http_client.post.side_effect = httpx.RequestError("Network error")
        mock_client_class.return_value.__enter__.return_value = mock_http_client

        with pytest.raises(OllamaProviderError) as exc_info:
            provider.generate(model="test-model", prompt="Hello")

        assert "HTTP request failed" in str(exc_info.value)


def test_ollama_provider_generate_http_status_failure():
    """Test that Ollama provider generate handles HTTP status failures."""
    provider = OllamaProvider("http://localhost:11434")

    # Mock the HTTP client to return a 500 error
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error", request=MagicMock(), response=mock_response
    )

    with patch('httpx.Client') as mock_client_class:
        mock_http_client = MagicMock()
        mock_http_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_http_client

        with pytest.raises(OllamaProviderError) as exc_info:
            provider.generate(model="test-model", prompt="Hello")

        assert "HTTP status error" in str(exc_info.value)


def test_ollama_provider_generate_invalid_json():
    """Test that Ollama provider generate handles invalid JSON response."""
    provider = OllamaProvider("http://localhost:11434")

    # Mock the HTTP client to return an invalid JSON response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")

    with patch('httpx.Client') as mock_client_class:
        mock_http_client = MagicMock()
        mock_http_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_http_client

        with pytest.raises(OllamaProviderError) as exc_info:
            provider.generate(model="test-model", prompt="Hello")

        assert "Invalid JSON response from Ollama" in str(exc_info.value)


def test_ollama_provider_generate_non_dict_json():
    """Test that Ollama provider generate handles non-dict JSON response."""
    provider = OllamaProvider("http://localhost:11434")

    # Mock the HTTP client to return a non-dict JSON response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = "not a dict"

    with patch('httpx.Client') as mock_client_class:
        mock_http_client = MagicMock()
        mock_http_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_http_client

        with pytest.raises(OllamaProviderError) as exc_info:
            provider.generate(model="test-model", prompt="Hello")

        assert "Response must be a dictionary" in str(exc_info.value)


def test_ollama_provider_generate_missing_response():
    """Test that Ollama provider generate handles missing response field."""
    provider = OllamaProvider("http://localhost:11434")

    # Mock the HTTP client to return a response without 'response' field
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"other_field": "value"}

    with patch('httpx.Client') as mock_client_class:
        mock_http_client = MagicMock()
        mock_http_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_http_client

        with pytest.raises(OllamaProviderError) as exc_info:
            provider.generate(model="test-model", prompt="Hello")

        assert "Response must be a non-empty string" in str(exc_info.value)


def test_ollama_provider_generate_non_string_response():
    """Test that Ollama provider generate handles non-string response field."""
    provider = OllamaProvider("http://localhost:11434")

    # Mock the HTTP client to return a response with non-string 'response' field
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": 123}

    with patch('httpx.Client') as mock_client_class:
        mock_http_client = MagicMock()
        mock_http_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_http_client

        with pytest.raises(OllamaProviderError) as exc_info:
            provider.generate(model="test-model", prompt="Hello")

        assert "Response must be a non-empty string" in str(exc_info.value)


def test_ollama_provider_generate_empty_response():
    """Test that Ollama provider generate handles empty response text."""
    provider = OllamaProvider("http://localhost:11434")

    # Mock the HTTP client to return a response with empty 'response' field
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": ""}

    with patch('httpx.Client') as mock_client_class:
        mock_http_client = MagicMock()
        mock_http_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_http_client

        with pytest.raises(OllamaProviderError) as exc_info:
            provider.generate(model="test-model", prompt="Hello")

        assert "Response cannot be empty" in str(exc_info.value)
