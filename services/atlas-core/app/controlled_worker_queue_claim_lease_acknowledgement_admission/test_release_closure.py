from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def _read(relative: str) -> str:
    return ROOT.joinpath(relative).read_text(encoding="utf-8")


def _python_tree(relative: str) -> ast.Module:
    return ast.parse(_read(relative))


def test_v051_release_closure_is_documented_as_admission_only() -> None:
    changelog = _read("CHANGELOG.md")
    roadmap = _read("ROADMAP.md")
    checklist = _read("docs/RELEASE_CHECKLIST.md")
    contract = _read(
        "docs/architecture/"
        "controlled-worker-queue-claim-lease-acknowledgement-admission-v1.md"
    )

    assert (
        "#### v0.51 P0-P5 - Controlled Worker Queue Claim/Lease/"
        "Acknowledgement Admission"
        in changelog
    )
    assert "P5 adds focused tests and release documentation only." in changelog
    assert (
        "## Completed v0.51 plan - Controlled Worker Queue Claim/Lease/"
        "Acknowledgement Admission"
        in roadmap
    )
    assert "P0-P5 are complete." in roadmap
    assert (
        "## Atlas v0.51 P0-P5 Controlled Worker Queue Claim/Lease/"
        "Acknowledgement Admission - complete"
        in checklist
    )
    assert (
        "Status: **Atlas v0.51 P0-P5 closed controlled worker queue claim/"
        "lease/acknowledgement admission contract**."
        in contract
    )

    closure_text = f"{changelog}\n{roadmap}\n{checklist}\n{contract}".lower()
    for phrase in (
        "one exact active same-owner v0.50",
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
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


def test_v051_only_admission_recorded_advanced_and_later_authority_blocked() -> None:
    contract = _read(
        "services/atlas-core/app/"
        "controlled_worker_queue_claim_lease_acknowledgement_admission/"
        "contract.py"
    )

    assert (
        'eligibility: Literal[\n        "controlled_worker_queue_claim_lease_'
        'acknowledgement_admission_recorded",\n        "blocked",\n    ]'
        in contract
    )
    assert "SUCCESS_BLOCKERS as V050_SUCCESS_BLOCKERS" in contract
    assert "ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1" in contract
    assert (
        "ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1"
        in contract
    )
    assert "recognized_v050_prerequisite_count" in contract

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
        "later_queue_claim_lease_acknowledgement_allowed: Literal[False] = False",
        "worker_start_admission_build_allowed: Literal[False] = False",
        "execution_start_admission_build_allowed: Literal[False] = False",
        "runtime_effect_allowed: Literal[False] = False",
    ):
        assert fixed_false_marker in contract


def test_v051_release_closure_does_not_add_effect_configuration() -> None:
    assert not ROOT.joinpath("compose.execution-smoke.override.yaml").exists()

    production_files = (
        (
            "services/atlas-core/app/"
            "controlled_worker_queue_claim_lease_acknowledgement_admission/"
            "contract.py"
        ),
        (
            "services/atlas-core/app/"
            "controlled_worker_queue_claim_lease_acknowledgement_admission/"
            "service.py"
        ),
        (
            "services/atlas-core/app/"
            "controlled_worker_queue_claim_lease_acknowledgement_admission/"
            "store.py"
        ),
        (
            "services/atlas-core/app/routes/"
            "controlled_worker_queue_claim_lease_acknowledgement_admission.py"
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
        "app.controlled_worker_queue_claim_admission.test_contract",
        "app.controlled_worker_queue_claim_lease_acknowledgement_admission.contract",
        "app.controlled_worker_queue_claim_lease_acknowledgement_admission.service",
        "app.controlled_worker_queue_claim_lease_acknowledgement_admission.store",
        "app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.contract",
        "app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.test_contract",
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


def test_v051_default_off_api_ui_agent_and_execution_worker_isolation() -> None:
    service = _read(
        "services/atlas-core/app/"
        "controlled_worker_queue_claim_lease_acknowledgement_admission/service.py"
    )
    store = _read(
        "services/atlas-core/app/"
        "controlled_worker_queue_claim_lease_acknowledgement_admission/store.py"
    )
    route = _read(
        "services/atlas-core/app/routes/"
        "controlled_worker_queue_claim_lease_acknowledgement_admission.py"
    )
    main = _read("services/atlas-core/app/main.py")
    mission_control_structural = _read(
        "services/mission-control/src/security/"
        "controlledWorkerQueueClaimLeaseAcknowledgementAdmissionStructural.test.ts"
    )
    mission_control_component = _read(
        "services/mission-control/src/features/installation/"
        "ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions.tsx"
    )

    assert "enabled: bool = False" in service
    assert "no queue, worker, Agent, or execution API" in service
    assert "read_owned" in service
    assert "resolve_idempotency" in service
    assert "append_indeterminate" in service
    assert "UPDATE cwqcla_admission" not in store
    assert "DELETE FROM cwqcla_admission" not in store
    assert "controlled_worker_queue_claim_lease_acknowledgement_admission_service" not in main
    assert (
        "create_controlled_worker_queue_claim_lease_acknowledgement_admission_service"
        not in main
    )

    assert (
        '@router.post(\n    "/{candidate_record_id}/'
        'controlled-worker-queue-claim-lease-acknowledgement-admissions"'
        in route
    )
    assert (
        '@router.get(\n    "/{candidate_record_id}/'
        'controlled-worker-queue-claim-lease-acknowledgement-admissions"'
        in route
    )
    assert (
        '@router.get(\n    "/{candidate_record_id}/'
        "controlled-worker-queue-claim-lease-acknowledgement-admissions/"
        '{admission_id}"'
        in route
    )
    for forbidden_method in ("@router.put", "@router.patch", "@router.delete"):
        assert forbidden_method not in route
    assert "require_operator_mutation" in route
    assert "require_operator_permission" in route

    assert "v0.51 controlled queue claim lease acknowledgement admission" in (
        mission_control_structural
    )
    assert "uses only guarded Core read APIs and no polling transport" in (
        mission_control_structural
    )
    assert r"atlas\.(post|put|patch|delete)" in mission_control_structural
    assert "expect(controls).toHaveLength(0)" in mission_control_structural
    assert "expect(consumers).toEqual" in mission_control_structural
    assert "v0.51 state: admission evidence recorded for the completed v0.50" in (
        mission_control_component
    )
    assert "Advanced v0.51 evidence" in mission_control_component
    assert "Ordered v0.51 blockers" in mission_control_component
    assert "Controlled queue claim lease acknowledgement fixed-false authority" in (
        mission_control_component
    )
    assert (
        "raw queue selectors, claim tokens, lease tokens, acknowledgement handles"
        in mission_control_component
    )

    markers = (
        "controlled_worker_queue_claim_lease_acknowledgement_admission",
        "ControlledWorkerQueueClaimLeaseAcknowledgementAdmission",
        "controlled-worker-queue-claim-lease-acknowledgement-admissions",
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
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
