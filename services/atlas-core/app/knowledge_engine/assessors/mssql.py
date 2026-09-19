from __future__ import annotations

from typing import ClassVar

from app.knowledge_engine.assessors.database import (
    DatabaseAssessor,
)


class MSSQLAssessor(DatabaseAssessor):
    """Assess Microsoft SQL Server deployments."""

    APPLICATION_NAME = "Microsoft SQL Server"

    IMAGES: ClassVar[set[str]] = {
        "mcr.microsoft.com/mssql/server",
    }

    STORAGE_PATH = "/var/opt/mssql"

    CONTAINER_PORT = 1433

    REQUIRED_ENVIRONMENT_VARIABLES: ClassVar[list[str]] = [
        "MSSQL_SA_PASSWORD",
    ]

    HEALTHCHECK_RECOMMENDATION = (
        "Add a Microsoft SQL Server health check using sqlcmd."
    )

    STORAGE_RECOMMENDATION = (
        "Mount /var/opt/mssql to persistent storage."
    )

    PORT_RECOMMENDATION = (
        "Keep Microsoft SQL Server on an internal network and "
        "avoid publicly exposing port 1433."
    )

    BEST_PRACTICES: ClassVar[list[str]] = [
        "Use persistent storage.",
        "Configure health checks.",
        "Avoid public network exposure.",
        "Configure regular database backups.",
    ]