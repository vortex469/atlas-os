"""Focused v0.14 P1c repository compose-image observation tests.

P1c adds a core-only, read-only acquirer that observes the literal local
``image`` string a bound service declares in a compose file under an
injected repository root. It has no production consumer, is not exported,
and ships no deployment bindings.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.discovery.exceptions import (
    DiscoveryCatalogError,
    RepositoryComposeObservationDocumentError,
    RepositoryComposeObservationError,
    RepositoryComposeObservationPathError,
    RepositoryComposeObservationSizeError,
    RepositoryComposeObservationValidationError,
    RepositoryComposeObservationYamlError,
)
from app.discovery.models import DeploymentBinding, RepositoryComposeImageObservation
from app.discovery.repository_compose_observation import (
    MAX_COMPOSE_FILE_BYTES,
    RepositoryComposeImageObservationAcquirer,
)

COMPOSE_FILE = "deploy/compose.yaml"
SERVICE = "app"
IMAGE = "ghcr.io/acme/app:v1.2.3"


def compose_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "deploy").mkdir(parents=True)
    (root / "deploy" / "compose.yaml").write_text(
        f"services:\n  {SERVICE}:\n    image: {IMAGE}\n", encoding="utf-8"
    )
    return root


def binding(
    compose_file: str = COMPOSE_FILE, compose_service: str = SERVICE
) -> DeploymentBinding:
    return DeploymentBinding(compose_file=compose_file, compose_service=compose_service)


def write_compose(root: Path, name: str, content: str) -> str:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return name


def test_exception_hierarchy_is_rooted_at_discovery_catalog_error() -> None:
    for exc_type in (
        RepositoryComposeObservationError,
        RepositoryComposeObservationPathError,
        RepositoryComposeObservationSizeError,
        RepositoryComposeObservationYamlError,
        RepositoryComposeObservationDocumentError,
        RepositoryComposeObservationValidationError,
    ):
        assert issubclass(exc_type, DiscoveryCatalogError)


def test_max_compose_file_bytes_constant() -> None:
    assert MAX_COMPOSE_FILE_BYTES == 256 * 1024


def test_happy_path_observes_bound_image(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    observation = RepositoryComposeImageObservationAcquirer(root).observe(binding())

    assert observation == RepositoryComposeImageObservation(
        compose_file=COMPOSE_FILE, compose_service=SERVICE, image=IMAGE
    )
    assert observation.model_dump() == {
        "compose_file": COMPOSE_FILE,
        "compose_service": SERVICE,
        "image": IMAGE,
    }


@pytest.mark.parametrize(
    "yaml_image,expected",
    [
        ("ghcr.io/acme/app:v1.2.3", "ghcr.io/acme/app:v1.2.3"),
        ('"ghcr.io/acme/app:v1.2.3"', "ghcr.io/acme/app:v1.2.3"),
        ("'ghcr.io/acme/app:v1.2.3'", "ghcr.io/acme/app:v1.2.3"),
        ("localhost:5000/acme/app:latest", "localhost:5000/acme/app:latest"),
        ("ghcr.io/acme/app", "ghcr.io/acme/app"),
        (
            "ghcr.io/acme/app@sha256:" + "0" * 64,
            "ghcr.io/acme/app@sha256:" + "0" * 64,
        ),
        ("a" * 1024, "a" * 1024),
    ],
)
def test_exact_literal_image_preserved(
    tmp_path: Path, yaml_image: str, expected: str
) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(
        f"services:\n  {SERVICE}:\n    image: {yaml_image}\n", encoding="utf-8"
    )

    observation = RepositoryComposeImageObservationAcquirer(root).observe(binding())

    assert observation.image == expected


def test_observations_are_deterministic(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    acquirer = RepositoryComposeImageObservationAcquirer(root)

    first = [acquirer.observe(binding()) for _ in range(3)]
    second = [
        RepositoryComposeImageObservationAcquirer(root).observe(binding())
        for _ in range(3)
    ]

    assert first == second
    assert all(item == first[0] for item in first)


def test_observation_is_independent_of_cwd(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    acquirer = RepositoryComposeImageObservationAcquirer(root)

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        from_cwd = acquirer.observe(binding())
        os.chdir("/")
        from_slash = acquirer.observe(binding())
    finally:
        os.chdir(original_cwd)

    assert from_cwd == from_slash
    assert from_slash.image == IMAGE


@pytest.mark.parametrize(
    "content",
    [
        "services:\n  app:\n    image: ghcr.io/acme/app:v1.2.3\n",
        (
            "services:\n  app:\n    image: ghcr.io/acme/app:v1.2.3\n"
            "    restart: unless-stopped\n"
        ),
        "name: demo\nservices:\n  app:\n    image: ghcr.io/acme/app:v1.2.3\n",
        (
            "name: demo\n"
            "version: '3.8'\n"
            "networks:\n  default: {name: demo}\n"
            "volumes: [db-data]\n"
            "services:\n"
            "  app:\n"
            "    image: ghcr.io/acme/app:v1.2.3\n"
            "    ports:\n      - '8080:80'\n"
            "    depends_on: [db]\n"
            "  db:\n"
            "    image: postgres:16\n"
            "    volumes: [db-data:/var/lib/postgresql/data]\n"
        ),
    ],
)
def test_unrelated_valid_compose_keys_accepted(tmp_path: Path, content: str) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(content, encoding="utf-8")

    observation = RepositoryComposeImageObservationAcquirer(root).observe(binding())

    assert observation.image == "ghcr.io/acme/app:v1.2.3"


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def test_missing_repository_root_rejected(tmp_path: Path) -> None:
    with pytest.raises(RepositoryComposeObservationPathError, match="does not exist"):
        RepositoryComposeImageObservationAcquirer(tmp_path / "missing").observe(
            binding()
        )


@pytest.mark.parametrize("relative", ["repo", "./repo", "../repo", "deploy/../repo"])
def test_relative_repository_root_rejected(tmp_path: Path, relative: str) -> None:
    """A relative repository_root is rejected at construction; it is never
    normalized against the process working directory."""
    compose_root(tmp_path)

    with pytest.raises(RepositoryComposeObservationPathError, match="absolute"):
        RepositoryComposeImageObservationAcquirer(Path(relative))


def test_repository_root_must_be_directory(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    file_as_root = root / "deploy" / "compose.yaml"

    with pytest.raises(RepositoryComposeObservationPathError, match="directory"):
        RepositoryComposeImageObservationAcquirer(file_as_root).observe(binding())


def test_symlink_repository_root_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    link = tmp_path / "repo-link"
    link.symlink_to(root)

    with pytest.raises(RepositoryComposeObservationPathError, match="symlink"):
        RepositoryComposeImageObservationAcquirer(link).observe(binding())


def test_missing_intermediate_directory_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    with pytest.raises(RepositoryComposeObservationPathError, match="intermediate"):
        RepositoryComposeImageObservationAcquirer(root).observe(
            binding(compose_file="nested/missing/deploy/compose.yaml")
        )


def test_intermediate_component_must_be_directory(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / "file-as-dir").write_text("x", encoding="utf-8")

    with pytest.raises(RepositoryComposeObservationPathError, match="intermediate"):
        RepositoryComposeImageObservationAcquirer(root).observe(
            binding(compose_file="file-as-dir/compose.yaml")
        )


def test_missing_compose_target_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    with pytest.raises(RepositoryComposeObservationPathError, match="does not exist"):
        RepositoryComposeImageObservationAcquirer(root).observe(
            binding(compose_file="deploy/absent.yaml")
        )


def test_target_directory_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / "deploy" / "adir.yaml").mkdir()

    with pytest.raises(RepositoryComposeObservationPathError, match="regular file"):
        RepositoryComposeImageObservationAcquirer(root).observe(
            binding(compose_file="deploy/adir.yaml")
        )


def test_symlink_target_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / "deploy" / "real.yaml").write_text(
        f"services:\n  {SERVICE}:\n    image: {IMAGE}\n", encoding="utf-8"
    )
    (root / "deploy" / "compose.yaml").unlink()
    (root / "deploy" / "compose.yaml").symlink_to(root / "deploy" / "real.yaml")

    with pytest.raises(RepositoryComposeObservationPathError, match="symlink"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_symlink_intermediate_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / "real").mkdir()
    (root / "real" / "compose.yaml").write_text(
        f"services:\n  {SERVICE}:\n    image: {IMAGE}\n", encoding="utf-8"
    )
    (root / "deploy" / "compose.yaml").unlink()
    (root / "deploy").rmdir()
    (root / "deploy").symlink_to(root / "real")

    with pytest.raises(RepositoryComposeObservationPathError, match="symlink"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_symlink_escape_of_root_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "evil.yaml").write_text(
        "services:\n  app:\n    image: evil/x:v1\n", encoding="utf-8"
    )
    (root / "deploy" / "compose.yaml").unlink()
    (root / "deploy").rmdir()
    (root / "deploy").symlink_to(outside)

    with pytest.raises(RepositoryComposeObservationPathError, match="symlink|escape"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_no_arbitrary_raw_compose_path_api(tmp_path: Path) -> None:
    import inspect

    root = compose_root(tmp_path)
    acquirer = RepositoryComposeImageObservationAcquirer(root)

    observe_signature = set(inspect.signature(acquirer.observe).parameters)
    assert observe_signature == {"binding"}
    assert not hasattr(acquirer, "observe_path")
    assert not hasattr(acquirer, "observe_file")


def test_repository_root_must_be_injected(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        RepositoryComposeImageObservationAcquirer()


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------


def test_default_max_file_bytes_is_256_kib(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    acquirer = RepositoryComposeImageObservationAcquirer(root)
    assert acquirer._max_file_bytes == MAX_COMPOSE_FILE_BYTES


@pytest.mark.parametrize(
    "bad", [0, -1, -256, "256", 256.0, 1.5, True, False, None, [256]]
)
def test_invalid_max_file_bytes_rejected(tmp_path: Path, bad: object) -> None:
    root = compose_root(tmp_path)
    with pytest.raises(RepositoryComposeObservationSizeError):
        RepositoryComposeImageObservationAcquirer(root, max_file_bytes=bad)  # type: ignore[arg-type]


def test_exactly_max_bytes_accepted(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    # A real (single-document) YAML mapping padded with spaces to exactly
    # MAX_COMPOSE_FILE_BYTES. The size bound must accept it and the failure
    # must be a document error, not a size error.
    head = b"services: {}"
    (root / COMPOSE_FILE).write_bytes(
        head + b" " * (MAX_COMPOSE_FILE_BYTES - len(head) - 1) + b"\n"
    )
    assert (root / COMPOSE_FILE).stat().st_size == MAX_COMPOSE_FILE_BYTES

    with pytest.raises(
        RepositoryComposeObservationDocumentError, match="missing 'app'"
    ):
        # A document (not size) error proves the MAX-byte bound is accepted
        # and the file reached parsing.
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_max_plus_one_bytes_rejected_before_yaml_parse(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    # Valid YAML content that is one byte too large: if the YAML parser ran
    # first this would be a document error instead of a size error.
    tail = b"services:\n  app: {} #"
    (root / COMPOSE_FILE).write_bytes(
        b" " * (MAX_COMPOSE_FILE_BYTES - len(tail) + 1) + tail
    )
    assert (root / COMPOSE_FILE).stat().st_size == MAX_COMPOSE_FILE_BYTES + 1

    with pytest.raises(RepositoryComposeObservationSizeError, match="exceeds the"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_custom_max_file_bytes_enforced(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_bytes(b"#" * 100)

    with pytest.raises(RepositoryComposeObservationSizeError):
        RepositoryComposeImageObservationAcquirer(root, max_file_bytes=99).observe(
            binding()
        )


def test_non_utf8_compose_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_bytes(b"services:\n  app:\n    image: a\xffb:v1\n")

    with pytest.raises(RepositoryComposeObservationYamlError, match="UTF-8"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


# ---------------------------------------------------------------------------
# YAML parsing
# ---------------------------------------------------------------------------


def test_malformed_yaml_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(
        "services:\n  app:\n   image: a/b:v1\n\t- x\n", encoding="utf-8"
    )

    with pytest.raises(RepositoryComposeObservationYamlError, match="parse"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_empty_file_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text("", encoding="utf-8")

    with pytest.raises(RepositoryComposeObservationDocumentError, match="document"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_multi_document_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(
        "a: 1\n---\nservices:\n  app:\n    image: x/y:v1\n", encoding="utf-8"
    )

    with pytest.raises(RepositoryComposeObservationDocumentError, match="exactly one"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_trailing_document_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(
        f"services:\n  {SERVICE}:\n    image: {IMAGE}\n---\n", encoding="utf-8"
    )

    with pytest.raises(RepositoryComposeObservationDocumentError, match="exactly one"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_unsafe_python_tag_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(
        'services: !!python/serialize "x"\n', encoding="utf-8"
    )

    with pytest.raises(RepositoryComposeObservationYamlError, match="unsafe|non-safe"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_unsafe_vendor_tag_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(
        "services: {app: {image: !!x/compose ghcr.io/a/b:v1}}\n", encoding="utf-8"
    )

    with pytest.raises(RepositoryComposeObservationYamlError, match="unsafe|non-safe"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_root_must_be_mapping(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text("- a\n- b\n", encoding="utf-8")

    with pytest.raises(RepositoryComposeObservationDocumentError, match="mapping"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_deeply_nested_yaml_fails_closed_without_recursion_error(
    tmp_path: Path,
) -> None:
    """Regression: pathological nesting below the file-size bound must
    raise RepositoryComposeObservationDocumentError, never RecursionError.

    20000 nested single-item sequences (~60 KiB) exceed the explicit node
    depth bound by a wide margin. Whether PyYAML's own composer raises
    RecursionError first, or composes successfully and the iterative node
    walkers hit the depth guard, the observable failure is the same typed
    document error.
    """
    root = compose_root(tmp_path)
    depth = 20000
    content = "[" * depth + "1" + "]" * depth
    (root / COMPOSE_FILE).write_text(content, encoding="utf-8")
    assert (root / COMPOSE_FILE).stat().st_size < MAX_COMPOSE_FILE_BYTES

    with pytest.raises(
        RepositoryComposeObservationDocumentError, match="nesting exceeds"
    ):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def _forcing_recursion_error(func: object) -> object:
    def wrapped(*args: object, **kwargs: object) -> object:
        raise RecursionError("maximum recursion depth exceeded")

    return wrapped


def test_recursion_error_from_yaml_compose_converted_to_document_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A RecursionError escaping yaml.compose_all is converted to a typed,
    bounded document error and never leaks to the caller."""
    import yaml as _yaml

    root = compose_root(tmp_path)
    monkeypatch.setattr(
        _yaml, "compose_all", _forcing_recursion_error(_yaml.compose_all)
    )

    with pytest.raises(
        RepositoryComposeObservationDocumentError, match="nesting exceeds"
    ) as exc_info:
        RepositoryComposeImageObservationAcquirer(root).observe(binding())
    assert isinstance(exc_info.value.__cause__, RecursionError)


# ---------------------------------------------------------------------------
# Document shape
# ---------------------------------------------------------------------------


def test_missing_services_key_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text("volumes: {}\n", encoding="utf-8")

    with pytest.raises(
        RepositoryComposeObservationDocumentError, match="missing 'services'"
    ):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_services_must_be_mapping(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text("services:\n  - app\n", encoding="utf-8")

    with pytest.raises(
        RepositoryComposeObservationDocumentError, match="must be a mapping"
    ):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_bound_service_must_exist(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(
        "services:\n  other:\n    image: a/b:v1\n", encoding="utf-8"
    )

    with pytest.raises(
        RepositoryComposeObservationDocumentError, match=f"missing '{SERVICE}'"
    ):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_bound_service_must_be_mapping(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(
        f"services:\n  {SERVICE}: latest\n", encoding="utf-8"
    )

    with pytest.raises(
        RepositoryComposeObservationDocumentError, match="must be a mapping"
    ):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_missing_local_image_key_rejected(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(
        f"services:\n  {SERVICE}:\n    build: .\n", encoding="utf-8"
    )

    with pytest.raises(
        RepositoryComposeObservationValidationError, match="local image"
    ):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_extends_without_local_image_fails_closed(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / "base.yaml").write_text(
        "services:\n  base:\n    image: base/x:v1\n", encoding="utf-8"
    )
    (root / COMPOSE_FILE).write_text(
        "services:\n  app:\n    extends:\n      file: base.yaml\n      service: base\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RepositoryComposeObservationValidationError, match="local image"
    ):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_image_inherited_from_environment_not_observed(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(
        f"services:\n  {SERVICE}:\n    environment:\n      IMAGE: a/b:v1\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RepositoryComposeObservationValidationError, match="local image"
    ):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


# ---------------------------------------------------------------------------
# Image validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "image_node",
    [
        "image: 123\n",
        "image: 12.5\n",
        "image: true\n",
        "image: null\n",
        "image:\n",
        "image:\n  repository: a/b\n  tag: v1\n",
        "image: [a/b, v1]\n",
    ],
)
def test_non_string_image_rejected(tmp_path: Path, image_node: str) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(
        f"services:\n  {SERVICE}:\n    {image_node}", encoding="utf-8"
    )

    with pytest.raises(RepositoryComposeObservationValidationError):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


@pytest.mark.parametrize(
    "image_node",
    [
        'image: ""\n',
        "image: ''\n",
        'image: "a/b:v1 "\n',
        'image: " a/b:v1"\n',
        'image: "a/b:v1\t"\n',
        "image: " + '"' + "a" * 1025 + '"\n',
    ],
)
def test_image_literal_validation(tmp_path: Path, image_node: str) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(
        f"services:\n  {SERVICE}:\n    {image_node}", encoding="utf-8"
    )

    with pytest.raises(RepositoryComposeObservationValidationError):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_image_length_message_uses_character_bound(tmp_path: Path) -> None:
    """The length bound is a character bound; the message says so."""
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(
        "services:\n  app:\n    image: " + '"' + "a" * 1025 + '"\n',
        encoding="utf-8",
    )

    with pytest.raises(
        RepositoryComposeObservationValidationError,
        match=r"exceeds the 1024 character bound",
    ):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_image_at_exact_character_bound_accepted(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    image = "a" * 1024
    (root / COMPOSE_FILE).write_text(
        f"services:\n  {SERVICE}:\n    image: {image}\n", encoding="utf-8"
    )

    observation = RepositoryComposeImageObservationAcquirer(root).observe(binding())

    assert observation.image == image


@pytest.mark.parametrize(
    "image_node",
    [
        "image: ${IMAGE_REF}\n",
        "image: ${IMG:-default}\n",
        'image: "$IMG"\n',
        "image: ghcr.io/a/${TAG}\n",
    ],
)
def test_interpolation_rejected(tmp_path: Path, image_node: str) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(
        f"services:\n  {SERVICE}:\n    {image_node}", encoding="utf-8"
    )

    with pytest.raises(
        RepositoryComposeObservationValidationError,
        match="interpolation|environment",
    ):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


# ---------------------------------------------------------------------------
# Anchors, aliases, duplicate keys
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        "services:\n  app: &svc\n    image: a/b:v1\n",
        "defaults: &d\n  image: a/b:v1\nservices:\n  app:\n    <<: *d\n",
        "services:\n  app:\n    image: &img a/b:v1\n",
        "x: &a 1\nservices:\n  app:\n    image: *a\n",
    ],
)
def test_anchors_aliases_rejected_anywhere(tmp_path: Path, content: str) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(content, encoding="utf-8")

    with pytest.raises(RepositoryComposeObservationYamlError, match="anchor|alias"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


@pytest.mark.parametrize(
    "content",
    [
        "services:\n  app:\n    image: a/b:v1\n    image: c/d:v2\n",
        "services:\n  app:\n    image: a/b:v1\n  app:\n    image: c/d:v2\n",
        "services: {}\nservices: {app: {image: a/b:v1}}\n",
        "image: a\nimage: b\nservices:\n  app:\n    image: a/b:v1\n",
    ],
)
def test_duplicate_mapping_keys_rejected(tmp_path: Path, content: str) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(content, encoding="utf-8")

    with pytest.raises(RepositoryComposeObservationDocumentError, match="Duplicate"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


@pytest.mark.parametrize(
    "content",
    [
        # Duplicate key in a mapping nested inside a sequence item.
        (
            "services:\n  app:\n    image: a/b:v1\n    depends_on:\n"
            "      - db: 1\n        db: 2\n"
        ),
        # Duplicate key in a mapping one sequence level deeper.
        (
            "services:\n  app:\n    image: a/b:v1\n    extra:\n"
            "      -\n        - db: 1\n          db: 2\n"
        ),
        # Duplicate key inside a sequence that is a mapping value of a
        # sequence item (mixed mapping/sequence nesting).
        (
            "services:\n  app:\n    image: a/b:v1\n    extra:\n"
            "      - name: x\n        items:\n          - k: 1\n"
            "            k: 2\n"
        ),
    ],
)
def test_duplicate_mapping_keys_nested_in_sequences_rejected(
    tmp_path: Path, content: str
) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(content, encoding="utf-8")

    with pytest.raises(RepositoryComposeObservationDocumentError, match="Duplicate"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


@pytest.mark.parametrize(
    "content",
    [
        # Merge key in a mapping nested inside a sequence item.
        (
            "defaults: &d\n  image: a/b:v1\n"
            "services:\n  app:\n    image: a/b:v1\n    depends_on:\n"
            "      - <<: *d\n"
        ),
        # Merge key in a mapping one sequence level deeper.
        (
            "defaults: &d\n  image: a/b:v1\n"
            "services:\n  app:\n    image: a/b:v1\n    extra:\n"
            "      -\n        - <<: *d\n"
        ),
    ],
)
def test_merge_keys_nested_in_sequences_rejected(tmp_path: Path, content: str) -> None:
    root = compose_root(tmp_path)
    (root / COMPOSE_FILE).write_text(content, encoding="utf-8")

    # Fail-closed: the alias used for the merge is rejected by the
    # anchor/alias scan, or the merge key itself by the merge-key check.
    # Either way a nested merge construct in a sequence is never accepted.
    with pytest.raises(RepositoryComposeObservationError, match="merge|anchor|alias"):
        RepositoryComposeImageObservationAcquirer(root).observe(binding())


def test_walker_rejects_merge_key_nested_in_sequence_directly() -> None:
    """The duplicate/merge walker itself rejects a merge key found in a
    mapping nested inside a sequence item (no anchors/aliases involved, so
    this exercises the walker's sequence recursion directly)."""
    import yaml as _yaml
    from yaml.nodes import MappingNode

    from app.discovery.repository_compose_observation import (
        RepositoryComposeImageObservationAcquirer as _Acquirer,
    )

    node = _yaml.compose(
        "services:\n  app:\n    extra:\n      - {image: a/b:v1, <<: 1}\n"
    )
    assert isinstance(node, MappingNode)

    with pytest.raises(RepositoryComposeObservationYamlError, match="merge"):
        _Acquirer._reject_duplicate_keys(node, "deploy/compose.yaml")


# ---------------------------------------------------------------------------
# Acquirer contract
# ---------------------------------------------------------------------------


def test_observe_requires_validated_deployment_binding(tmp_path: Path) -> None:
    root = compose_root(tmp_path)
    acquirer = RepositoryComposeImageObservationAcquirer(root)

    with pytest.raises(
        RepositoryComposeObservationValidationError, match="DeploymentBinding"
    ):
        acquirer.observe({"compose_file": COMPOSE_FILE, "compose_service": SERVICE})  # type: ignore[arg-type]
    with pytest.raises(RepositoryComposeObservationValidationError):
        acquirer.observe("deploy/compose.yaml")  # type: ignore[arg-type]
    with pytest.raises(RepositoryComposeObservationValidationError):
        acquirer.observe(None)  # type: ignore[arg-type]


def test_repository_compose_image_observation_model_unchanged() -> None:
    fields = RepositoryComposeImageObservation.model_fields

    assert list(fields) == ["compose_file", "compose_service", "image"]
    assert set(fields) == {"compose_file", "compose_service", "image"}


def test_deployment_binding_model_unchanged() -> None:
    fields = DeploymentBinding.model_fields

    assert list(fields) == [
        "compose_file",
        "compose_service",
        "mutable_property",
        "deployment_method",
    ]
