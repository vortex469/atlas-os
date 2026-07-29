"""Tests for the ModelService."""

from unittest.mock import Mock

import pytest

from app.model_providers.interface import ModelProvider
from app.model_providers.models import ModelResponse
from app.model_service.service import ModelService


def test_model_service_uses_configured_default_model():
    """Test that the service uses the configured default model."""
    # Create a mock provider
    mock_provider = Mock(spec=ModelProvider)
    mock_response = ModelResponse(text="test response", model="test-model", provider_id="test-provider")
    mock_provider.generate.return_value = mock_response

    # Create service with a specific default model
    service = ModelService(provider=mock_provider, default_model="my-default-model")

    # Call generate
    result = service.generate(prompt="test prompt")

    # Verify the provider was called with the correct model and prompt
    mock_provider.generate.assert_called_once_with(model="my-default-model", prompt="test prompt")
    assert result == mock_response


def test_model_service_forwards_prompt_unchanged():
    """Test that the service forwards the prompt unchanged."""
    # Create a mock provider
    mock_provider = Mock(spec=ModelProvider)
    mock_response = ModelResponse(text="test response", model="test-model", provider_id="test-provider")
    mock_provider.generate.return_value = mock_response

    # Create service
    service = ModelService(provider=mock_provider, default_model="test-model")

    # Call generate with a specific prompt
    result = service.generate(prompt="my special prompt with spaces and symbols!@#$%^&*()")

    # Verify the provider was called with the exact same prompt
    mock_provider.generate.assert_called_once_with(model="test-model", prompt="my special prompt with spaces and symbols!@#$%^&*()")
    assert result == mock_response


def test_model_service_returns_exact_provider_response():
    """Test that the service returns the exact ModelResponse from the provider."""
    # Create a mock provider
    mock_provider = Mock(spec=ModelProvider)

    # Create a specific response instance
    expected_response = ModelResponse(text="exact response", model="exact-model", provider_id="exact-provider")
    mock_provider.generate.return_value = expected_response

    # Create service
    service = ModelService(provider=mock_provider, default_model="test-model")

    # Call generate
    result = service.generate(prompt="test prompt")

    # Verify it returns the exact same instance
    assert result is expected_response


def test_model_service_propagates_provider_exceptions():
    """Test that provider exceptions are propagated unchanged."""
    # Create a mock provider that raises an exception
    mock_provider = Mock(spec=ModelProvider)
    expected_error = ValueError("test exception")
    mock_provider.generate.side_effect = expected_error

    # Create service
    service = ModelService(provider=mock_provider, default_model="test-model")

    # Call generate and verify the exception is propagated
    with pytest.raises(ValueError) as exc_info:
        mock_provider.generate.side_effect = expected_error
        service.generate(prompt="test prompt")
        assert exc_info.value is expected_error
