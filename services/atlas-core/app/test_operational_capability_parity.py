"""Release assertion coverage for the cross-service capability boundary."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARITY_FILES = (
    "services/atlas-agent/app/candidate_planning/models.py",
    "services/atlas-agent/app/candidate_planning/operational_translation.py",
    "services/atlas-core/app/operational_dispatch/registry.py",
    "services/atlas-core/app/operational_dispatch/production.py",
    "services/atlas-core/app/execution_candidates/operational_capabilities.py",
)


def _fixture(tmp_path: Path) -> Path:
    for relative in PARITY_FILES:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    return tmp_path


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["ATLAS_CAPABILITY_PARITY_ROOT"] = str(root)
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/operational-capability-parity")],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_capability_parity_passes_for_reviewed_tuple(tmp_path) -> None:
    result = _run(_fixture(tmp_path))

    assert result.returncode == 0
    assert "restart-service/proxmox/qemu" in result.stdout


def test_capability_parity_fails_on_mismatch(tmp_path) -> None:
    root = _fixture(tmp_path)
    path = root / "services/atlas-core/app/operational_dispatch/registry.py"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'frozenset({"restart-service"})', "frozenset()"
        ),
        encoding="utf-8",
    )

    result = _run(root)

    assert result.returncode != 0
    assert "Core execution gate" in result.stderr
