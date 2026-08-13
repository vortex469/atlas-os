"""Execution-disabled HTTP API for the private worker socket."""

from __future__ import annotations

import logging
import secrets
from typing import Any

from app.execution.worker_contracts import (
    BoundedOutput,
    WorkerAttestation,
    WorkerExecutionRequest,
    WorkerExecutionResult,
    WorkerExecutionStatus,
    WorkerFailureCode,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .durable_ledger import (
    DurableLedgerConflictError,
    DurableLedgerCorruptionError,
    DurableRequestLedger,
)
from .ledger import RequestConflictError, RequestLedger
from .runner import WorkspaceExecutionRunner

LOGGER = logging.getLogger("atlas_execution_worker")
SERVICE_NAME = "atlas-execution-worker"


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

    app = FastAPI(title=SERVICE_NAME, docs_url=None, redoc_url=None)
    request_ledger = (
        ledger if ledger is not None else durable_ledger if durable_ledger is not None else RequestLedger()
    )
    configured_runners = runners or {}

    @app.get("/health")
    async def health() -> dict[str, Any]:
        counts = request_ledger.counts() if isinstance(request_ledger, DurableRequestLedger) else {}
        return {
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
        if authentication_token is not None and not secrets.compare_digest(
            request.headers.get("authorization", ""),
            f"Bearer {authentication_token}",
        ):
            return _error(401, "authentication_required", "worker authentication failed")
        try:
            payload = await request.json()
            worker_request = WorkerExecutionRequest.from_dict(payload)
        except (ValueError, TypeError, KeyError, UnicodeDecodeError) as exc:
            LOGGER.info("worker request rejected code=invalid_request")
            return _error(400, "invalid_request", str(exc))
        except Exception:
            LOGGER.exception("worker request parsing failed code=invalid_request")
            return _error(400, "invalid_request", "request could not be parsed")

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
        if authentication_token is not None and not secrets.compare_digest(
            request.headers.get("authorization", ""),
            f"Bearer {authentication_token}",
        ):
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
                "result": entry.result.to_dict() if entry.result else None,
            }
        )

    return app


app = create_app()
