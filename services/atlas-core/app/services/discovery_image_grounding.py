"""Inert construction for the Discovery image-grounding read dependency."""

from pathlib import Path

from ..discovery.image_grounding import ImageGroundingStatus
from .image_grounding_read_model import (
    BindingDrivenImageGroundingService,
    ImageGroundingReadError,
    ImageGroundingReadFailure,
    ImageGroundingReadModel,
)

__all__ = [
    "ImageGroundingReadError",
    "ImageGroundingReadFailure",
    "ImageGroundingReadModel",
    "ImageGroundingStatus",
    "get_discovery_image_grounding_service",
]

ATLAS_ROOT = Path("/opt/atlas")


def get_discovery_image_grounding_service() -> BindingDrivenImageGroundingService:
    """Construct the local-only P1 service without reading any inputs."""

    return BindingDrivenImageGroundingService(ATLAS_ROOT)
