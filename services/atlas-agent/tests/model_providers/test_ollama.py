"""Tests for the Ollama model provider."""

from unittest.mock import MagicMock, patch

import httpx

from app.model_providers.ollama import OllamaProvider


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
