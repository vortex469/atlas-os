from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def _read(relative: str) -> str:
    return ROOT.joinpath(relative).read_text(encoding="utf-8")


def _python_tree(relative: str) -> ast.Module:
    return ast.parse(_read(relative))


def test_v050_release_closure_is_documented_as_prerequisite_only() -> None:
    changelog = _read("CHANGELOG.md")
    roadmap = _read("ROADMAP.md")
    checklist = _read("docs/RELEASE_CHECKLIST.md")
    contract = _read(
        "docs/architecture/"
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-v1.md"
    )

    assert (
        "#### v0.50 P0-P5 - Controlled Worker Queue Claim/Lease/"
        "Acknowledgement Prerequisite"
        in changelog
    )
    assert "P5 adds focused tests and release documentation only." in changelog
    assert (
        "## Completed v0.50 plan - Controlled Worker Queue Claim/Lease/"
        "Acknowledgement Prerequisite"
        in roadmap
    )
    assert "P0-P5 are complete." in roadmap
    assert (
        "## Atlas v0.50 P0-P5 Controlled Worker Queue Claim/Lease/"
        "Acknowledgement Prerequisite - complete"
        in checklist
    )
    assert (
        "Status: **Atlas v0.50 P0-P5 closed controlled worker queue claim/"
        "lease/acknowledgement prerequisite contract**."
        in contract
    )

    closure_text = f"{changelog}\n{roadmap}\n{checklist}\n{contract}".lower()
    for phrase in (
        "one active same-owner v0.49",
        "v0.50_prerequisite_frozen",
        "queue_adapter_not_defined",
        "queue_claim_not_defined",
        "queue_lease_not_defined",
        "queue_ack_not_defined",
        "worker_activation_runtime_not_defined",
        "store_contact_not_defined",
        "runtime_contact_not_defined",
        "worker_start_admission_not_defined",
        "worker_start_not_defined",
        "agent_invocation_not_defined",
        "execution_start_boundary_not_defined",
        "agent/execution-worker zero-consumer",
        "compose.execution-smoke.override.yaml",
    ):
        assert phrase in closure_text


def test_v050_only_prerequisite_frozen_advanced_and_later_authority_blocked() -> None:
    contract = _read(
        "services/atlas-core/app/"
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite/"
        "contract.py"
    )

    assert 'eligibility: Literal["v0.50_prerequisite_frozen"]' in contract
    assert "SUCCESS_BLOCKERS as V049_SUCCESS_BLOCKERS" in contract
    assert "ControlledWorkerQueueClaimAdmissionV1" in contract
    assert "ControlledWorkerQueueClaimAdmissionStatusV1" in contract
    assert "recognized_v049_admission_count" in contract

    for blocker in (
        '"queue_adapter_not_defined"',
        '"queue_claim_not_defined"',
        '"queue_lease_not_defined"',
        '"queue_ack_not_defined"',
        '"worker_activation_runtime_not_defined"',
        '"store_contact_not_defined"',
        '"runtime_contact_not_defined"',
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
        "caller_supplied_queue_selector_allowed: Literal[False] = False",
        "caller_supplied_claim_token_allowed: Literal[False] = False",
        "caller_supplied_lease_token_allowed: Literal[False] = False",
        "caller_supplied_acknowledgement_handle_allowed: Literal[False] = False",
        "payload_schema_defined: Literal[False] = False",
        "payload_constructed: Literal[False] = False",
        "payload_serialized: Literal[False] = False",
        "queue_adapter_defined: Literal[False] = False",
        "queue_polling_allowed: Literal[False] = False",
        "queue_claim_allowed: Literal[False] = False",
        "queue_lease_allowed: Literal[False] = False",
        "queue_ack_allowed: Literal[False] = False",
        "queue_consume_allowed: Literal[False] = False",
        "queue_requeue_allowed: Literal[False] = False",
        "queue_mutation_allowed: Literal[False] = False",
        "worker_activation_runtime_allowed: Literal[False] = False",
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
        "queue_claimed: Literal[False] = False",
        "queue_leased: Literal[False] = False",
        "queue_acknowledged: Literal[False] = False",
        "worker_start_admitted: Literal[False] = False",
        "worker_started: Literal[False] = False",
        "agent_invoked: Literal[False] = False",
        "execution_started: Literal[False] = False",
    ):
        assert fixed_false_marker in contract


def test_v050_release_closure_does_not_add_effect_configuration() -> None:
    assert not ROOT.joinpath("compose.execution-smoke.override.yaml").exists()

    production_files = (
        (
            "services/atlas-core/app/"
            "controlled_worker_queue_claim_lease_acknowledgement_prerequisite/"
            "contract.py"
        ),
        (
            "services/atlas-core/app/"
            "controlled_worker_queue_claim_lease_acknowledgement_prerequisite/"
            "service.py"
        ),
        (
            "services/atlas-core/app/"
            "controlled_worker_queue_claim_lease_acknowledgement_prerequisite/"
            "store.py"
        ),
        (
            "services/atlas-core/app/routes/"
            "controlled_worker_queue_claim_lease_acknowledgement_prerequisite.py"
        ),
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
    allowed_imports = {
        "app.controlled_worker_queue_claim_admission.contract",
        "app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.contract",
        "app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.service",
        "app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.store",
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
            if name not in allowed_imports
            and any(marker in name for marker in forbidden_import_markers)
        ]
        assert definitions.isdisjoint(forbidden_def_names)
        assert calls.isdisjoint(forbidden_call_names)


def test_v050_default_off_api_ui_agent_and_execution_worker_isolation() -> None:
    service = _read(
        "services/atlas-core/app/"
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite/"
        "service.py"
    )
    store = _read(
        "services/atlas-core/app/"
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite/"
        "store.py"
    )
    route = _read(
        "services/atlas-core/app/routes/"
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite.py"
    )
    main = _read("services/atlas-core/app/main.py")
    mission_control_structural = _read(
        "services/mission-control/src/security/"
        "controlledWorkerQueueClaimAdmissionStructural.test.ts"
    )
    mission_control_component = _read(
        "services/mission-control/src/features/installation/"
        "ControlledWorkerQueueClaimAdmissions.tsx"
    )

    assert "enabled: bool = False" in service
    assert "no queue, worker, Agent, or execution API" in service
    assert "read_owned" in service
    assert "resolve_idempotency" in service
    assert "append_indeterminate" in service
    assert "UPDATE cwqcla_prerequisite" not in store
    assert "DELETE FROM cwqcla_prerequisite" not in store
    assert (
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite_service"
        not in main
    )
    assert (
        "create_controlled_worker_queue_claim_lease_acknowledgement_prerequisite_service"
        not in main
    )

    assert (
        '@router.post(\n    "/{candidate_record_id}/'
        'controlled-worker-queue-claim-lease-acknowledgement-prerequisites"'
        in route
    )
    assert (
        '@router.get(\n    "/{candidate_record_id}/'
        'controlled-worker-queue-claim-lease-acknowledgement-prerequisites"'
        in route
    )
    assert (
        '@router.get(\n    "/{candidate_record_id}/'
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisites/"
        '{prerequisite_id}"'
        in route
    )
    for forbidden_method in ("@router.put", "@router.patch", "@router.delete"):
        assert forbidden_method not in route
    assert "require_operator_mutation" in route
    assert "require_operator_permission" in route

    assert "v0.50 prerequisite isolation" in (
        mission_control_structural
    )
    assert "v0.50 progress: prerequisite frozen, documentation-only" in (
        mission_control_component
    )
    assert "v0.50 prerequisite details" in mission_control_component
    assert "one active same-owner v0.49 controlled worker queue claim admission" in (
        mission_control_component
    )
    assert "v0.50 prerequisite frozen equals queue claimed" in (
        mission_control_component
    )
    assert (
        "No queue claim, queue lease, queue acknowledgement, worker-start admission"
        in mission_control_component
    )
    assert (
        "claim token|lease token|acknowledgement token"
        in mission_control_structural
    )

    markers = (
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite",
        "ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisite",
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisites",
        "v0_50_prerequisite_frozen",
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
