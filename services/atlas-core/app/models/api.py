from pydantic import BaseModel, Field


class APIDiscovery(BaseModel):
    name: str = "Atlas Core API"
    version: str = "v1"
    release: str
    documentation: str = "/docs"
    openapi: str = "/openapi.json"
    endpoints: dict[str, str] = Field(default_factory=dict)
