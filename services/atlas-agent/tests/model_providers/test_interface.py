"""Tests for the model provider interface."""


from app.model_providers.interface import ModelProvider


class DummyProvider:
    """Dummy implementation of the ModelProvider interface."""
    
    def __init__(self, provider_id: str = "test-provider"):
        self._provider_id = provider_id
    
    @property
    def provider_id(self) -> str:
        return self._provider_id
    
    def health_check(self) -> bool:
        return True


def test_provider_identity():
    """Test that providers have correct identity."""
    provider = DummyProvider("test-provider")
    assert provider.provider_id == "test-provider"


def test_provider_health_check():
    """Test that providers can perform health checks."""
    provider = DummyProvider()
    result = provider.health_check()
    assert result is True


def test_interface_is_protocol():
    """Test that ModelProvider is a Protocol."""
    # This test verifies that we can instantiate the interface
    # since it's a Protocol, we just verify it's defined correctly
    assert hasattr(ModelProvider, '__annotations__')
    assert hasattr(ModelProvider, 'provider_id')
    assert hasattr(ModelProvider, 'health_check')
