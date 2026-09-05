from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def _read(relative: str) -> str:
    return ROOT.joinpath(relative).read_text(encoding="utf-8")


def test_v044_release_closure_is_documented_as_evidence_only() -> None:
    changelog = _read("CHANGELOG.md")
    roadmap = _read("ROADMAP.md")
    contract = _read("docs/architecture/controlled-dequeue-admission-v1.md")

    assert "#### v0.44 P0-P5 - Controlled Dequeue Admission" in changelog
    assert "P5 adds focused tests and release documentation only." in changelog
    assert "## Completed v0.44 plan - Controlled Dequeue Admission" in roadmap
    assert "P0-P5 are complete." in roadmap
    assert (
        "Status: **Atlas v0.44 P0-P5 closed controlled dequeue admission contract**."
        in contract
    )

    closure_text = f"{changelog}\n{roadmap}\n{contract}".lower()
    for phrase in (
        "no live dequeue",
        "queue polling consumer",
        "worker start/invocation",
        "agent invocation",
        "execution start",
        "docker/podman/container/shell/",
        "provider/repository/in-guest",
        "compose.execution-smoke.override.yaml",
    ):
        assert phrase in closure_text


def test_v044_release_closure_does_not_add_effect_configuration() -> None:
    assert not ROOT.joinpath("compose.execution-smoke.override.yaml").exists()

    production_files = (
        "services/atlas-core/app/controlled_dequeue_admission/contract.py",
        "services/atlas-core/app/controlled_dequeue_admission/service.py",
        "services/atlas-core/app/controlled_dequeue_admission/store.py",
        "services/atlas-core/app/routes/controlled_dequeue_admission.py",
    )
    forbidden_import_markers = {
        "agent",
        "container",
        "deployment",
        "dispatch",
        "docker",
        "httpx",
        "podman",
        "provider",
        "repository",
        "requests",
        "rollback",
        "scheduler",
        "socket",
        "subprocess",
        "transport",
        "workflow",
        "worker",
    }
    forbidden_def_names = {
        "ack",
        "acknowledge",
        "claim",
        "consume",
        "dequeue",
        "deploy",
        "dispatch",
        "execute",
        "invoke_agent",
        "lease",
        "poll",
        "remove",
        "resend",
        "retry",
        "rollback",
        "run",
        "schedule",
        "start",
        "start_worker",
    }
    forbidden_call_names = (forbidden_def_names - {"execute"}) | {
        "create_subprocess_exec",
        "create_subprocess_shell",
        "exec",
        "fork",
        "popen",
        "spawn",
        "system",
    }

    for relative in production_files:
        tree = ast.parse(_read(relative))
        imports = {
            alias.name if isinstance(node, ast.Import) else node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        definitions = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        }
        calls = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        assert not [
            name
            for name in imports
            if any(marker in name for marker in forbidden_import_markers)
        ]
        assert definitions.isdisjoint(forbidden_def_names)
        assert calls.isdisjoint(forbidden_call_names)
