class ApplicationServiceError(Exception):
    """Base application service exception."""


class UnsupportedDeploymentSource(ApplicationServiceError):
    """Raised when no analyzer exists for the requested source."""