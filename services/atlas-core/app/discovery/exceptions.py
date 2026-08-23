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


class ImageReleaseEvidenceLoaderError(DiscoveryCatalogError):
    """Base exception for curated image-release evidence loader failures."""


class ImageReleaseEvidencePathError(ImageReleaseEvidenceLoaderError):
    """Raised when an image-release evidence path or file cannot be used."""


class ImageReleaseEvidenceYamlError(ImageReleaseEvidenceLoaderError):
    """Raised when an image-release evidence YAML source cannot be parsed."""


class ImageReleaseEvidenceDocumentError(ImageReleaseEvidenceLoaderError):
    """Raised when an image-release evidence YAML source has an invalid
    document shape."""


class ImageReleaseEvidenceValidationError(ImageReleaseEvidenceLoaderError):
    """Raised when an image-release evidence row fails domain-model
    validation."""


class ImageReleaseEvidenceDuplicateError(ImageReleaseEvidenceLoaderError):
    """Raised when image-release evidence rows contain duplicate
    source identifiers."""


class ImageReleaseEvidenceConflictError(ImageReleaseEvidenceLoaderError):
    """Raised when image-release evidence rows conflict for one item and
    release version."""


class DiscoveryRepositoryError(RuntimeError):
    """Base exception for Discovery Center repository failures."""


class DiscoveryRepositoryDuplicateError(DiscoveryRepositoryError):
    """Raised when repository entries contain duplicate identifiers."""


class DiscoveryRepositoryValidationError(DiscoveryRepositoryError):
    """Raised when repository relationship or index validation fails."""


class RepositoryComposeObservationError(DiscoveryCatalogError):
    """Base exception for repository compose-image observation failures."""


class RepositoryComposeObservationPathError(RepositoryComposeObservationError):
    """Raised when the compose path or repository root cannot be used."""


class RepositoryComposeObservationSizeError(RepositoryComposeObservationError):
    """Raised when a compose file exceeds the configured byte bound."""


class RepositoryComposeObservationYamlError(RepositoryComposeObservationError):
    """Raised when a compose file cannot be parsed as safe YAML."""


class RepositoryComposeObservationDocumentError(RepositoryComposeObservationError):
    """Raised when a compose document has an invalid shape."""


class RepositoryComposeObservationValidationError(RepositoryComposeObservationError):
    """Raised when a bound service's local image value fails validation."""
