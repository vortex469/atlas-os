"""Guarded API for operator-controlled delivery enablement evidence."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError

from app.core.exceptions import request_id_for
from app.models.contracts import APIError
from app.operator_auth.dependencies import (
    require_operator_mutation,
    require_operator_permission,
)
from app.operator_auth.models import (
    INSTALLATION_DELIVERY_ENABLEMENT_CREATE,
    INSTALLATION_DELIVERY_ENABLEMENT_READ,
    OperatorPrincipal,
)
from app.operator_controlled_delivery_enablement.contract import (
    MAX_CREATE_BYTES,
    OperatorControlledDeliveryEnablementCreateV1,
    OperatorControlledDeliveryEnablementOperationResultV1,
)

router = APIRouter(
    prefix="/installation-delivery-enablements",
    tags=["Installation Delivery Enablements"],
)
_read = require_operator_permission(INSTALLATION_DELIVERY_ENABLEMENT_READ)
_create = require_operator_mutation(INSTALLATION_DELIVERY_ENABLEMENT_CREATE)
ReadPrincipal = Annotated[OperatorPrincipal, Depends(_read)]
CreatePrincipal = Annotated[OperatorPrincipal, Depends(_create)]
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
]
_UUID4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_MAX_JSON_DEPTH = 16


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class OperatorControlledDeliveryEnablementCollectionV1(_Closed):
    enablements: tuple[OperatorControlledDeliveryEnablementOperationResultV1, ...]
    next_cursor: str | None = None


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def _depth(value: Any) -> int:
    pending = [(value, 1)]
    maximum = 1
    while pending:
        current, depth = pending.pop()
        maximum = max(maximum, depth)
        if depth > _MAX_JSON_DEPTH:
            return depth
        if isinstance(current, dict):
            pending.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            pending.extend((child, depth + 1) for child in current)
    return maximum


async def _body(request: Request) -> OperatorControlledDeliveryEnablementCreateV1:
    media_type = request.headers.get("content-type", "").split(";", 1)[0]
    if media_type.strip().lower() != "application/json":
        raise HTTPException(415, "Delivery enablement must use application/json.")
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1 or (
        lengths
        and (
            not lengths[0].isascii()
            or not lengths[0].isdecimal()
            or int(lengths[0]) > MAX_CREATE_BYTES
        )
    ):
        raise HTTPException(413, "Delivery enablement request is too large.")
    raw = await request.body()
    if len(raw) > MAX_CREATE_BYTES:
        raise HTTPException(413, "Delivery enablement request is too large.")
    try:
        decoded = json.loads(raw, object_pairs_hook=_pairs)
        if not isinstance(decoded, dict) or _depth(decoded) > _MAX_JSON_DEPTH:
            raise ValueError("invalid JSON shape")
        return OperatorControlledDeliveryEnablementCreateV1.model_validate(decoded)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
        RecursionError,
    ) as error:
        raise HTTPException(422, "Delivery enablement request is invalid.") from error


def _key(value: str) -> str:
    if not value.isascii() or not 1 <= len(value.encode("ascii")) <= 128 or any(
        not 0x21 <= ord(character) <= 0x7E for character in value
    ):
        raise HTTPException(422, "Delivery enablement request is invalid.")
    return value


def _service(request: Request) -> Any:
    service = getattr(
        request.app.state, "operator_controlled_delivery_enablement_service", None
    )
    if service is None:
        raise HTTPException(503, "Delivery enablement is unavailable.")
    return service


def _failure(
    value: OperatorControlledDeliveryEnablementOperationResultV1,
) -> JSONResponse:
    assert value.error is not None
    status_code = {
        "not_found": 404,
        "replay_conflict": 409,
        "quota_exceeded": 409,
        "not_current": 409,
        "preflight_not_eligible": 409,
        "malformed": 422,
        "confirmation_mismatch": 422,
        "linkage_mismatch": 422,
        "fingerprint_mismatch": 422,
        "unauthenticated": 401,
        "unauthorized": 403,
    }.get(value.error.error_code, 503)
    return JSONResponse(status_code=status_code, content=jsonable_encoder(value))


_ERRORS = {
    code: {"model": APIError}
    for code in (401, 403, 404, 409, 413, 415, 422, 429, 503)
}


@router.post(
    "",
    response_model=OperatorControlledDeliveryEnablementOperationResultV1,
    status_code=201,
    responses=_ERRORS,
)
async def create_delivery_enablement(
    request: Request,
    response: Response,
    principal: CreatePrincipal,
    idempotency_key: IdempotencyKey,
) -> OperatorControlledDeliveryEnablementOperationResultV1 | JSONResponse:
    payload = await _body(request)
    result = _service(request).create(
        payload,
        authenticated_operator_id=principal.operator_id,
        idempotency_key=_key(idempotency_key),
        correlation_id=request_id_for(request),
    )
    if result.error is not None:
        return _failure(result)
    if result.disposition == "exact_replay":
        response.status_code = 200
    return result


@router.get(
    "",
    response_model=OperatorControlledDeliveryEnablementCollectionV1,
    responses=_ERRORS,
)
def list_delivery_enablements(
    request: Request,
    principal: ReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=16)] = 16,
    cursor: Annotated[str | None, Query(pattern=_UUID4)] = None,
) -> OperatorControlledDeliveryEnablementCollectionV1 | JSONResponse:
    values = _service(request).list(
        authenticated_operator_id=principal.operator_id,
        correlation_id=request_id_for(request),
    )
    failure = next((value for value in values if value.error is not None), None)
    if failure is not None:
        return _failure(failure)
    if cursor is not None:
        indexes = [
            index
            for index, value in enumerate(values)
            if value.record and value.record.enablement_id == cursor
        ]
        if not indexes:
            raise HTTPException(404, "Delivery enablement was not found.")
        values = values[indexes[0] + 1 :]
    page = values[:limit]
    next_cursor = (
        page[-1].record.enablement_id
        if len(values) > limit and page[-1].record
        else None
    )
    return OperatorControlledDeliveryEnablementCollectionV1(
        enablements=page, next_cursor=next_cursor
    )


@router.get(
    "/{enablement_id}",
    response_model=OperatorControlledDeliveryEnablementOperationResultV1,
    responses=_ERRORS,
)
def get_delivery_enablement(
    request: Request,
    principal: ReadPrincipal,
    enablement_id: Annotated[str, Path(pattern=_UUID4)],
) -> OperatorControlledDeliveryEnablementOperationResultV1 | JSONResponse:
    result = _service(request).get(
        authenticated_operator_id=principal.operator_id,
        enablement_id=enablement_id,
        correlation_id=request_id_for(request),
    )
    return _failure(result) if result.error is not None else result


@router.api_route(
    "",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_collection_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET, POST"})


@router.api_route(
    "/{enablement_id}",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_item_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET"})
