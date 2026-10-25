"""Execution-disabled HTTP API for the private worker socket."""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from typing import Any

from app.execution.worker_contracts import (
    BoundedOutput,
    WorkerAttestation,
    WorkerExecutionRequest,
    WorkerExecutionResult,
    WorkerExecutionStatus,
    WorkerFailureCode,
)
from app.execution.worker_json import decode_worker_json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .durable_ledger import (
    DurableLedgerConflictError,
    DurableLedgerCorruptionError,
    DurableLedgerStartConflict,
    DurableRequestLedger,
)
from .isolation import IsolationUnavailable
from .ledger import RequestConflictError, RequestLedger
from .runner import WorkspaceExecutionRunner

LOGGER = logging.getLogger("atlas_execution_worker")
SERVICE_NAME = "atlas-execution-worker"
MAX_EXECUTION_REQUEST_BYTES = 2 * 1024 * 1024
MAX_REQUEST_READ_SECONDS = 5.0


def _disabled_result(request: WorkerExecutionRequest) -> WorkerExecutionResult:
    return WorkerExecutionResult(
        schema_version=1,
        execution_request_id=request.execution_request_id,
        status=WorkerExecutionStatus.BLOCKED,
        return_code=None,
        stdout=BoundedOutput(""),
        stderr=BoundedOutput(""),
        changed_files=(),
        patch_digest=None,
        patch_size_bytes=None,
        patch_truncated=False,
        duration_seconds=0,
        failure_code=WorkerFailureCode.WORKER_UNAVAILABLE,
        workspace_head=None,
        worker_attestation=WorkerAttestation(
            runtime_uid=10001,
            readonly_rootfs=True,
            no_new_privileges=True,
            effective_capabilities="0000000000000000",
            sandbox_profile="execution-disabled",
        ),
    )


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _authenticated(request: Request, token: str) -> bool:
    values = request.headers.getlist("authorization")
    if len(values) != 1:
        return False
    try:
        provided = values[0].encode("ascii")
    except UnicodeEncodeError:
        return False
    return secrets.compare_digest(provided, ("Bearer " + token).encode("ascii"))


def create_app(
    ledger: RequestLedger | None = None,
    durable_ledger: DurableRequestLedger | None = None,
    *,
    execution_enabled: bool = False,
    runners: dict[str, WorkspaceExecutionRunner] | None = None,
    authentication_token: str | None = None,
    allowed_client_address: str | None = None,
) -> FastAPI:
    """Create the execution-disabled app with an injectable ledger."""

    if authentication_token is not None and (
        not isinstance(authentication_token, str) or not authentication_token
        or len(authentication_token) > 1024
        or any(not 33 <= ord(char) <= 126 for char in authentication_token)
    ):
        raise ValueError("worker authentication must be one bounded ASCII credential")
    app = FastAPI(title=SERVICE_NAME, docs_url=None, redoc_url=None)
    request_ledger = (
        ledger if ledger is not None else durable_ledger if durable_ledger is not None else RequestLedger()
    )
    configured_runners = runners or {}

    @app.get("/health")
    async def health() -> dict[str, Any]:
        counts = request_ledger.counts() if isinstance(request_ledger, DurableRequestLedger) else {}
        observed = None
        reason = "execution_disabled"
        if execution_enabled:
            reason = "runtime_provider_unobserved"
            if configured_runners and all(isinstance(runner, WorkspaceExecutionRunner) for runner in configured_runners.values()):
                try:
                    for runner in configured_runners.values():
                        runner.observe_runtime()
                    observed, reason = True, "isolation_observed"
                except IsolationUnavailable:
                    observed, reason = False, "isolation_unavailable"
        return {
            "execution_readiness": {
                "configured_enabled":execution_enabled, "isolation_observed_safe":observed,
                "reason":reason, "full_readiness_proven":False, "activation_authorized":False,
            },
            "service": SERVICE_NAME,
            "status": "healthy",
            "contract_schema_version": 1,
            "execution_enabled": execution_enabled,
            **(
                {
                    "ledger_counts": {
                        "claimed": counts.get("claimed", 0),
                        "completed": counts.get("completed", 0),
                        "unknown_outcome": counts.get("unknown_outcome", 0),
                    }
                }
                if isinstance(request_ledger, DurableRequestLedger)
                else {}
            ),
        }

    @app.post("/v1/executions")
    async def submit(request: Request) -> JSONResponse:
        if (
            allowed_client_address is not None
            and (request.client is None or request.client.host != allowed_client_address)
        ):
            return _error(403, "untrusted_peer", "worker client network identity rejected")
        if authentication_token is not None and not _authenticated(request, authentication_token):
            return _error(401, "authentication_required", "worker authentication failed")
        lengths = request.headers.getlist("content-length")
        if (lengths and request.headers.get("transfer-encoding")) or len(lengths) > 1 or (lengths and (not lengths[0].isascii() or not lengths[0].isdigit() or len(lengths[0]) > 10)):
            return _error(400, "invalid_request", "invalid request framing")
        if lengths and int(lengths[0]) > MAX_EXECUTION_REQUEST_BYTES:
            return _error(413, "request_too_large", "execution request exceeds byte bound")
        body = bytearray()
        deadline = time.monotonic() + MAX_REQUEST_READ_SECONDS
        try:
            async with asyncio.timeout(MAX_REQUEST_READ_SECONDS):
                async for chunk in request.stream():
                    if len(body) + len(chunk) > MAX_EXECUTION_REQUEST_BYTES:
                        return _error(413, "request_too_large", "execution request exceeds byte bound")
                    body.extend(chunk)
            if lengths and len(body) != int(lengths[0]):
                return _error(400, "invalid_request", "request length mismatch")
            payload = decode_worker_json(body)
            worker_request = WorkerExecutionRequest.from_dict(payload)
            if time.monotonic() >= deadline:
                return _error(408, "request_timeout", "execution request read deadline exceeded")
        except TimeoutError:
            return _error(408, "request_timeout", "execution request read deadline exceeded")
        except (ValueError, TypeError, KeyError, UnicodeDecodeError, RecursionError) as exc:
            LOGGER.info("worker request rejected code=invalid_request")
            return _error(400, "invalid_request", str(exc))
        except Exception:
            LOGGER.exception("worker request parsing failed code=invalid_request")
            return _error(400, "invalid_request", "request could not be parsed")

        if execution_enabled:
            configured = configured_runners.get(worker_request.repository_token)
            if configured is None:
                return _error(400, "unknown_repository_token", "repository token is not configured")
            if isinstance(configured, WorkspaceExecutionRunner):
                try:
                    configured.validate_runtime()
                except IsolationUnavailable:
                    return _error(503, "sandbox_unavailable", "required execution isolation unavailable")
        try:
            entry = request_ledger.claim(worker_request)
        except DurableLedgerCorruptionError:
            LOGGER.error("worker ledger corruption code=ledger_corrupt")
            return _error(503, "ledger_corrupt", "stored execution result is invalid")
        except (RequestConflictError, DurableLedgerConflictError):
            LOGGER.info(
                "worker request rejected execution_request_id=%s request_digest=%s claim_state=conflict result_code=conflict",
                worker_request.execution_request_id,
                worker_request.request_digest,
            )
            return _error(409, "request_id_conflict", "execution request ID has a different digest")

        if execution_enabled and entry.result is None and entry.state == "claimed":
            runner = configured_runners.get(worker_request.repository_token)
            if runner is None:
                return _error(400, "unknown_repository_token", "repository token is not configured")
            if not isinstance(request_ledger, DurableRequestLedger):
                return _error(503, "ledger_unavailable", "enabled execution requires durable ledger")
            try:
                request_ledger.mark_executing(worker_request)
                result = runner.execute(worker_request)
                entry = request_ledger.persist_result(worker_request, result)
            except DurableLedgerStartConflict as conflict:
                entry = conflict.entry
            except IsolationUnavailable:
                return _error(503, "sandbox_unavailable", "required execution isolation unavailable")
            except ValueError:
                LOGGER.exception(
                    "worker result rejected execution_request_id=%s result_code=invalid_result",
                    worker_request.execution_request_id,
                )
                return _error(424, "invalid_result", "worker returned an invalid result")
            except Exception:
                LOGGER.exception(
                    "worker execution failed execution_request_id=%s result_code=worker_execution_failed",
                    worker_request.execution_request_id,
                )
                return _error(424, "worker_execution_failed", "worker execution failed")
        elif entry.result is None and entry.state == "claimed":
            result = _disabled_result(worker_request)
            if isinstance(request_ledger, DurableRequestLedger):
                entry = request_ledger.persist_result(worker_request, result)
            else:
                entry = request_ledger.complete(worker_request, result)
        LOGGER.info(
            "worker request handled execution_request_id=%s request_digest=%s claim_state=%s result_code=%s",
            worker_request.execution_request_id,
            worker_request.request_digest,
            entry.state,
            entry.result.failure_code if entry.result else "none",
        )
        return JSONResponse(
            status_code=202 if entry.state == "claimed" else 200,
            content={
                "state": entry.state,
                "request_digest": entry.request_digest,
                "result": entry.result.to_dict() if entry.result else None,
            },
        )

    @app.get("/v1/executions/{execution_request_id}")
    async def get_result(execution_request_id: str, request: Request) -> JSONResponse:
        if (
            allowed_client_address is not None
            and (request.client is None or request.client.host != allowed_client_address)
        ):
            return _error(403, "untrusted_peer", "worker client network identity rejected")
        if authentication_token is not None and not _authenticated(request, authentication_token):
            return _error(401, "authentication_required", "worker authentication failed")
        try:
            entry = request_ledger.get(execution_request_id)
        except DurableLedgerCorruptionError:
            return _error(503, "ledger_corrupt", "stored execution result is invalid")
        if entry is None:
            return _error(404, "execution_not_found", "execution request was not found")
        return JSONResponse(
            content={
                "state": entry.state,
                "request_digest": entry.request_digest,
                "result": entry.result.to_dict() if entry.result else None,
            }
        )

    return app


app = create_app()
