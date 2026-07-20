from pydantic import BaseModel, Field


class ResourceEstimate(BaseModel):
    """Estimated infrastructure resources required by a deployment."""

    cpu_cores: float | None = Field(default=None, ge=0)
    memory_gb: float | None = Field(default=None, ge=0)
    storage_gb: float | None = Field(default=None, ge=0)
    gpu_required: bool = False
    gpu_memory_gb: float | None = Field(default=None, ge=0)
    estimated_duration_minutes: int | None = Field(
        default=None,
        ge=0,
    )
