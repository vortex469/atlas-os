from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

OPERATIONAL_INTENT_CREATE = "operational_intent:create"
PROVIDER_INTENT_UPDATE = "provider_intent:update"
INSTALLATION_DESTINATION_SELECT = "installation_destination:select"
INSTALLATION_DELIVERY_PREFLIGHT_CREATE = "installation_delivery_preflight:create"
INSTALLATION_DELIVERY_PREFLIGHT_READ = "installation_delivery_preflight:read"
INSTALLATION_DELIVERY_ENABLEMENT_CREATE = "installation_delivery_enablement:create"
INSTALLATION_DELIVERY_ENABLEMENT_READ = "installation_delivery_enablement:read"
INSTALLATION_EXECUTION_PERMISSION_GRANT = (
    "installation.execution.permission.grant"
)
INSTALLATION_EXECUTION_PERMISSION_GRANT_READ = (
    "installation.execution.permission.grant.read"
)
INSTALLATION_EXECUTION_ADMISSION_RECORD = (
    "installation.execution.admission.record"
)
INSTALLATION_EXECUTION_ADMISSION_READ = "installation.execution.admission.read"
INSTALLATION_RUNNER_BINDING_PLAN_RECORD = "installation.runner.binding.plan.record"
INSTALLATION_RUNNER_BINDING_PLAN_READ = "installation.runner.binding.plan.read"
INSTALLATION_WORKER_ADMISSION_STUB_RECORD = (
    "installation.execution.worker_admission_stub.record"
)
INSTALLATION_WORKER_ADMISSION_STUB_READ = (
    "installation.execution.worker_admission_stub.read"
)
INSTALLATION_WORKER_QUEUE_RESERVATION_RECORD = (
    "installation.execution.worker_queue_reservation.record"
)
INSTALLATION_WORKER_QUEUE_RESERVATION_READ = (
    "installation.execution.worker_queue_reservation.read"
)
INSTALLATION_WORKER_INTAKE_ADMISSION_RECORD = (
    "installation.execution.worker_intake_admission.record"
)
INSTALLATION_WORKER_INTAKE_ADMISSION_READ = (
    "installation.execution.worker_intake_admission.read"
)
INSTALLATION_LIVE_ENQUEUE_ADMISSION_RECORD = (
    "installation.execution.live_enqueue_admission.record"
)
INSTALLATION_LIVE_ENQUEUE_ADMISSION_READ = (
    "installation.execution.live_enqueue_admission.read"
)
INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_RECORD = (
    "installation.execution.one_shot_live_enqueue.record"
)
INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_READ = (
    "installation.execution.one_shot_live_enqueue.read"
)
INSTALLATION_QUEUE_OBSERVATION_RECORD = (
    "installation.execution.queue_observation.record"
)
INSTALLATION_QUEUE_OBSERVATION_READ = "installation.execution.queue_observation.read"
SUPPORTED_OPERATOR_PERMISSIONS = frozenset(
    {
        OPERATIONAL_INTENT_CREATE,
        PROVIDER_INTENT_UPDATE,
        INSTALLATION_DESTINATION_SELECT,
        INSTALLATION_DELIVERY_PREFLIGHT_CREATE,
        INSTALLATION_DELIVERY_PREFLIGHT_READ,
        INSTALLATION_DELIVERY_ENABLEMENT_CREATE,
        INSTALLATION_DELIVERY_ENABLEMENT_READ,
        INSTALLATION_EXECUTION_PERMISSION_GRANT,
        INSTALLATION_EXECUTION_PERMISSION_GRANT_READ,
        INSTALLATION_EXECUTION_ADMISSION_RECORD,
        INSTALLATION_EXECUTION_ADMISSION_READ,
        INSTALLATION_RUNNER_BINDING_PLAN_RECORD,
        INSTALLATION_RUNNER_BINDING_PLAN_READ,
        INSTALLATION_WORKER_ADMISSION_STUB_RECORD,
        INSTALLATION_WORKER_ADMISSION_STUB_READ,
        INSTALLATION_WORKER_QUEUE_RESERVATION_RECORD,
        INSTALLATION_WORKER_QUEUE_RESERVATION_READ,
        INSTALLATION_WORKER_INTAKE_ADMISSION_RECORD,
        INSTALLATION_WORKER_INTAKE_ADMISSION_READ,
        INSTALLATION_LIVE_ENQUEUE_ADMISSION_RECORD,
        INSTALLATION_LIVE_ENQUEUE_ADMISSION_READ,
        INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_RECORD,
        INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_READ,
        INSTALLATION_QUEUE_OBSERVATION_RECORD,
        INSTALLATION_QUEUE_OBSERVATION_READ,
    }
)


class OperatorAuthModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OperatorCredential(OperatorAuthModel):
    operator_id: str = Field(min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9._@-]+$")
    password_hash: str = Field(min_length=1)
    enabled: bool = True
    permissions: tuple[str, ...]

    @model_validator(mode="after")
    def validate_permissions(self) -> OperatorCredential:
        if len(set(self.permissions)) != len(self.permissions):
            raise ValueError("operator permissions must be unique")
        if not set(self.permissions) <= SUPPORTED_OPERATOR_PERMISSIONS:
            raise ValueError("operator credential contains an unsupported permission")
        return self


class OperatorCredentialFile(OperatorAuthModel):
    schema_version: Literal[1]
    operators: tuple[OperatorCredential, ...]

    @model_validator(mode="after")
    def validate_operator_ids(self) -> OperatorCredentialFile:
        identifiers = [operator.operator_id for operator in self.operators]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("operator IDs must be unique")
        return self


class OperatorPrincipal(OperatorAuthModel):
    operator_id: str
    authenticated_at: datetime
    permissions: tuple[str, ...]
    auth_method: Literal["core_session"] = "core_session"


class OperatorLoginRequest(OperatorAuthModel):
    operator_id: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=4096)


class OperatorSessionResponse(OperatorAuthModel):
    authenticated: Literal[True] = True
    principal: OperatorPrincipal
    expires_at: datetime


class OperatorLogoutResponse(OperatorAuthModel):
    authenticated: Literal[False] = False


class OperatorProbeRequest(OperatorAuthModel):
    action: Literal["operator-auth-boundary-probe"] = "operator-auth-boundary-probe"


class OperatorProbeResponse(OperatorAuthModel):
    operator_id: str
    permission: Literal["operational_intent:create"]
    action: Literal["operator-auth-boundary-probe"]
    authorized: Literal[True] = True
