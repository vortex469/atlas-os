"""Tests for AtlasCoreClient."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

import httpx
import pytest
from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
    OperationalApprovalMetadata,
)
from app.candidate_planning.models import operational_verification_digest
from app.config.settings import Settings
from app.core_client.client import AtlasCoreClient
from app.core_client.exceptions import (
    AtlasCoreConnectionError,
    AtlasCorePayloadError,
    AtlasCoreResponseError,
    AtlasCoreTimeoutError,
)
from app.core_client.models import (
    AtlasCoreHealth,
    AtlasCoreIntelligenceSummary,
    AtlasCoreStatus,
)
from tests.candidate_planning.test_operational_models import operational_request


def create_test_settings(
    host="127.0.0.1",
    port=8643,
    timeout=10.0,
    operational_auth_file: Path | None = None,
):
    """Create test settings with custom values."""
    return Settings(
        atlas_core_host=host,
        atlas_core_port=port,
        atlas_core_timeout_seconds=timeout,
        operational_dispatch_auth_file=(
            operational_auth_file or Path("/run/atlas-core-agent-auth/token")
        ),
    )


def create_mock_health_response():
    """Create a valid health response payload."""
    return {
        "atlas": "test-atlas",
        "services": {
            "service1": {
                "provider_id": "test-provider",
                "status": "healthy",
                "latency_ms": 150.5,
                "http_status": 200,
                "message": "All good",
                "details": {"version": "1.0"}
            }
        }
    }


def create_mock_status_response():
    """Create a valid status response payload."""
    return {
        "atlas": "test-atlas",
        "assistant": "test-assistant",
        "engine": "test-engine",
        "release": "1.0.0"
    }


def create_mock_intelligence_response():
    """Create a valid intelligence response payload."""
    return {
        "score": 80,
        "status": "warning",
        "summary": "One recommendation is available.",
        "findings": [],
        "assessments": [],
        "recommendations": [
            {
                "title": "Review provider health",
                "reason": "A provider is degraded.",
                "priority": "high",
                "confidence": 0.9,
                "estimated_effort": "small",
            }
        ],
    }


def create_mock_action_history_response():
    """Create a valid action history response payload."""
    return [
        {
            "id": "entry-1",
            "provider_id": "docker",
            "provider_name": "Docker",
            "action_id": "restart-container",
            "action_label": "Restart Container",
            "status": "failed",
            "success": False,
            "message": "Container restart failed.",
            "confirmed": True,
            "destructive": True,
            "parameter_names": ["container"],
            "request_id": "request-1",
            "started_at": "2026-07-31T16:00:00+00:00",
            "completed_at": "2026-07-31T16:00:01+00:00",
            "duration_ms": 1000.0,
        }
    ]


@pytest.fixture
def mock_health_response():
    """Mock a valid health response."""
    return create_mock_health_response()


@pytest.fixture
def mock_status_response():
    """Mock a valid status response."""
    return create_mock_status_response()


@pytest.fixture
def mock_settings():
    """Mock settings fixture."""
    return create_test_settings()


@pytest.fixture
def atlas_core_client(mock_settings):
    """Create AtlasCoreClient instance."""
    return AtlasCoreClient(settings=mock_settings)


@pytest.fixture
def mock_client():
    """Mock httpx.AsyncClient."""
    return MagicMock()


def test_get_health_parsing_valid_response(atlas_core_client, mock_health_response):
    """Test that get_health() parses a valid health response."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/health"
        return httpx.Response(200, json=mock_health_response)

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        # Run the test
        result = asyncio.run(atlas_client.get_health())

        assert isinstance(result, AtlasCoreHealth)
        assert result.atlas == "test-atlas"
        assert "service1" in result.services
        assert result.services["service1"].provider_id == "test-provider"


def test_get_status_parsing_valid_response(atlas_core_client, mock_status_response):
    """Test that get_status() parses a valid status response."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/status/"
        return httpx.Response(200, json=mock_status_response)

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        # Run the test
        result = asyncio.run(atlas_client.get_status())

        assert isinstance(result, AtlasCoreStatus)
        assert result.atlas == "test-atlas"
        assert result.assistant == "test-assistant"


def test_get_intelligence_summary_uses_supported_endpoint() -> None:
    """Intelligence retrieval uses the versioned read-only endpoint."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/intelligence/summary"
        return httpx.Response(
            200,
            json=create_mock_intelligence_response(),
        )

    with httpx.MockTransport(handler) as transport:
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(
            settings=create_test_settings(),
            client=client,
        )

        result = asyncio.run(atlas_client.get_intelligence_summary())

    assert isinstance(result, AtlasCoreIntelligenceSummary)
    assert result.recommendations[0].title == "Review provider health"


def test_get_action_history_uses_supported_endpoint() -> None:
    """Action history retrieval uses the versioned read-only endpoint."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/ops/actions"
        assert request.url.params["limit"] == "25"
        return httpx.Response(
            200,
            json=create_mock_action_history_response(),
        )

    with httpx.MockTransport(handler) as transport:
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(
            settings=create_test_settings(),
            client=client,
        )

        result = asyncio.run(atlas_client.get_action_history(limit=25))

    assert result[0].status == "failed"
    assert result[0].parameter_names == ("container",)


def test_validate_candidate_planning_intake_posts_authoritative_request() -> None:
    """Candidate planning intake sends only candidate identity and fingerprint."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == (
            "/api/v1/execution-candidates/candidate-1/planning-intake"
        )
        assert json.loads(request.content) == {
            "expected_candidate_fingerprint": "candidate-fingerprint-v1:old"
        }
        return httpx.Response(
            200,
            json={
                "status": "accepted_for_planning",
                "candidate_id": "candidate-1",
                "planning_allowed": True,
                "reason_codes": [],
                "current_candidate_fingerprint": "candidate-fingerprint-v1:new",
                "current_candidate": {
                    "id": "candidate-1",
                    "source_recommendation_id": "finding-1",
                    "source_subsystem": "orion",
                    "recommendation_class": "update_compose_stack",
                    "catalog_item_id": "frigate",
                    "target_id": "atlas-compose",
                    "target_type": "repository",
                    "execution_category": "update",
                    "execution_intent": "update-compose-stack",
                    "status": "eligible",
                    "required_approval_level": "standard",
                    "rationale": "Update the compose stack.",
                    "constraints": ["requires-current-evidence"],
                    "evidence_ids": ["evidence-1"],
                    "compatibility_assessment_id": "assessment-1",
                    "compatibility_status": "compatible",
                    "relationship_ids": ["relationship-1"],
                    "created_at": "2026-08-01T23:45:00+00:00",
                    "expires_at": None,
                },
            },
        )

    with httpx.MockTransport(handler) as transport:
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(
            settings=create_test_settings(),
            client=client,
        )

        result = asyncio.run(
            atlas_client.validate_candidate_planning_intake(
                "candidate-1",
                expected_candidate_fingerprint="candidate-fingerprint-v1:old",
            )
        )

    assert result.status == "accepted_for_planning"
    assert result.current_candidate is not None
    assert result.current_candidate.execution_intent == "update-compose-stack"


def test_action_history_payload_error_preserves_exception_semantics() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"invalid": "payload"})

    with httpx.MockTransport(handler) as transport:
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(
            settings=create_test_settings(),
            client=client,
        )

        with pytest.raises(AtlasCorePayloadError):
            asyncio.run(atlas_client.get_action_history())


@pytest.mark.parametrize(
    ("error", "expected_exception"),
    (
        (
            httpx.ConnectError("connection failed"),
            AtlasCoreConnectionError,
        ),
        (
            httpx.TimeoutException("request timed out"),
            AtlasCoreTimeoutError,
        ),
    ),
)
def test_intelligence_transport_errors_preserve_exception_semantics(
    error,
    expected_exception,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    with httpx.MockTransport(handler) as transport:
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(
            settings=create_test_settings(),
            client=client,
        )

        with pytest.raises(expected_exception):
            asyncio.run(atlas_client.get_intelligence_summary())


def test_intelligence_response_error_preserves_exception_semantics() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    with httpx.MockTransport(handler) as transport:
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(
            settings=create_test_settings(),
            client=client,
        )

        with pytest.raises(AtlasCoreResponseError):
            asyncio.run(atlas_client.get_intelligence_summary())


def test_intelligence_payload_error_preserves_exception_semantics() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"invalid": "payload"})

    with httpx.MockTransport(handler) as transport:
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(
            settings=create_test_settings(),
            client=client,
        )

        with pytest.raises(AtlasCorePayloadError):
            asyncio.run(atlas_client.get_intelligence_summary())


def test_validate_connection_calls_health_endpoint(atlas_core_client):
    """Test that validate_connection() calls the health endpoint and returns None."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/health"
        return httpx.Response(200, json=create_mock_health_response())

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        # Run the test
        result = asyncio.run(atlas_client.validate_connection())

        assert result is None


def test_configured_host_and_port_used(atlas_core_client):
    """Test that configured host and port are used for internally created clients."""
    # Create a new client with custom host and port
    custom_settings = create_test_settings(host="192.168.1.100", port=9000)
    client = AtlasCoreClient(settings=custom_settings)

    # The base URL should be constructed with the custom values
    assert client._base_url == "http://192.168.1.100:9000"


def test_configured_timeout_applied(atlas_core_client):
    """Test that configured timeout is applied to internally created clients."""
    # Create a new client with custom timeout
    custom_settings = create_test_settings(timeout=30.0)
    client = AtlasCoreClient(settings=custom_settings)

    # The timeout should be set correctly
    assert client._timeout.connect == 30.0
    assert client._timeout.read == 30.0


def test_injected_client_not_closed_by_close(atlas_core_client, mock_client):
    """Test that injected AsyncClient is not closed by close()."""
    # Create a client with an injected httpx.AsyncClient
    injected_client = MagicMock()
    client_with_injected = AtlasCoreClient(settings=create_test_settings(), client=injected_client)

    # Call close - should not close the injected client
    asyncio.run(client_with_injected.close())

    # The injected client's aclose method should not have been called
    assert not injected_client.aclose.called


def test_internally_created_client_closed_by_close(monkeypatch):
    """Test that internally created AsyncClient is closed by close()."""
    internal_client = MagicMock(spec=httpx.AsyncClient)
    internal_client.aclose = AsyncMock()
    monkeypatch.setattr(
        "app.core_client.client.httpx.AsyncClient",
        lambda: internal_client,
    )
    atlas_client = AtlasCoreClient(settings=create_test_settings())

    assert atlas_client._get_client() is internal_client

    asyncio.run(atlas_client.close())

    internal_client.aclose.assert_awaited_once_with()
    assert atlas_client._client is None


def test_context_manager_closes_internally_owned_client(monkeypatch):
    """Test that async context-manager use closes an internally owned client."""
    internal_client = MagicMock(spec=httpx.AsyncClient)
    internal_client.aclose = AsyncMock()
    monkeypatch.setattr(
        "app.core_client.client.httpx.AsyncClient",
        lambda: internal_client,
    )
    atlas_client = AtlasCoreClient(settings=create_test_settings())
    atlas_client._get_client()

    asyncio.run(atlas_client.__aenter__())
    asyncio.run(atlas_client.__aexit__(None, None, None))

    internal_client.aclose.assert_awaited_once_with()


def test_context_manager_does_not_close_injected_client(atlas_core_client, mock_client):
    """Test that async context-manager use does not close an injected client."""
    # Create a client with an injected httpx.AsyncClient
    injected_client = MagicMock()
    client_with_injected = AtlasCoreClient(settings=create_test_settings(), client=injected_client)

    # Use the context manager
    asyncio.run(client_with_injected.__aenter__())
    asyncio.run(client_with_injected.__aexit__(None, None, None))

    # The injected client's aclose method should not have been called
    assert not injected_client.aclose.called


def test_owned_client_reuses_connection_pool_on_same_event_loop(monkeypatch):
    """Owned clients are reused while requests stay on their owner loop."""
    created_clients = []

    def create_client():
        client = MagicMock(spec=httpx.AsyncClient)
        response = MagicMock()
        response.raise_for_status = Mock()
        response.json.return_value = create_mock_health_response()
        client.get = AsyncMock(
            return_value=response
        )
        client.aclose = AsyncMock()
        client.is_closed = False
        created_clients.append(client)
        return client

    monkeypatch.setattr("app.core_client.client.httpx.AsyncClient", create_client)
    atlas_client = AtlasCoreClient(settings=create_test_settings())

    async def make_requests() -> None:
        await atlas_client.get_health()
        first_client = atlas_client._client
        await atlas_client.get_health()
        assert atlas_client._client is first_client
        assert len(created_clients) == 1
        await atlas_client.close()

    asyncio.run(make_requests())


def test_owned_client_is_not_reused_after_owner_event_loop_closes(monkeypatch):
    """A new loop gets a new owned pool instead of a stale closed-loop pool."""
    created_clients = []

    def create_client():
        client = MagicMock(spec=httpx.AsyncClient)
        response = MagicMock()
        response.raise_for_status = Mock()
        response.json.return_value = create_mock_health_response()
        client.get = AsyncMock(
            return_value=response
        )
        client.aclose = AsyncMock()
        client.is_closed = False
        created_clients.append(client)
        return client

    monkeypatch.setattr("app.core_client.client.httpx.AsyncClient", create_client)
    atlas_client = AtlasCoreClient(settings=create_test_settings())

    asyncio.run(atlas_client.get_health())
    first_client = atlas_client._client
    asyncio.run(atlas_client.get_health())

    assert len(created_clients) == 2
    assert atlas_client._client is not first_client
    asyncio.run(atlas_client.close())


def test_injected_client_rejects_cross_event_loop_use_without_taking_ownership():
    """Injected clients remain caller-owned and cannot cross their pool's loop."""
    injected_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=create_mock_health_response())
        )
    )
    atlas_client = AtlasCoreClient(
        settings=create_test_settings(),
        client=injected_client,
    )

    asyncio.run(atlas_client.get_health())
    with pytest.raises(RuntimeError, match="cannot be used across event loops"):
        asyncio.run(atlas_client.get_health())

    assert not injected_client.is_closed
    asyncio.run(injected_client.aclose())


def test_connect_error_maps_to_atlas_core_connection_error(atlas_core_client):
    """Test that httpx.ConnectError maps to AtlasCoreConnectionError."""

    # Create mock transport with proper handler that raises an error
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed")

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCoreConnectionError) as exc_info:
            asyncio.run(atlas_client.get_health())

        assert "connection failed" in str(exc_info.value)


def test_timeout_exception_maps_to_atlas_core_timeout_error(atlas_core_client):
    """Test that httpx.TimeoutException maps to AtlasCoreTimeoutError."""

    # Create mock transport with proper handler that raises an error
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCoreTimeoutError) as exc_info:
            asyncio.run(atlas_client.get_health())

        assert "timeout" in str(exc_info.value)


def test_request_error_maps_to_atlas_core_connection_error(atlas_core_client):
    """Test that another httpx.RequestError maps to AtlasCoreConnectionError."""

    # Create mock transport with proper handler that raises an error
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.RequestError("request error")

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCoreConnectionError) as exc_info:
            asyncio.run(atlas_client.get_health())

        assert "request error" in str(exc_info.value)


def test_non_2xx_health_response_maps_to_atlas_core_response_error(atlas_core_client):
    """Test that non-2xx health response maps to AtlasCoreResponseError."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCoreResponseError) as exc_info:
            asyncio.run(atlas_client.get_health())

        assert "500" in str(exc_info.value)


def test_non_2xx_status_response_maps_to_atlas_core_response_error(atlas_core_client):
    """Test that non-2xx status response maps to AtlasCoreResponseError."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="service unavailable")

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCoreResponseError) as exc_info:
            asyncio.run(atlas_client.get_status())

        assert "503" in str(exc_info.value)


def test_invalid_json_maps_to_atlas_core_payload_error(atlas_core_client):
    """Test that invalid JSON maps to AtlasCorePayloadError."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="invalid json")

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCorePayloadError) as exc_info:
            asyncio.run(atlas_client.get_health())

        assert "Invalid payload" in str(exc_info.value)


def test_invalid_health_payload_maps_to_atlas_core_payload_error(atlas_core_client):
    """Test that invalid health payload maps to AtlasCorePayloadError."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"invalid": "payload"})

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCorePayloadError) as exc_info:
            asyncio.run(atlas_client.get_health())

        assert "Invalid payload" in str(exc_info.value)


def test_invalid_status_payload_maps_to_atlas_core_payload_error(atlas_core_client):
    """Test that invalid status payload maps to AtlasCorePayloadError."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"invalid": "payload"})

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCorePayloadError) as exc_info:
            asyncio.run(atlas_client.get_status())

        assert "Invalid payload" in str(exc_info.value)


def test_useful_context_preserved_in_error_messages(atlas_core_client):
    """Test that useful context is preserved in error messages."""

    # Test connection error
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed")

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        try:
            asyncio.run(atlas_client.get_health())
            assert False, "Expected exception was not raised"
        except AtlasCoreConnectionError as e:
            # The error message should contain the URL and original error
            assert "http://127.0.0.1:8643/api/v1/health" in str(e)
            assert "connection failed" in str(e)

    # Test timeout error
    def handler_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    with httpx.MockTransport(handler_timeout) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        try:
            asyncio.run(atlas_client.get_health())
            assert False, "Expected exception was not raised"
        except AtlasCoreTimeoutError as e:
            # The error message should contain the URL and original error
            assert "http://127.0.0.1:8643/api/v1/health" in str(e)
            assert "timeout" in str(e)


def test_operational_dispatch_uses_dedicated_header_and_typed_payload(tmp_path) -> None:
    token = "agent-core-test-token"
    token_file = tmp_path / "token"
    token_file.write_text(f"{token}\n", encoding="ascii")
    action = operational_request()
    approval = OperationalApprovalMetadata(
        action_request_id=action.request_id,
        action_request_digest=action.request_digest,
        candidate_id=action.candidate_id,
        candidate_fingerprint=action.candidate_fingerprint,
        operational_plan_fingerprint=action.candidate_plan_fingerprint,
        provider_id=action.provider_id,
        resource_id=action.resource_id,
        resource_type=action.resource_type,
        target_fingerprint=action.target_fingerprint,
        target_version=action.target_version,
        operation_intent=action.execution_intent,
        disruption_scope=action.disruption_scope,
        verification_digest=operational_verification_digest(action.verification),
        generated_at=action.generated_at,
        expires_at=action.expires_at,
    )
    approval_result = ApprovalResult(
        decision=ApprovalDecision(
            request=ApprovalRequest(
                identifier="approval-operational-1",
                checkpoint_id="implementation-approval",
                title="Approve exact operational request",
                requested_tool="operational-action",
                requested_command=(),
                rationale="Exact semantic approval",
                workflow_id=action.workflow_session_id,
                purpose=ApprovalPurpose.IMPLEMENTATION,
                operational_metadata=approval,
            ),
            status=ApprovalStatus.APPROVED,
        )
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/internal/operational-actions/dispatch"
        assert request.headers["Authorization"] == f"Bearer {token}"
        payload = json.loads(request.content)
        assert "authorization" not in json.dumps(payload).lower()
        assert payload["request_digest"] == action.request_digest
        assert payload["approval"]["action_request_digest"] == action.request_digest
        return httpx.Response(
            200,
            json={
                "status": "failed",
                "request_id": action.request_id,
                "request_digest": action.request_digest,
                "target_fingerprint": action.target_fingerprint,
                "started_at": datetime.now(UTC).isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "sanitized_message": "Operational execution capability is disabled.",
            },
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    client = AtlasCoreClient(
        settings=create_test_settings(operational_auth_file=token_file),
        client=http_client,
    )
    result = asyncio.run(
        client.dispatch_operational_action(
            action,
            approval_result,
        )
    )
    assert result.status == "failed"


def test_repository_core_requests_do_not_receive_operational_auth_header(tmp_path) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("must-not-leak\n", encoding="ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        return httpx.Response(200, json=create_mock_health_response())

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AtlasCoreClient(
        settings=create_test_settings(operational_auth_file=token_file),
        client=http_client,
    )
    asyncio.run(client.get_health())


def test_operational_status_reader_is_typed_authenticated_and_read_only(tmp_path) -> None:
    token = "agent-core-status-token"
    token_file = tmp_path / "token"
    token_file.write_text(f"{token}\n", encoding="ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/internal/operational-actions/request-1"
        assert request.headers["Authorization"] == f"Bearer {token}"
        assert request.content == b""
        return httpx.Response(
            200,
            json={
                "request_id": "request-1",
                "request_digest": "operational-action-request-digest-v1:abc",
                "ledger_state": "outcome_unknown",
                "dispatch_result": None,
                "verification_result": None,
                "verification_resumable": False,
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AtlasCoreClient(
        settings=create_test_settings(operational_auth_file=token_file),
        client=http_client,
    )
    result = asyncio.run(client.get_operational_action_status("request-1"))
    assert result.ledger_state == "outcome_unknown"
    with pytest.raises(AtlasCorePayloadError):
        asyncio.run(client.get_operational_action_status("../request-1"))
