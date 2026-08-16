from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ACTIVATED_OVERLAY = ROOT / "compose.provider-intent-activated.yaml"
IMPORT_ID = (
    "provider-intent-legacy-policy-import-v1:"
    "80161236828631f0957b3e7d6d390959042ab179641bf45e75df1faf056e7e9b"
)
DATABASE = "/opt/atlas/data/provider_intents.db"


def _render(
    *,
    activated: bool,
    database: str | None = None,
    import_id: str | None = None,
    extra_files: tuple[Path, ...] = (),
):
    command = ["docker", "compose", "-f", "compose.production.yaml"]
    if activated:
        command.extend(("-f", str(ACTIVATED_OVERLAY)))
    for path in extra_files:
        command.extend(("-f", str(path)))
    command.extend(("config", "--format", "json"))
    environment = {
        "HOME": os.environ.get("HOME", "/tmp"),
        "PATH": os.environ["PATH"],
        "ATLAS_ENV_FILE": ".env.example",
        "ATLAS_REPOSITORY_HOST_PATH": str(ROOT),
        "ATLAS_CODEX_AUTH_HOST_PATH": "/tmp/codex-auth.json",
        "ATLAS_OPERATOR_AUTH_VERIFIER_HOST_PATH": "/tmp/operators.json",
        "ATLAS_OPERATOR_AUTH_TRUSTED_ORIGINS": "https://atlas.internal",
        "ATLAS_TLS_CERT_FILE": "/tmp/atlas.crt",
        "ATLAS_TLS_KEY_FILE": "/tmp/atlas.key",
        "ATLAS_HTPASSWD_FILE": "/tmp/atlas.htpasswd",
    }
    for name in (
        "ATLAS_PROVIDER_INTENT_DATABASE",
        "ATLAS_PROVIDER_INTENT_EXPECTED_LEGACY_IMPORT_ID",
    ):
        environment.pop(name, None)
    if database is not None:
        environment["ATLAS_PROVIDER_INTENT_DATABASE"] = database
    if import_id is not None:
        environment["ATLAS_PROVIDER_INTENT_EXPECTED_LEGACY_IMPORT_ID"] = import_id
    return subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_activated_provider_intent_render_is_explicit_and_complete() -> None:
    result = _render(activated=True, database=DATABASE, import_id=IMPORT_ID)
    assert result.returncode == 0, result.stderr
    environment = json.loads(result.stdout)["services"]["atlas-core"]["environment"]
    assert environment["ATLAS_PROVIDER_INTENT_ACTIVATION"] == "activated"
    assert environment["ATLAS_PROVIDER_INTENT_DATABASE"] == DATABASE
    assert environment["ATLAS_PROVIDER_INTENT_EXPECTED_LEGACY_IMPORT_ID"] == IMPORT_ID


def test_inactive_provider_intent_render_preserves_core_defaults() -> None:
    result = _render(activated=False)
    assert result.returncode == 0, result.stderr
    environment = json.loads(result.stdout)["services"]["atlas-core"]["environment"]
    assert "ATLAS_PROVIDER_INTENT_ACTIVATION" not in environment
    assert "ATLAS_PROVIDER_INTENT_DATABASE" not in environment
    assert "ATLAS_PROVIDER_INTENT_EXPECTED_LEGACY_IMPORT_ID" not in environment


@pytest.mark.parametrize("activation_last", [False, True])
def test_activated_overlay_composes_with_full_production_stack(
    tmp_path: Path,
    activation_last: bool,
) -> None:
    candidate = tmp_path / "candidate.yaml"
    candidate.write_text(
        "services:\n  atlas-core:\n    image: atlas-p3d-review-core:local\n"
    )
    full_stack = (
        ROOT / "compose.https.yaml",
        ROOT / "compose.operator-auth.yaml",
    )
    if activation_last:
        result = _render(
            activated=False,
            database=DATABASE,
            import_id=IMPORT_ID,
            extra_files=(*full_stack, candidate, ACTIVATED_OVERLAY),
        )
    else:
        result = _render(
            activated=False,
            database=DATABASE,
            import_id=IMPORT_ID,
            extra_files=(*full_stack, ACTIVATED_OVERLAY, candidate),
        )
    assert result.returncode == 0, result.stderr
    core = json.loads(result.stdout)["services"]["atlas-core"]
    environment = core["environment"]
    assert core["image"] == "atlas-p3d-review-core:local"
    assert environment["ATLAS_PROVIDER_INTENT_ACTIVATION"] == "activated"
    assert environment["ATLAS_PROVIDER_INTENT_DATABASE"] == DATABASE
    assert environment["ATLAS_PROVIDER_INTENT_EXPECTED_LEGACY_IMPORT_ID"] == IMPORT_ID
    assert environment["ATLAS_POLICY_FILE"] == "/opt/atlas/data/config/policies.yaml"
    assert environment["ATLAS_OPERATOR_AUTH_ENABLED"] == "true"
    assert environment["ATLAS_OPERATOR_AUTH_VERIFIER_FILE"] == (
        "/run/atlas-operator-auth/operators.json"
    )


@pytest.mark.parametrize(
    ("database", "import_id", "missing_name"),
    [
        (None, IMPORT_ID, "ATLAS_PROVIDER_INTENT_DATABASE"),
        ("", IMPORT_ID, "ATLAS_PROVIDER_INTENT_DATABASE"),
        (DATABASE, None, "ATLAS_PROVIDER_INTENT_EXPECTED_LEGACY_IMPORT_ID"),
        (DATABASE, "", "ATLAS_PROVIDER_INTENT_EXPECTED_LEGACY_IMPORT_ID"),
    ],
)
def test_activated_provider_intent_render_requires_complete_configuration(
    database: str | None,
    import_id: str | None,
    missing_name: str,
) -> None:
    result = _render(activated=True, database=database, import_id=import_id)
    assert result.returncode != 0
    assert missing_name in result.stderr
