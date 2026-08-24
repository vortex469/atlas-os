"""Isolation guards for the unexported Home Assistant verifier proof."""

from __future__ import annotations

import ast
import builtins
import io
import os
import socket
import subprocess
import sys
from pathlib import Path

import app.discovery.home_assistant_sigstore_verifier as verifier_module

_MODULE_NAME = "home_assistant_sigstore_verifier"
_FUNCTION_NAME = "verify_home_assistant_2026_8_3_bundle"
_OWNED = {
    f"{_MODULE_NAME}.py",
    f"test_{_MODULE_NAME}.py",
    f"test_{_MODULE_NAME}_isolation.py",
    "home_assistant_registry_attested.py",
    "test_home_assistant_registry_attested.py",
    "test_home_assistant_registry_attested_isolation.py",
    "test_home_assistant_registry_attested_promotion.py",
    "test_home_assistant_image_evidence_provenance.py",
    "test_home_assistant_image_evidence_provenance_isolation.py",
}
_FIXTURE = (
    Path(__file__).parent / "testdata/home_assistant_sigstore/ha-2026.8.3-bundle.json"
)
_TRUST_ROOT = (
    Path(__file__).parent / "trust/sigstore-production-trusted-root.json"
).resolve()


def _tree() -> ast.Module:
    return ast.parse(Path(verifier_module.__file__).read_text(encoding="utf-8"))


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_module_imports_only_contract_and_lazy_sigstore_apis() -> None:
    origins: set[str] = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            origins.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            origins.add(node.module or "")
    assert origins == {
        "__future__",
        "dataclasses",
        "datetime",
        "hashlib",
        "json",
        "pathlib",
        "typing",
        "sigstore.models",
        "sigstore_models.trustroot",
        "sigstore.verify",
        "sigstore.verify.policy",
    }


def test_sigstore_imports_are_inside_verification_call() -> None:
    for node in _tree().body:
        assert not (
            isinstance(node, (ast.Import, ast.ImportFrom))
            and "sigstore" in (getattr(node, "module", "") or "")
        )


def test_no_forbidden_execution_acquisition_or_ambient_trust_capabilities() -> None:
    source = Path(verifier_module.__file__).read_text(encoding="utf-8").lower()
    for forbidden in (
        "verifier.production",
        "clienttrustconfig",
        "trustupdater",
        "subprocess",
        "import cosign",
        "cosign.exe",
        "curl",
        "docker",
        "ghcr",
        "requests",
        "httpx",
        "urllib",
        "rekor_client",
        "fulcio",
        "environ",
        "getenv",
        "platformdirs",
    ):
        assert forbidden not in source


def test_runtime_reads_repository_trust_root_once_without_reopening_or_writing(
    monkeypatch,
) -> None:
    bundle = _FIXTURE.read_bytes()
    reads: list[Path] = []
    original_builtin_open = builtins.open
    original_io_open = io.open
    original_os_open = os.open

    def check_mode(file, mode) -> None:
        assert not any(flag in mode for flag in "wax+"), "filesystem write attempted"
        path = Path(file).resolve()
        reads.append(path)
        assert path == _TRUST_ROOT, f"unexpected runtime read: {path}"

    def guarded_builtin_open(file, mode="r", *args, **kwargs):
        check_mode(file, mode)
        return original_builtin_open(file, mode, *args, **kwargs)

    def guarded_io_open(file, mode="r", *args, **kwargs):
        check_mode(file, mode)
        return original_io_open(file, mode, *args, **kwargs)

    def guarded_os_open(path, flags, *args, **kwargs):
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
        assert flags & write_flags == 0, "filesystem write attempted via os.open"
        resolved = Path(path).resolve()
        reads.append(resolved)
        assert resolved == _TRUST_ROOT, f"unexpected runtime read: {resolved}"
        return original_os_open(path, flags, *args, **kwargs)

    def forbidden_socket(*args, **kwargs):
        raise AssertionError("network/socket access attempted")

    def forbidden_mutation(*args, **kwargs):
        raise AssertionError("filesystem mutation attempted")

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    monkeypatch.setattr(socket, "create_connection", forbidden_socket)
    monkeypatch.setattr(builtins, "open", guarded_builtin_open)
    monkeypatch.setattr(io, "open", guarded_io_open)
    monkeypatch.setattr(os, "open", guarded_os_open)
    for name in ("mkdir", "makedirs", "remove", "rename", "replace", "unlink"):
        monkeypatch.setattr(os, name, forbidden_mutation)

    result = verifier_module.verify_home_assistant_2026_8_3_bundle(bundle_bytes=bundle)
    assert result.image_digest == verifier_module._IMAGE_DIGEST
    assert reads == [_TRUST_ROOT]


def test_clean_home_and_xdg_are_unchanged_and_ambient_cache_is_ignored(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    cache = tmp_path / "cache"
    config = tmp_path / "config"
    for directory in (home, cache, config):
        directory.mkdir()

    fake_root = cache / "sigstore" / "tuf" / "trusted_root.json"
    fake_root.parent.mkdir(parents=True)
    fake_root.write_bytes(_TRUST_ROOT.read_bytes())
    code = """
import socket
from pathlib import Path
from app.discovery.home_assistant_sigstore_verifier import verify_home_assistant_2026_8_3_bundle
import sigstore.models
import sigstore.verify
import sigstore.verify.policy
socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network"))
bundle = Path(__import__('sys').argv[1]).read_bytes()
result = verify_home_assistant_2026_8_3_bundle(bundle_bytes=bundle)
assert result.release_version == "2026.8.3"
"""
    env = os.environ.copy()
    env.update(
        HOME=str(home),
        XDG_CACHE_HOME=str(cache),
        XDG_CONFIG_HOME=str(config),
        PYTHONDONTWRITEBYTECODE="1",
    )
    command = [sys.executable, "-c", code, str(_FIXTURE)]
    subprocess.run(command, cwd=Path(__file__).parents[2], env=env, check=True)
    fake_root.write_text('{"hostile":"ambient trusted root"}', encoding="utf-8")
    expected = _snapshot(tmp_path)
    subprocess.run(command, cwd=Path(__file__).parents[2], env=env, check=True)
    assert _snapshot(tmp_path) == expected
    assert not (cache / "sigstore" / "signing_config.json").exists()
    assert list(home.iterdir()) == []
    assert list(config.iterdir()) == []


def test_verifier_is_not_publicly_exported() -> None:
    init = Path(__file__).with_name("__init__.py").read_text(encoding="utf-8")
    assert _MODULE_NAME not in init
    assert _FUNCTION_NAME not in init


def test_no_production_import_consumer_or_wiring() -> None:
    root = Path(__file__).parents[4]
    references: set[str] = set()
    for path in root.rglob("*.py"):
        if path.name in _OWNED:
            continue
        text = path.read_text(encoding="utf-8")
        if _MODULE_NAME in text or _FUNCTION_NAME in text:
            references.add(str(path.relative_to(root)))
    assert references == set()
