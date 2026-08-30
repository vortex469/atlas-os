import os
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class ProviderIntentActivation(StrEnum):
    NOT_ACTIVATED = "not_activated"
    ACTIVATED = "activated"


ATLAS_ROOT = Path("/opt/atlas")
CONFIG_FILE = ATLAS_ROOT / "config" / "atlas.yaml"
ENV_FILE = ATLAS_ROOT / ".env"

load_dotenv(ENV_FILE)


class AtlasSettings(BaseModel):
    name: str = "Atlas OS"
    release: str
    assistant: str = "Orion"
    host: str = "0.0.0.0"
    port: int = Field(default=8643, ge=1, le=65535)


class InfrastructureSettings(BaseModel):
    domain: str = "home.arpa"


class ProxmoxSettings(BaseModel):
    host: str
    port: int = Field(default=8006, ge=1, le=65535)
    node: str
    verify_ssl: bool = False


class HomeAssistantSettings(BaseModel):
    url: str


class DockerSettings(BaseModel):
    socket: str = "unix:///var/run/docker.sock"


class InventorySettings(BaseModel):
    file: str


class AuditSettings(BaseModel):
    database: str = "/opt/atlas/data/action_history.db"
    max_entries: int = Field(default=5000, ge=1)
    retention_days: int = Field(default=90, ge=1)


class IntelligenceSettings(BaseModel):
    provider_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        le=60,
    )
    telemetry_database: str = "/opt/atlas/data/provider_intelligence.db"
    telemetry_max_entries: int = Field(default=10_000, ge=1)
    telemetry_retention_days: int = Field(default=30, ge=1)


class OperationalDispatchSettings(BaseModel):
    database: str = "/opt/atlas/data/operational_dispatch.db"
    agent_auth_file: str = "/run/atlas-core-agent-auth/token"


class DynamicDiscoverySettings(BaseModel):
    enabled: bool = False


class ProviderIntentSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    activation: ProviderIntentActivation = ProviderIntentActivation.NOT_ACTIVATED
    database: str = "/opt/atlas/data/provider_intents.db"
    expected_legacy_import_id: str | None = Field(
        default=None,
        pattern=r"^provider-intent-legacy-policy-import-v1:[a-f0-9]{64}$",
    )

    @model_validator(mode="after")
    def validate_activation_contract(self) -> "ProviderIntentSettings":
        database = Path(self.database)
        if (
            not self.database
            or self.database != self.database.strip()
            or not database.is_absolute()
            or self.database == ":memory:"
        ):
            raise ValueError("provider intent database must be an absolute path")
        if self.activation is ProviderIntentActivation.NOT_ACTIVATED:
            if self.expected_legacy_import_id is not None:
                raise ValueError(
                    "inactive Provider Intent cannot expect a legacy import"
                )
        elif self.expected_legacy_import_id is None:
            raise ValueError(
                "activated Provider Intent requires an expected legacy import ID"
            )
        return self


class OperatorAuthSettings(BaseModel):
    enabled: bool = False
    verifier_file: str = "/run/atlas-operator-auth/operators.json"
    trusted_origins: tuple[str, ...] = ()
    session_lifetime_seconds: int = Field(default=28_800, ge=300, le=86_400)
    login_rate_limit: int = Field(default=5, ge=1, le=100)
    mutation_rate_limit: int = Field(default=10, ge=1, le=1000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    session_database: str = "/opt/atlas/data/operator_sessions.db"
    audit_database: str = "/opt/atlas/data/operator_security_audit.db"
    intent_database: str = "/opt/atlas/data/operator_intents.db"
    installation_selection_database: str = (
        "/opt/atlas/data/installation_destination_selections.db"
    )
    installation_candidate_record_database: str = (
        "/opt/atlas/data/installation_candidate_records.db"
    )
    installation_approval_intent_database: str = (
        "/opt/atlas/data/installation_approval_intents.db"
    )
    installation_execution_request_enabled: bool = False
    installation_execution_request_database: str = (
        "/opt/atlas/data/installation_execution_requests.db"
    )
    installation_dispatch_handoff_enabled: bool = False
    installation_dispatch_handoff_database: str = (
        "/opt/atlas/data/installation_dispatch_handoffs.db"
    )
    execution_permission_grant_database: str = (
        "/opt/atlas/data/execution_permission_grants.db"
    )
    installation_execution_admission_database: str = (
        "/opt/atlas/data/installation_execution_admissions.db"
    )
    runner_binding_plan_database: str = (
        "/opt/atlas/data/runner_binding_plans.db"
    )
    worker_admission_stub_database: str = (
        "/opt/atlas/data/worker_admission_stubs.db"
    )

    @model_validator(mode="after")
    def validate_enabled_configuration(self) -> "OperatorAuthSettings":
        selection_database = Path(self.installation_selection_database)
        if (
            not self.installation_selection_database
            or self.installation_selection_database
            != self.installation_selection_database.strip()
            or not selection_database.is_absolute()
            or self.installation_selection_database == ":memory:"
        ):
            raise ValueError("installation selection database must be an absolute path")
        candidate_database = Path(self.installation_candidate_record_database)
        if (
            not self.installation_candidate_record_database
            or self.installation_candidate_record_database
            != self.installation_candidate_record_database.strip()
            or not candidate_database.is_absolute()
            or self.installation_candidate_record_database == ":memory:"
        ):
            raise ValueError(
                "installation candidate record database must be an absolute path"
            )
        approval_intent_database = Path(self.installation_approval_intent_database)
        if (
            not self.installation_approval_intent_database
            or self.installation_approval_intent_database
            != self.installation_approval_intent_database.strip()
            or not approval_intent_database.is_absolute()
            or self.installation_approval_intent_database == ":memory:"
        ):
            raise ValueError(
                "installation approval intent database must be an absolute path"
            )
        execution_request_database = Path(self.installation_execution_request_database)
        if (
            not self.installation_execution_request_database
            or self.installation_execution_request_database
            != self.installation_execution_request_database.strip()
            or not execution_request_database.is_absolute()
            or self.installation_execution_request_database == ":memory:"
        ):
            raise ValueError(
                "installation execution request database must be an absolute path"
            )
        dispatch_handoff_database = Path(self.installation_dispatch_handoff_database)
        if (
            not self.installation_dispatch_handoff_database
            or self.installation_dispatch_handoff_database
            != self.installation_dispatch_handoff_database.strip()
            or not dispatch_handoff_database.is_absolute()
            or self.installation_dispatch_handoff_database == ":memory:"
        ):
            raise ValueError(
                "installation dispatch handoff database must be an absolute path"
            )
        permission_grant_database = Path(self.execution_permission_grant_database)
        if (
            not self.execution_permission_grant_database
            or self.execution_permission_grant_database
            != self.execution_permission_grant_database.strip()
            or not permission_grant_database.is_absolute()
            or self.execution_permission_grant_database == ":memory:"
        ):
            raise ValueError(
                "execution permission grant database must be an absolute path"
            )
        execution_admission_database = Path(
            self.installation_execution_admission_database
        )
        if (
            not self.installation_execution_admission_database
            or self.installation_execution_admission_database
            != self.installation_execution_admission_database.strip()
            or not execution_admission_database.is_absolute()
            or self.installation_execution_admission_database == ":memory:"
        ):
            raise ValueError(
                "installation execution admission database must be an absolute path"
            )
        runner_binding_plan_database = Path(self.runner_binding_plan_database)
        if (
            not self.runner_binding_plan_database
            or self.runner_binding_plan_database
            != self.runner_binding_plan_database.strip()
            or not runner_binding_plan_database.is_absolute()
            or self.runner_binding_plan_database == ":memory:"
        ):
            raise ValueError(
                "runner binding plan database must be an absolute path"
            )
        worker_admission_stub_database = Path(self.worker_admission_stub_database)
        if (
            not self.worker_admission_stub_database
            or self.worker_admission_stub_database
            != self.worker_admission_stub_database.strip()
            or not worker_admission_stub_database.is_absolute()
            or self.worker_admission_stub_database == ":memory:"
        ):
            raise ValueError(
                "worker admission stub database must be an absolute path"
            )
        if not self.enabled:
            return self
        if not self.verifier_file.strip():
            raise ValueError("operator auth verifier file is required")
        if not self.trusted_origins:
            raise ValueError("operator auth requires at least one trusted HTTPS origin")
        normalized: list[str] = []
        for origin in self.trusted_origins:
            value = origin.strip().rstrip("/")
            parsed = urlsplit(value)
            if (
                parsed.scheme != "https"
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username is not None
                or parsed.password is not None
                or "*" in value
            ):
                raise ValueError("operator auth origins must be exact HTTPS origins")
            normalized.append(value)
        if len(set(normalized)) != len(normalized):
            raise ValueError("operator auth origins must be unique")
        object.__setattr__(self, "trusted_origins", tuple(normalized))
        return self


class Settings(BaseModel):
    atlas: AtlasSettings
    infrastructure: InfrastructureSettings
    proxmox: ProxmoxSettings
    home_assistant: HomeAssistantSettings
    docker: DockerSettings
    inventory: InventorySettings
    audit: AuditSettings = Field(default_factory=AuditSettings)
    intelligence: IntelligenceSettings = Field(
        default_factory=IntelligenceSettings,
    )
    operational_dispatch: OperationalDispatchSettings = Field(
        default_factory=OperationalDispatchSettings,
    )
    provider_intents: ProviderIntentSettings = Field(
        default_factory=ProviderIntentSettings,
    )
    operator_auth: OperatorAuthSettings = Field(default_factory=OperatorAuthSettings)
    dynamic_discovery: DynamicDiscoverySettings = Field(
        default_factory=DynamicDiscoverySettings,
    )


def load_yaml_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        raise RuntimeError(f"Atlas configuration file not found: {CONFIG_FILE}")

    with CONFIG_FILE.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    if not isinstance(config, dict):
        raise RuntimeError(  # noqa: TRY004 - preserve configuration error contract
            f"Atlas configuration is invalid: {CONFIG_FILE}"
        )

    return config


def load_settings() -> Settings:
    try:
        raw = load_yaml_config()
        operator_raw = dict(raw.get("operator_auth") or {})
        environment_overrides = {
            "enabled": os.getenv("ATLAS_OPERATOR_AUTH_ENABLED"),
            "verifier_file": os.getenv("ATLAS_OPERATOR_AUTH_VERIFIER_FILE"),
            "trusted_origins": os.getenv("ATLAS_OPERATOR_AUTH_TRUSTED_ORIGINS"),
            "session_database": os.getenv("ATLAS_OPERATOR_AUTH_SESSION_DATABASE"),
            "audit_database": os.getenv("ATLAS_OPERATOR_AUTH_AUDIT_DATABASE"),
            "intent_database": os.getenv("ATLAS_OPERATOR_INTENT_DATABASE"),
            "installation_selection_database": os.getenv(
                "ATLAS_OPERATOR_AUTH_INSTALLATION_SELECTION_DATABASE"
            ),
            "installation_candidate_record_database": os.getenv(
                "ATLAS_OPERATOR_AUTH_INSTALLATION_CANDIDATE_RECORD_DATABASE"
            ),
            "installation_approval_intent_database": os.getenv(
                "ATLAS_OPERATOR_AUTH_INSTALLATION_APPROVAL_INTENT_DATABASE"
            ),
            "installation_execution_request_enabled": os.getenv(
                "ATLAS_OPERATOR_AUTH_INSTALLATION_EXECUTION_REQUEST_ENABLED"
            ),
            "installation_execution_request_database": os.getenv(
                "ATLAS_OPERATOR_AUTH_INSTALLATION_EXECUTION_REQUEST_DATABASE"
            ),
            "installation_dispatch_handoff_enabled": os.getenv(
                "ATLAS_OPERATOR_AUTH_INSTALLATION_DISPATCH_HANDOFF_ENABLED"
            ),
            "installation_dispatch_handoff_database": os.getenv(
                "ATLAS_OPERATOR_AUTH_INSTALLATION_DISPATCH_HANDOFF_DATABASE"
            ),
            "execution_permission_grant_database": os.getenv(
                "ATLAS_OPERATOR_AUTH_EXECUTION_PERMISSION_GRANT_DATABASE"
            ),
            "installation_execution_admission_database": os.getenv(
                "ATLAS_OPERATOR_AUTH_INSTALLATION_EXECUTION_ADMISSION_DATABASE"
            ),
            "runner_binding_plan_database": os.getenv(
                "ATLAS_OPERATOR_AUTH_RUNNER_BINDING_PLAN_DATABASE"
            ),
            "worker_admission_stub_database": os.getenv(
                "ATLAS_OPERATOR_AUTH_WORKER_ADMISSION_STUB_DATABASE"
            ),
        }
        for key, value in environment_overrides.items():
            if value is None:
                continue
            if key in {
                "enabled",
                "installation_execution_request_enabled",
                "installation_dispatch_handoff_enabled",
            }:
                operator_raw[key] = value.strip().lower() in {"1", "true", "yes", "on"}
            elif key == "trusted_origins":
                operator_raw[key] = tuple(
                    item.strip() for item in value.split(",") if item.strip()
                )
            else:
                operator_raw[key] = value
        raw["operator_auth"] = operator_raw
        provider_intent_raw = dict(raw.get("provider_intents") or {})
        provider_intent_overrides = {
            "activation": os.getenv("ATLAS_PROVIDER_INTENT_ACTIVATION"),
            "database": os.getenv("ATLAS_PROVIDER_INTENT_DATABASE"),
            "expected_legacy_import_id": os.getenv(
                "ATLAS_PROVIDER_INTENT_EXPECTED_LEGACY_IMPORT_ID"
            ),
        }
        provider_intent_raw.update(
            (key, value)
            for key, value in provider_intent_overrides.items()
            if value is not None
        )
        raw["provider_intents"] = provider_intent_raw
        dynamic_discovery_raw = dict(raw.get("dynamic_discovery") or {})
        dynamic_discovery_enabled = os.getenv("ATLAS_ENABLE_DISCOVERY_DYNAMIC_REFRESH")
        if dynamic_discovery_enabled is not None:
            dynamic_discovery_raw["enabled"] = (
                dynamic_discovery_enabled.strip().lower()
                in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }
            )
        raw["dynamic_discovery"] = dynamic_discovery_raw
        loaded = Settings.model_validate(raw)
        auth_file = os.getenv("ATLAS_OPERATIONAL_DISPATCH_AUTH_FILE")
        if auth_file:
            loaded = loaded.model_copy(
                update={
                    "operational_dispatch": loaded.operational_dispatch.model_copy(
                        update={"agent_auth_file": auth_file}
                    )
                }
            )
        return loaded
    except ValidationError as error:
        raise RuntimeError(
            f"Atlas configuration validation failed:\n{error}"
        ) from error


settings = load_settings()
