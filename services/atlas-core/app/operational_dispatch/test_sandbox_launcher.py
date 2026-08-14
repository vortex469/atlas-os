from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _isolated_launcher(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    atlas_root = tmp_path / "atlas"
    scripts = atlas_root / "scripts"
    scripts.mkdir(parents=True)
    source = Path(__file__).parents[4] / "scripts" / "atlas-operational-sandbox"
    launcher = scripts / source.name
    shutil.copy2(source, launcher)

    path_bin = tmp_path / "path-bin"
    path_bin.mkdir()
    for command in ("bash", "dirname"):
        executable = shutil.which(command)
        assert executable is not None
        (path_bin / command).symlink_to(executable)
    environment = os.environ.copy()
    environment["PATH"] = str(path_bin)
    return launcher, environment


def test_launcher_uses_atlas_interpreter_when_path_has_no_python(tmp_path: Path) -> None:
    launcher, environment = _isolated_launcher(tmp_path)
    atlas_root = launcher.parent.parent
    interpreter = atlas_root / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    capture = tmp_path / "python-arguments"
    interpreter.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$ATLAS_LAUNCHER_CAPTURE\"\n",
        encoding="utf-8",
    )
    interpreter.chmod(0o700)
    environment["ATLAS_LAUNCHER_CAPTURE"] = str(capture)

    result = subprocess.run(
        [str(launcher), "--ledger", str(tmp_path / "sandbox.db")],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert capture.read_text(encoding="utf-8").splitlines() == [
        "-m",
        "app.operational_dispatch.sandbox",
        "--ledger",
        str(tmp_path / "sandbox.db"),
    ]


def test_launcher_fails_before_python_or_ledger_when_interpreter_missing(
    tmp_path: Path,
) -> None:
    launcher, environment = _isolated_launcher(tmp_path)
    capture = tmp_path / "python-arguments"
    ledger = tmp_path / "sandbox.db"
    environment["ATLAS_LAUNCHER_CAPTURE"] = str(capture)

    result = subprocess.run(
        [str(launcher), "--ledger", str(ledger)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    expected = launcher.parent.parent / ".venv" / "bin" / "python"
    assert result.returncode == 127
    assert result.stdout == ""
    assert result.stderr.strip() == (
        f"Atlas sandbox interpreter unavailable: expected executable {expected}"
    )
    assert not capture.exists()
    assert not ledger.exists()
