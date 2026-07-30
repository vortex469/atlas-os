"""Tests for context-aware workflow composition."""

import asyncio
from unittest.mock import AsyncMock, Mock

from app.context.engine import ContextEngine
from app.context.models import AgentContext
from app.workflow.engine import WorkflowEngine
from app.workflow.models import WorkflowRequest, WorkflowResult
from app.workflow.orchestrator import WorkflowOrchestrator


def test_captures_context_once_before_running_workflow() -> None:
    request = Mock(spec=WorkflowRequest)
    result = Mock(spec=WorkflowResult)
    context = AgentContext(
        atlas="online",
        assistant="Atlas",
        engine="Hermes",
        release="test",
        services={},
    )
    context_engine = Mock(spec=ContextEngine)
    context_engine.get_context = AsyncMock(return_value=context)
    workflow_engine = Mock(spec=WorkflowEngine)
    workflow_engine.run.return_value = result

    actual = asyncio.run(
        WorkflowOrchestrator(
            workflow_engine=workflow_engine,
            context_engine=context_engine,
        ).run(request)
    )

    context_engine.get_context.assert_awaited_once_with()
    workflow_engine.run.assert_called_once_with(request, context=context)
    assert actual is result


def test_optional_context_failure_runs_repository_only_workflow() -> None:
    request = Mock(spec=WorkflowRequest)
    result = Mock(spec=WorkflowResult)
    context_engine = Mock(spec=ContextEngine)
    context_engine.get_context = AsyncMock(
        side_effect=RuntimeError("unavailable")
    )
    workflow_engine = Mock(spec=WorkflowEngine)
    workflow_engine.run.return_value = result

    actual = asyncio.run(
        WorkflowOrchestrator(
            workflow_engine=workflow_engine,
            context_engine=context_engine,
        ).run(request)
    )

    workflow_engine.run.assert_called_once_with(request, context=None)
    workflow_engine.block_before_planning.assert_not_called()
    assert actual is result


def test_required_context_failure_blocks_before_planning() -> None:
    request = Mock(spec=WorkflowRequest)
    result = Mock(spec=WorkflowResult)
    context_engine = Mock(spec=ContextEngine)
    context_engine.get_context = AsyncMock(
        side_effect=RuntimeError("unavailable")
    )
    workflow_engine = Mock(spec=WorkflowEngine)
    workflow_engine.block_before_planning.return_value = result

    actual = asyncio.run(
        WorkflowOrchestrator(
            workflow_engine=workflow_engine,
            context_engine=context_engine,
            atlas_core_required=True,
        ).run(request)
    )

    workflow_engine.block_before_planning.assert_called_once_with(
        request,
        error_message="Atlas Core context acquisition failed",
    )
    workflow_engine.run.assert_not_called()
    assert actual is result
