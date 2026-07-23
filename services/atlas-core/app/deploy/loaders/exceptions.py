class LoaderError(Exception):
    """Base exception for deployment document loader failures."""


class InvalidYamlError(LoaderError):
    """Raised when YAML content cannot be parsed."""


class InvalidDocumentError(LoaderError):
    """Raised when a loaded YAML document is not a mapping."""
