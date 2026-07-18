import os
from pathlib import Path

import yaml

from app.config.settings import CONFIG_FILE, ENV_FILE, settings


REQUIRED_ENVIRONMENT_VARIABLES = (
    "PROXMOX_USER",
    "PROXMOX_TOKEN_NAME",
    "PROXMOX_TOKEN_VALUE",
    "HASS_TOKEN",
)


class ConfigurationValidationError(RuntimeError):
    pass


def validate_environment() -> list[str]:
    errors: list[str] = []

    if not ENV_FILE.exists():
        errors.append(f"Environment file not found: {ENV_FILE}")
        return errors

    missing_variables = [
        variable
        for variable in REQUIRED_ENVIRONMENT_VARIABLES
        if not os.getenv(variable)
    ]

    if missing_variables:
        errors.append(
            "Missing environment variables: "
            + ", ".join(missing_variables)
        )

    return errors


def validate_inventory() -> list[str]:
    errors: list[str] = []

    inventory_path = Path(settings.inventory.file)

    if not inventory_path.exists():
        errors.append(
            f"Inventory file not found: {inventory_path}"
        )
        return errors

    try:
        with inventory_path.open("r", encoding="utf-8") as file:
            inventory = yaml.safe_load(file)
    except yaml.YAMLError as error:
        errors.append(
            f"Inventory YAML is invalid: {error}"
        )
        return errors

    if not isinstance(inventory, dict):
        errors.append("Inventory must contain a YAML mapping.")
        return errors

    services = inventory.get("services")

    if not isinstance(services, dict) or not services:
        errors.append(
            "Inventory must contain a non-empty 'services' mapping."
        )
        return errors

    required_fields = {
        "host",
        "port",
        "protocol",
        "health_endpoint",
        "critical",
    }

    for service_name, service in services.items():
        if not isinstance(service, dict):
            errors.append(
                f"Service '{service_name}' must be a mapping."
            )
            continue

        missing_fields = required_fields - service.keys()

        if missing_fields:
            errors.append(
                f"Service '{service_name}' is missing fields: "
                + ", ".join(sorted(missing_fields))
            )

        port = service.get("port")

        if port is not None and (
            not isinstance(port, int)
            or not 1 <= port <= 65535
        ):
            errors.append(
                f"Service '{service_name}' has invalid port: {port}"
            )

        protocol = service.get("protocol")

        if protocol not in {"http", "https"}:
            errors.append(
                f"Service '{service_name}' has invalid protocol: "
                f"{protocol}"
            )

    return errors


def validate_docker() -> list[str]:
    errors: list[str] = []

    socket_value = settings.docker.socket

    if socket_value.startswith("unix://"):
        socket_path = Path(
            socket_value.removeprefix("unix://")
        )

        if not socket_path.exists():
            errors.append(
                f"Docker socket not found: {socket_path}"
            )

    return errors


def validate_configuration() -> None:
    errors: list[str] = []

    if not CONFIG_FILE.exists():
        errors.append(
            f"Atlas configuration file not found: {CONFIG_FILE}"
        )

    errors.extend(validate_environment())
    errors.extend(validate_inventory())
    errors.extend(validate_docker())

    if errors:
        formatted_errors = "\n".join(
            f" - {error}"
            for error in errors
        )

        raise ConfigurationValidationError(
            "Atlas configuration validation failed:\n"
            f"{formatted_errors}"
        )
