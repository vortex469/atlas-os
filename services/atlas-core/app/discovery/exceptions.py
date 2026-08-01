from __future__ import annotations


class DiscoveryCatalogError(RuntimeError):
    """Base exception for Discovery Center catalog loading failures."""


class DiscoveryCatalogPathError(DiscoveryCatalogError):
    """Raised when a catalog path or file cannot be used."""


class DiscoveryCatalogYamlError(DiscoveryCatalogError):
    """Raised when a YAML catalog source cannot be parsed."""


class DiscoveryCatalogDocumentError(DiscoveryCatalogError):
    """Raised when a YAML catalog source has an invalid document shape."""


class DiscoveryCatalogValidationError(DiscoveryCatalogError):
    """Raised when a catalog entry fails domain-model validation."""


class DiscoveryCatalogDuplicateError(DiscoveryCatalogError):
    """Raised when catalog entries contain duplicate identifiers."""
