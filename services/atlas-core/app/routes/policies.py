from fastapi import APIRouter, HTTPException

from app.config.policies import PolicyLoadError, load_policies
from app.config.policy_models import Policies
from app.models.contracts import APIError


router = APIRouter(
    prefix="/policies",
    tags=["Policies"],
)


@router.get(
    "",
    response_model=Policies,
    responses={503: {"model": APIError}},
)
def policies() -> Policies:
    """Return the current validated operational policy snapshot."""

    try:
        return load_policies()
    except PolicyLoadError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
