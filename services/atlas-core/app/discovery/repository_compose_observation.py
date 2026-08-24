"""v0.14 P1c repository compose-image observation.

Given an injected repository root and an existing, validated
``DeploymentBinding``, this module performs a single, bounded, read-only
observation of the literal ``image`` string that the bound service declares
in its local compose file.

The module is core-only and inert in P1c: it has no production consumer and
is not exported from the public Discovery API. It performs no network
access, registry or tag resolution, clock reads, subprocess execution,
caching, or filesystem writes. It does not resolve ``extends``, include
files, environment variables, anchors, tags, or digests: the observation
records the tracked literal exactly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

from app.discovery.exceptions import (
    RepositoryComposeObservationDocumentError,
    RepositoryComposeObservationPathError,
    RepositoryComposeObservationSizeError,
    RepositoryComposeObservationValidationError,
    RepositoryComposeObservationYamlError,
)
from app.discovery.models import DeploymentBinding, RepositoryComposeImageObservation

MAX_COMPOSE_FILE_BYTES = 256 * 1024
# Explicit bound for recursive YAML node walkers. A compose document whose
# node nesting exceeds this fails closed with a document error instead of
# relying on (and leaking) Python's interpreter recursion depth.
MAX_COMPOSE_NODE_DEPTH = 10000

_PLAIN_STR_TAG = "tag:yaml.org,2002:str"
# Core safe-schema tags only. Any other tag (python/*, binary, set, omap,
# merge, or any vendor tag) is rejected fail-closed.
_SAFE_CORE_TAGS = frozenset(
    {
        "tag:yaml.org,2002:str",
        "tag:yaml.org,2002:int",
        "tag:yaml.org,2002:float",
        "tag:yaml.org,2002:bool",
        "tag:yaml.org,2002:null",
        "tag:yaml.org,2002:map",
        "tag:yaml.org,2002:seq",
        "tag:yaml.org,2002:timestamp",
    }
)
_IMAGE_KEY = "image"
_SERVICES_KEY = "services"
_IMAGE_MAX_LENGTH = 1024
_INTERPOLATION_TOKENS = ("${", "$")


class RepositoryComposeImageObservationAcquirer:
    """Acquire ``RepositoryComposeImageObservation`` values from a repository.

    The repository root is required and injected at construction. It is
    never derived from the process working directory. The compose target
    path comes only from the validated ``DeploymentBinding``; there is no
    API for passing an arbitrary raw compose path.
    """

    def __init__(
        self,
        repository_root: Path,
        *,
        max_file_bytes: int = MAX_COMPOSE_FILE_BYTES,
    ) -> None:
        self._repository_root = Path(repository_root)
        if not self._repository_root.is_absolute():
            raise RepositoryComposeObservationPathError(
                f"Repository root must be an absolute path: {repository_root}"
            )
        self._max_file_bytes = self._validate_max_file_bytes(max_file_bytes)

    @staticmethod
    def _validate_max_file_bytes(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise RepositoryComposeObservationSizeError(
                "max_file_bytes must be a positive integer number of bytes."
            )
        if value <= 0:
            raise RepositoryComposeObservationSizeError(
                "max_file_bytes must be a positive integer number of bytes."
            )
        return value

    def observe(self, binding: DeploymentBinding) -> RepositoryComposeImageObservation:
        """Observe the bound service's local image string from the repository.

        ``binding`` must be an existing, validated ``DeploymentBinding``.
        Every failure mode raises one of the
        ``RepositoryComposeObservation*`` errors; the acquirer never
        returns a partial or default observation.
        """

        if not isinstance(binding, DeploymentBinding):
            raise RepositoryComposeObservationValidationError(
                "binding must be an existing, validated DeploymentBinding."
            )

        compose_path = self._resolve_compose_path(binding)
        content = self._read_compose_file(compose_path)
        document = self._parse_compose_document(content, source=binding.compose_file)
        image = self._extract_bound_image(document, binding)

        return RepositoryComposeImageObservation(
            compose_file=binding.compose_file,
            compose_service=binding.compose_service,
            image=image,
        )

    def _resolve_compose_path(self, binding: DeploymentBinding) -> Path:
        root = self._repository_root
        if root.is_symlink():
            raise RepositoryComposeObservationPathError(
                f"Repository root must not be a symlink: {root}"
            )
        if not root.exists():
            raise RepositoryComposeObservationPathError(
                f"Repository root does not exist: {root}"
            )
        if not root.is_dir():
            raise RepositoryComposeObservationPathError(
                f"Repository root must be a directory: {root}"
            )

        target = root / binding.compose_file
        for component in (root, *target.parents):
            if not component.exists():
                raise RepositoryComposeObservationPathError(
                    f"Missing intermediate directory: {component}"
                )
            if not component.is_dir():
                raise RepositoryComposeObservationPathError(
                    f"Intermediate path component is not a directory: {component}"
                )
            if component.is_symlink():
                raise RepositoryComposeObservationPathError(
                    f"Intermediate path component must not be a symlink: {component}"
                )
        if target.is_symlink():
            raise RepositoryComposeObservationPathError(
                f"Compose target must not be a symlink: {target}"
            )
        if not target.exists():
            raise RepositoryComposeObservationPathError(
                f"Compose file does not exist: {target}"
            )
        if not target.is_file():
            raise RepositoryComposeObservationPathError(
                f"Compose target must be an existing regular file: {target}"
            )

        # Containment under the injected root, re-asserted fail-closed.
        try:
            resolved_target = target.resolve(strict=True)
            resolved_root = root.resolve(strict=True)
        except OSError as error:
            raise RepositoryComposeObservationPathError(
                f"Unable to resolve compose target {target}: {error}"
            ) from error
        if not resolved_target.is_relative_to(resolved_root):
            raise RepositoryComposeObservationPathError(
                "Compose target escapes the injected repository root."
            )
        return target

    def _read_compose_file(self, compose_path: Path) -> bytes:
        try:
            file_size = compose_path.stat().st_size
        except OSError as error:
            raise RepositoryComposeObservationPathError(
                f"Unable to stat compose file {compose_path}: {error}"
            ) from error
        if file_size > self._max_file_bytes:
            raise RepositoryComposeObservationSizeError(
                f"Compose file exceeds the {self._max_file_bytes} byte bound: "
                f"{compose_path}"
            )

        try:
            with compose_path.open("rb") as handle:
                content = handle.read(self._max_file_bytes + 1)
        except (OSError, ValueError) as error:
            raise RepositoryComposeObservationPathError(
                f"Unable to read compose file {compose_path}: {error}"
            ) from error

        if len(content) > self._max_file_bytes:
            raise RepositoryComposeObservationSizeError(
                f"Compose file exceeds the {self._max_file_bytes} byte bound: "
                f"{compose_path}"
            )
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise RepositoryComposeObservationYamlError(
                f"Compose file is not valid UTF-8: {compose_path}: {error}"
            ) from error
        return content

    @staticmethod
    def _reject_anchors_and_aliases(content: bytes, *, source: str) -> None:
        """Reject anchors and aliases using the YAML event stream.

        PyYAML's composition step resolves aliases into shared node
        objects, so the anchor/alias metadata only survives at the event
        level. Anchors appear as the ``anchor`` attribute on node events
        and aliases as ``AliasEvent``. Both are rejected fail-closed.
        """
        try:
            for event in yaml.parse(content):
                if isinstance(event, yaml.AliasEvent) or getattr(event, "anchor", None):
                    raise RepositoryComposeObservationYamlError(
                        f"Compose document must not use anchors or aliases: {source}"
                    )
        except RecursionError as error:
            raise RepositoryComposeObservationDocumentError(
                f"Compose document nesting exceeds the "
                f"{MAX_COMPOSE_NODE_DEPTH} node bound: {source}"
            ) from error
        except yaml.YAMLError as error:
            raise RepositoryComposeObservationYamlError(
                f"Unable to parse compose YAML from {source}: {error}"
            ) from error

    @staticmethod
    def _parse_compose_document(content: bytes, *, source: str) -> MappingNode:
        RepositoryComposeImageObservationAcquirer._reject_anchors_and_aliases(
            content, source=source
        )
        try:
            documents = list(yaml.compose_all(content))
        except RecursionError as error:
            raise RepositoryComposeObservationDocumentError(
                f"Compose document nesting exceeds the "
                f"{MAX_COMPOSE_NODE_DEPTH} node bound: {source}"
            ) from error
        except yaml.YAMLError as error:
            raise RepositoryComposeObservationYamlError(
                f"Unable to parse compose YAML from {source}: {error}"
            ) from error

        if len(documents) != 1:
            raise RepositoryComposeObservationDocumentError(
                f"Compose file must contain exactly one YAML document: {source}"
            )
        document = documents[0]
        if not isinstance(document, MappingNode):
            raise RepositoryComposeObservationDocumentError(
                f"Compose document root must be a mapping: {source}"
            )

        RepositoryComposeImageObservationAcquirer._reject_unsafe_constructs(
            document, source
        )
        RepositoryComposeImageObservationAcquirer._reject_duplicate_keys(
            document, source
        )
        return document

    @staticmethod
    def _reject_unsafe_constructs(node: Any, source: str) -> None:
        """Iterative walk so pathological nesting fails closed on the
        explicit node-depth bound instead of leaking ``RecursionError``."""
        stack: list[tuple[Any, int]] = [(node, 0)]
        while stack:
            current, depth = stack.pop()
            if depth > MAX_COMPOSE_NODE_DEPTH:
                raise RepositoryComposeObservationDocumentError(
                    f"Compose document nesting exceeds the "
                    f"{MAX_COMPOSE_NODE_DEPTH} node bound: {source}"
                )
            if not current.tag.startswith("tag:yaml.org,2002:"):
                raise RepositoryComposeObservationYamlError(
                    f"Compose document contains an unsafe YAML tag "
                    f"'{current.tag}' in {source}."
                )
            if current.tag not in _SAFE_CORE_TAGS:
                raise RepositoryComposeObservationYamlError(
                    f"Compose document contains a non-safe YAML tag "
                    f"'{current.tag}' in {source}."
                )
            if isinstance(current, MappingNode):
                for key_node, value_node in current.value:
                    stack.append((key_node, depth + 1))
                    stack.append((value_node, depth + 1))
            elif isinstance(current, SequenceNode):
                for child in current.value:
                    stack.append((child, depth + 1))

    @staticmethod
    def _reject_duplicate_keys(node: MappingNode, source: str) -> None:
        """Iterative, exhaustive walk: duplicate-key, merge-key, and
        plain-scalar-key checks apply to every mapping in the document,
        including mappings nested inside sequence items. Nested documents
        beyond the explicit node-depth bound fail closed with a document
        error instead of leaking ``RecursionError``."""
        stack: list[tuple[Any, int]] = [(node, 0)]
        while stack:
            current, depth = stack.pop()
            if depth > MAX_COMPOSE_NODE_DEPTH:
                raise RepositoryComposeObservationDocumentError(
                    f"Compose document nesting exceeds the "
                    f"{MAX_COMPOSE_NODE_DEPTH} node bound: {source}"
                )
            if isinstance(current, MappingNode):
                seen_keys: set[str] = set()
                for key_node, value_node in current.value:
                    if not isinstance(key_node, ScalarNode):
                        raise RepositoryComposeObservationDocumentError(
                            f"Compose mapping keys must be plain scalars: {source}"
                        )
                    if key_node.value == "<<":
                        raise RepositoryComposeObservationYamlError(
                            f"Compose document must not use merge keys: {source}"
                        )
                    if key_node.value in seen_keys:
                        raise RepositoryComposeObservationDocumentError(
                            f"Duplicate compose mapping key {key_node.value!r} "
                            f"in {source}."
                        )
                    seen_keys.add(key_node.value)
                    stack.append((key_node, depth + 1))
                    stack.append((value_node, depth + 1))
            elif isinstance(current, SequenceNode):
                for child in current.value:
                    stack.append((child, depth + 1))

    @staticmethod
    def _mapping_key(mapping: MappingNode, key: str, *, source: str) -> MappingNode:
        for key_node, value_node in mapping.value:
            if isinstance(key_node, ScalarNode) and key_node.value == key:
                if not isinstance(value_node, MappingNode):
                    raise RepositoryComposeObservationDocumentError(
                        f"Compose '{key}' must be a mapping: {source}"
                    )
                return value_node
        raise RepositoryComposeObservationDocumentError(
            f"Compose document is missing '{key}': {source}"
        )

    @staticmethod
    def _scalar_literal(value: str, *, source: str, label: str) -> None:
        if any(token in value for token in _INTERPOLATION_TOKENS):
            raise RepositoryComposeObservationValidationError(
                f"Compose {label} must not contain interpolation or "
                f"environment syntax: {source}"
            )
        if len(value) > _IMAGE_MAX_LENGTH:
            raise RepositoryComposeObservationValidationError(
                f"Compose {label} exceeds the {_IMAGE_MAX_LENGTH} "
                f"character bound: {source}"
            )
        if value != value.strip():
            raise RepositoryComposeObservationValidationError(
                f"Compose {label} must not have surrounding whitespace: {source}"
            )

    def _extract_bound_image(
        self, document: MappingNode, binding: DeploymentBinding
    ) -> str:
        source = binding.compose_file
        services = self._mapping_key(document, _SERVICES_KEY, source=source)
        service = self._mapping_key(services, binding.compose_service, source=source)
        for key_node, value_node in service.value:
            if not isinstance(key_node, ScalarNode) or key_node.value != _IMAGE_KEY:
                continue
            if not isinstance(value_node, ScalarNode):
                raise RepositoryComposeObservationValidationError(
                    f"Bound service image must be a literal string: {source}"
                )
            if value_node.tag != _PLAIN_STR_TAG:
                raise RepositoryComposeObservationValidationError(
                    f"Bound service image must be a plain string literal: {source}"
                )
            image = value_node.value
            self._scalar_literal(image, source=source, label="image")
            if not image:
                raise RepositoryComposeObservationValidationError(
                    f"Bound service image must not be empty: {source}"
                )
            return image
        raise RepositoryComposeObservationValidationError(
            f"Bound service must declare its own local image key: {source}"
        )
