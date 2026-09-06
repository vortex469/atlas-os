from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def _read(relative: str) -> str:
    return ROOT.joinpath(relative).read_text(encoding="utf-8")


def _python_tree(relative: str) -> ast.Module:
    return ast.parse(_read(relative))


def test_v048_release_closure_is_documented_as_activation_evidence_only() -> None:
    changelog = _read("CHANGELOG.md")
    roadmap = _read("ROADMAP.md")
    contract = _read(
        "docs/architecture/worker-binding-activation-evidence-v1.md"
    )

    assert "#### v0.48 P0-P5 - Worker Binding Activation Evidence" in changelog
    assert "P5 adds focused tests and release documentation only." in changelog
    assert "## Completed v0.48 plan - Worker Binding Activation Evidence" in roadmap
    assert "P0-P5 are complete." in roadmap
    assert (
        "Status: **Atlas v0.48 P0-P5 closed worker binding activation "
        "evidence contract**."
        in contract
    )

    closure_text = f"{changelog}\n{roadmap}\n{contract}".lower()
    for phrase in (
        "one active same-owner v0.47",
        "worker_binding_activation_evidence_recorded",
        "worker_activation_runtime_not_defined",
        "store_contact_not_defined",
        "runtime_contact_not_defined",
        "queue_claim_not_defined",
        "queue_lease_not_defined",
        "queue_ack_not_defined",
        "worker_start_admission_not_defined",
        "worker_start_not_defined",
        "agent_invocation_not_defined",
        "execution_start_boundary_not_defined",
        "agent/execution-worker zero-consumer",
        "compose.execution-smoke.override.yaml",
    ):
        assert phrase in closure_text


def test_v048_only_activation_evidence_advanced_and_later_authority_blocked() -> None:
    contract = _read(
        "services/atlas-core/app/worker_binding_activation_evidence/contract.py"
    )

    assert (
        'eligibility: Literal["worker_binding_activation_evidence_recorded"]'
        in contract
    )
    assert "SUCCESS_BLOCKERS as V047_SUCCESS_BLOCKERS" in contract
    assert "WorkerBindingActivationPreflightV1" in contract
    assert "WorkerBindingActivationPreflightStatusV1" in contract
    assert "recognized_v047_preflight_count" in contract

    for blocker in (
        '"worker_activation_runtime_not_defined"',
        '"store_contact_not_defined"',
        '"runtime_contact_not_defined"',
        '"queue_claim_not_defined"',
        '"queue_lease_not_defined"',
        '"queue_ack_not_defined"',
        '"worker_start_admission_not_defined"',
        '"worker_start_not_defined"',
        '"agent_invocation_not_defined"',
        '"execution_start_boundary_not_defined"',
    ):
        assert blocker in contract

    for fixed_false_marker in (
        "caller_supplied_credentials_allowed: Literal[False] = False",
        "caller_supplied_endpoint_allowed: Literal[False] = False",
        "caller_supplied_command_allowed: Literal[False] = False",
        "caller_supplied_payload_allowed: Literal[False] = False",
        "payload_schema_defined: Literal[False] = False",
        "payload_constructed: Literal[False] = False",
        "payload_serialized: Literal[False] = False",
        "queue_polling_allowed: Literal[False] = False",
        "queue_claim_allowed: Literal[False] = False",
        "queue_lease_allowed: Literal[False] = False",
        "queue_ack_allowed: Literal[False] = False",
        "queue_consume_allowed: Literal[False] = False",
        "queue_mutation_allowed: Literal[False] = False",
        "worker_store_contact_allowed: Literal[False] = False",
        "worker_runtime_contact_allowed: Literal[False] = False",
        "worker_contact_allowed: Literal[False] = False",
        "worker_start_admission_allowed: Literal[False] = False",
        "worker_start_allowed: Literal[False] = False",
        "worker_invocation_allowed: Literal[False] = False",
        "agent_invocation_allowed: Literal[False] = False",
        "execution_authorization_allowed: Literal[False] = False",
        "execution_start_allowed: Literal[False] = False",
        "process_execution_allowed: Literal[False] = False",
        "store_contact_allowed: Literal[False] = False",
        "runtime_contact_allowed: Literal[False] = False",
        "dispatch_allowed: Literal[False] = False",
        "retry_allowed: Literal[False] = False",
        "resend_allowed: Literal[False] = False",
        "scheduler_allowed: Literal[False] = False",
        "workflow_start_allowed: Literal[False] = False",
        "shell_execution_allowed: Literal[False] = False",
        "provider_mutation_allowed: Literal[False] = False",
        "repository_mutation_allowed: Literal[False] = False",
        "in_guest_mutation_allowed: Literal[False] = False",
        "installation_allowed: Literal[False] = False",
        "deployment_allowed: Literal[False] = False",
        "rollback_allowed: Literal[False] = False",
        "replay_bypass_allowed: Literal[False] = False",
        "artifact_publication_allowed: Literal[False] = False",
        "tag_push_allowed: Literal[False] = False",
        "release_publication_allowed: Literal[False] = False",
        "binding_activation_allowed: Literal[False] = False",
        "worker_activation_runtime_allowed: Literal[False] = False",
    ):
        assert fixed_false_marker in contract


def test_v048_release_closure_does_not_add_effect_configuration() -> None:
    assert not ROOT.joinpath("compose.execution-smoke.override.yaml").exists()

    production_files = (
        "services/atlas-core/app/worker_binding_activation_evidence/contract.py",
        "services/atlas-core/app/worker_binding_activation_evidence/service.py",
        "services/atlas-core/app/worker_binding_activation_evidence/store.py",
        "services/atlas-core/app/routes/worker_binding_activation_evidence.py",
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
        "worker_queue",
        "worker_runtime",
    }
    forbidden_def_names = {
        "ack",
        "acknowledge",
        "activate",
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
        "publish",
        "remove",
        "resend",
        "retry",
        "rollback",
        "run",
        "schedule",
        "send",
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
            if isinstance(node, ast.Import | ast.ImportFrom)
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
            and isinstance(node.func, ast.Attribute | ast.Name)
        }
        assert not [
            name
            for name in imports
            if any(marker in name for marker in forbidden_import_markers)
        ]
        assert definitions.isdisjoint(forbidden_def_names)
        assert calls.isdisjoint(forbidden_call_names)


def test_v048_default_off_api_ui_agent_and_execution_worker_isolation() -> None:
    service = _read(
        "services/atlas-core/app/worker_binding_activation_evidence/service.py"
    )
    store = _read("services/atlas-core/app/worker_binding_activation_evidence/store.py")
    route = _read("services/atlas-core/app/routes/worker_binding_activation_evidence.py")
    main = _read("services/atlas-core/app/main.py")
    mission_control_structural = _read(
        "services/mission-control/src/security/"
        "workerBindingActivationEvidenceStructural.test.ts"
    )

    assert "enabled: bool = False" in service
    assert "no activation or worker contact exists" in service
    assert "read_owned" in service
    assert "resolve_idempotency" in service
    assert "append_indeterminate" in service
    assert "UPDATE worker_binding_activation_evidence" not in store
    assert "DELETE FROM worker_binding_activation_evidence" not in store
    assert "worker_binding_activation_evidence_service" not in main
    assert "create_worker_binding_activation_evidence_service" not in main

    assert '@router.post(\n    "/{candidate_record_id}/worker-binding-activation-evidence"' in route
    assert '@router.get(\n    "/{candidate_record_id}/worker-binding-activation-evidence"' in route
    assert (
        '@router.get(\n    "/{candidate_record_id}/worker-binding-activation-evidence/'
        '{activation_evidence_id}"'
        in route
    )
    for forbidden_method in ("@router.put", "@router.patch", "@router.delete"):
        assert forbidden_method not in route
    assert "require_operator_mutation" in route
    assert "require_operator_permission" in route

    assert "v0.48 worker binding activation evidence Mission Control boundary" in (
        mission_control_structural
    )
    assert r"atlas\.(post|put|patch|delete)" in mission_control_structural
    assert "worker-binding-activation-evidence|WorkerBindingActivationEvidence" in (
        mission_control_structural
    )
    assert "expect(consumers).toEqual" in mission_control_structural

    markers = (
        "worker_binding_activation_evidence",
        "WorkerBindingActivationEvidence",
        "worker-binding-activation-evidence",
    )
    app_roots = (
        ROOT / "services" / "atlas-agent" / "app",
        ROOT / "services" / "atlas-execution-worker" / "atlas_execution_worker",
    )
    violations = [
        f"{path.relative_to(ROOT)} -> {marker}"
        for app_root in app_roots
        for path in app_root.rglob("*.py")
        if "__pycache__" not in path.parts
        for marker in markers
        if marker in path.read_text(encoding="utf-8")
    ]
    assert violations == []
