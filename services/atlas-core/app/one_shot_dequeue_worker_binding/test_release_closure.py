from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def _read(relative: str) -> str:
    return ROOT.joinpath(relative).read_text(encoding="utf-8")


def _python_tree(relative: str) -> ast.Module:
    return ast.parse(_read(relative))


def test_v046_release_closure_is_documented_as_evidence_only() -> None:
    changelog = _read("CHANGELOG.md")
    roadmap = _read("ROADMAP.md")
    contract = _read("docs/architecture/one-shot-dequeue-worker-binding-v1.md")

    assert "#### v0.46 P0-P5 - One-Shot Dequeue Worker Binding" in changelog
    assert "P5 adds focused tests and release documentation only." in changelog
    assert "## Completed v0.46 plan - One-Shot Dequeue Worker Binding" in roadmap
    assert "P0-P5 are complete." in roadmap
    assert (
        "Status: **Atlas v0.46 P0-P5 closed one-shot dequeue worker binding contract**."
        in contract
    )

    closure_text = f"{changelog}\n{roadmap}\n{contract}".lower()
    for phrase in (
        "exact v0.45 lineage",
        "one successful same-owner v0.45 one-shot controlled dequeue",
        "one exact same-owner v0.40 worker intake subject",
        "worker store contact",
        "worker runtime contact",
        "worker start/invocation",
        "agent invocation",
        "execution authorization/start",
        "permanent idempotency and subject no-replay",
        "bounded/redacted/secret-free persistence",
        "api/ui isolation",
        "agent/execution-worker zero-consumer",
        "compose.execution-smoke.override.yaml",
    ):
        assert phrase in closure_text


def test_v046_release_closure_does_not_add_effect_configuration() -> None:
    assert not ROOT.joinpath("compose.execution-smoke.override.yaml").exists()

    production_files = (
        "services/atlas-core/app/one_shot_dequeue_worker_binding/contract.py",
        "services/atlas-core/app/one_shot_dequeue_worker_binding/service.py",
        "services/atlas-core/app/one_shot_dequeue_worker_binding/store.py",
        "services/atlas-core/app/routes/one_shot_dequeue_worker_binding.py",
    )
    forbidden_import_markers = {
        "agent",
        "atlas_execution_worker",
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
    }
    forbidden_def_names = {
        "ack",
        "acknowledge",
        "claim",
        "consume",
        "contact_runtime",
        "contact_store",
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
        "start_execution",
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
        tree = _python_tree(relative)
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


def test_v046_exact_lineage_and_zero_consumer_regression_closure() -> None:
    contract = _read("services/atlas-core/app/one_shot_dequeue_worker_binding/contract.py")
    service = _read("services/atlas-core/app/one_shot_dequeue_worker_binding/service.py")
    store = _read("services/atlas-core/app/one_shot_dequeue_worker_binding/store.py")
    route = _read("services/atlas-core/app/routes/one_shot_dequeue_worker_binding.py")
    main = _read("services/atlas-core/app/main.py")
    mission_control_structural = _read(
        "services/mission-control/src/security/oneShotDequeueWorkerBindingStructural.test.ts"
    )

    for lineage_marker in (
        "SUCCESS_BLOCKERS as V045_SUCCESS_BLOCKERS",
        "OneShotControlledDequeueReceiptV1",
        "dequeue_record_fingerprint as v045_dequeue_record_fingerprint",
        "status_fingerprint as v045_status_fingerprint",
        "WorkerIntakeAdmissionV1",
        "record_fingerprint as v040_record_fingerprint",
        "status_fingerprint as v040_status_fingerprint",
        "v0.45 dequeue fingerprint mismatch",
        "v0.40 worker intake fingerprint mismatch",
        "worker subject mismatch",
        "queue item reference mismatch",
        "inherited limits mismatch",
    ):
        assert lineage_marker in contract

    for fixed_false_marker in (
        'store_contact_allowed: Literal[False] = False',
        'runtime_contact_allowed: Literal[False] = False',
        'worker_contact_allowed: Literal[False] = False',
        'worker_start_allowed: Literal[False] = False',
        'agent_invocation_allowed: Literal[False] = False',
        'execution_start_allowed: Literal[False] = False',
        'process_execution_allowed: Literal[False] = False',
        'replay_bypass_allowed: Literal[False] = False',
    ):
        assert fixed_false_marker in contract

    assert "enabled: bool = False" in service
    assert "no worker or runtime contact exists" in service
    assert "read_owned" in service
    assert "resolve_idempotency" in service
    assert "append_indeterminate" in service
    assert "UPDATE one_shot_dequeue_worker" not in store
    assert "DELETE FROM one_shot_dequeue_worker" not in store
    assert "one_shot_dequeue_worker_binding_service" not in main
    assert "create_one_shot_dequeue_worker_binding_service" not in main

    assert 'methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "PUT", "TRACE"]' in route
    assert 'methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"]' in route
    assert "require_operator_mutation" in route
    assert "require_operator_permission" in route

    assert "v0.46 one-shot dequeue worker binding Mission Control boundary" in (
        mission_control_structural
    )
    assert r"atlas\.(post|put|patch|delete)" in mission_control_structural
    assert "one-shot-dequeue-worker-bindings|OneShotDequeueWorkerBinding" in (
        mission_control_structural
    )
    assert "expect(consumers).toEqual" in mission_control_structural
