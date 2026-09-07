from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def _read(relative: str) -> str:
    return ROOT.joinpath(relative).read_text(encoding="utf-8")


def test_v052_p1_release_reference_documents_validation_only_boundary() -> None:
    changelog = _read("CHANGELOG.md")
    checklist = _read("docs/RELEASE_CHECKLIST.md")
    architecture = _read(
        "docs/architecture/"
        "controlled-worker-queue-claim-lease-acknowledgement-boundary-v1.md"
    )
    combined = f"{changelog}\n{checklist}\n{architecture}".lower()

    assert "v0.52 p1" in changelog.lower()
    assert "closed immutable core contract models" in combined
    assert "pure fail-closed evaluator" in combined
    assert "one exact active same-owner v0.51 admission record" in combined
    assert "controlled_worker_queue_claim_lease_acknowledgement_recorded" in combined
    for blocker in (
        "worker_activation_runtime_not_defined",
        "store_contact_not_defined",
        "runtime_contact_not_defined",
        "worker_start_admission_not_defined",
        "worker_start_not_defined",
        "agent_invocation_not_defined",
        "execution_start_boundary_not_defined",
    ):
        assert blocker in combined


def test_v052_contract_advances_only_queue_receipt_and_blocks_later_authority() -> None:
    contract = _read(
        "services/atlas-core/app/"
        "controlled_worker_queue_claim_lease_acknowledgement/contract.py"
    )

    assert "SUCCESS_BLOCKERS as V051_SUCCESS_BLOCKERS" in contract
    assert "ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1" in contract
    assert "ControlledWorkerQueueAdapterReceiptFactsV1" in contract
    assert "recognized_v051_admission_count" in contract
    assert "recognized_adapter_receipt_count" in contract
    assert '"controlled_worker_queue_claim_lease_acknowledgement_recorded"' in contract
    assert '"queue_adapter_not_defined"' not in contract
    assert '"queue_claim_not_defined"' not in contract
    assert '"queue_lease_not_defined"' not in contract
    assert '"queue_ack_not_defined"' not in contract

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
        "autonomous_queue_polling_allowed: Literal[False] = False",
        "work_discovery_allowed: Literal[False] = False",
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
        "worker_start_admitted: Literal[False] = False",
        "worker_started: Literal[False] = False",
        "agent_invoked: Literal[False] = False",
        "execution_started: Literal[False] = False",
        "worker_start_admission_build_allowed: Literal[False] = False",
        "execution_start_admission_build_allowed: Literal[False] = False",
        "runtime_effect_allowed: Literal[False] = False",
    ):
        assert fixed_false_marker in contract


def test_v052_p2_adds_only_local_service_store_without_effect_consumers() -> None:
    assert not ROOT.joinpath("compose.execution-smoke.override.yaml").exists()
    assert ROOT.joinpath(
        "services/atlas-core/app/routes/"
        "controlled_worker_queue_claim_lease_acknowledgement.py"
    ).exists()
    assert ROOT.joinpath(
        "services/atlas-core/app/controlled_worker_queue_claim_lease_acknowledgement/"
        "service.py"
    ).exists()
    assert ROOT.joinpath(
        "services/atlas-core/app/controlled_worker_queue_claim_lease_acknowledgement/"
        "store.py"
    ).exists()

    forbidden_import_markers = {
        "agent",
        "atlas_execution_worker",
        "deployment",
        "dispatch",
        "docker",
        "fastapi",
        "httpx",
        "provider",
        "repository",
        "requests",
        "rollback",
        "scheduler",
        "socket",
        "sqlite",
        "subprocess",
        "transport",
        "workflow",
        "worker_runtime",
    }
    for relative in (
        (
            "services/atlas-core/app/"
            "controlled_worker_queue_claim_lease_acknowledgement/contract.py"
        ),
        (
            "services/atlas-core/app/"
            "controlled_worker_queue_claim_lease_acknowledgement/service.py"
        ),
        (
            "services/atlas-core/app/"
            "controlled_worker_queue_claim_lease_acknowledgement/store.py"
        ),
    ):
        tree = ast.parse(_read(relative))
        imports = {
            alias.name if isinstance(node, ast.Import) else node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.Import | ast.ImportFrom)
            for alias in node.names
        }
        forbidden = [
            name
            for name in imports
            if any(marker in name for marker in forbidden_import_markers)
        ]
        if relative.endswith("/store.py"):
            forbidden = [name for name in forbidden if name != "sqlite3"]
        assert not forbidden


def test_v052_final_contract_and_release_closure_are_evidence_only() -> None:
    documents = {
        relative: _read(relative)
        for relative in (
            "ROADMAP.md",
            "CHANGELOG.md",
            "docs/RELEASE_CHECKLIST.md",
            (
                "docs/architecture/"
                "controlled-worker-queue-claim-lease-acknowledgement-boundary-v1.md"
            ),
        )
    }
    for relative, source in documents.items():
        assert "P0-P5" in source, relative
        assert "already-observed" in source, relative
    contract = documents[
        "docs/architecture/"
        "controlled-worker-queue-claim-lease-acknowledgement-boundary-v1.md"
    ]
    assert "It has no queue adapter client" in contract
    assert "16 reservations per owner, 256 globally, 192 KiB" in contract
    assert "one terminal audit per reservation" in contract
    assert "Corruption closes reads and writes" in contract
    assert "Production startup never constructs the service or readers" in contract


def test_v052_exact_core_and_ui_consumer_allowlists() -> None:
    # Exact identifiers avoid matching the historical v0.50/v0.51 packages.
    import re

    marker = re.compile(
        r"\bcontrolled_worker_queue_claim_lease_acknowledgement\b|"
        r"\bcontrolled_worker_queue_claim_lease_acknowledgement_service\b|"
        r"\bcontrolled_worker_queue_claim_lease_acknowledgement_recorded\b|"
        r"\bControlledWorkerQueueClaimLeaseAcknowledgement(?:Service|V1)\b|"
        r"controlled-worker-queue-claim-lease-acknowledgements"
    )
    core = ROOT / "services/atlas-core/app"
    consumers = {
        path.relative_to(core).as_posix()
        for path in core.rglob("*.py")
        if not path.name.startswith("test_")
        and path.parent.name != "controlled_worker_queue_claim_lease_acknowledgement"
        and marker.search(path.read_text(encoding="utf-8"))
    }
    assert consumers == {
        "api/v1/router.py",
        "operator_auth/models.py",
        "routes/controlled_worker_queue_claim_lease_acknowledgement.py",
    }
    ui = ROOT / "services/mission-control/src"
    consumers = {
        path.relative_to(ui).as_posix()
        for path in ui.rglob("*")
        if path.suffix in {".ts", ".tsx"}
        and ".test." not in path.name
        and "test" not in path.relative_to(ui).parts
        and re.search(
            r"controlledWorkerQueueReceipt|ControlledWorkerQueueReceipt|"
            r"controlled-worker-queue-claim-lease-acknowledgements",
            path.read_text(encoding="utf-8"),
        )
    }
    assert consumers == {
        "api/controlledWorkerQueueReceipt.ts",
        "features/installation/ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions.tsx",
        "features/installation/ControlledWorkerQueueReceipt.tsx",
        "types/controlledWorkerQueueReceipt.ts",
    }
    for relative in (
        "services/atlas-agent/app",
        "services/atlas-execution-worker/atlas_execution_worker",
    ):
        root = ROOT / relative
        assert root.is_dir(), relative
        assert not [
            path.relative_to(ROOT).as_posix()
            for path in root.rglob("*.py")
            if marker.search(path.read_text(encoding="utf-8"))
        ]


def test_v052_durable_receipt_keeps_exact_prerequisite_and_false_authority(
    tmp_path: Path,
) -> None:
    from typing import Literal, get_args, get_origin

    import pytest
    from pydantic import ValidationError

    from .contract import SUCCESS_BLOCKERS
    from .test_service_store import _record, _service

    (
        receipt_service,
        receipt_store,
        reader,
        adapter_reader,
        admission,
        status,
        facts,
        create,
    ) = _service(tmp_path)
    result = _record(receipt_service, admission, create)
    assert result.ok
    record = result.record
    assert record.admission_id == admission.admission_id == status.admission_id
    assert (
        record.controlled_worker_queue_claim_lease_acknowledgement_admission
        == admission
    )
    assert (
        record.controlled_worker_queue_claim_lease_acknowledgement_admission_status
        == status
    )
    assert (
        record.v051_admission_record_fingerprint
        == admission.admission_record_fingerprint
    )
    assert record.v051_admission_status_fingerprint == status.status_fingerprint
    assert (
        record.v050_prerequisite_record_fingerprint
        == admission.prerequisite_record_fingerprint
    )
    assert (
        record.v050_prerequisite_status_fingerprint
        == admission.prerequisite_status_fingerprint
    )
    for name in (
        "v049_admission_record_fingerprint",
        "v049_admission_status_fingerprint",
        "binding_subject_fingerprint",
        "worker_subject_fingerprint",
        "queue_item_reference_fingerprint",
        "inherited_limits_fingerprint",
    ):
        assert getattr(record, name) == getattr(admission, name)
    assert record.adapter_receipt == facts
    assert record.blockers == SUCCESS_BLOCKERS
    false_fields = {
        name
        for name, field in type(record).model_fields.items()
        if get_origin(field.annotation) is Literal
        and get_args(field.annotation)[0] is False
    }
    assert {
        "worker_start_allowed",
        "execution_start_allowed",
        "installation_allowed",
        "deployment_allowed",
        "rollback_allowed",
        "release_publication_allowed",
    } <= false_fields
    for name in false_fields:
        assert getattr(record, name) is False
        raw = record.model_dump(mode="python")
        raw[name] = True
        with pytest.raises(ValidationError):
            type(record).model_validate(raw)
    calls = (reader.calls, adapter_reader.calls)
    assert _record(receipt_service, admission, create).record == record
    assert (reader.calls, adapter_reader.calls) == calls
    persisted = receipt_store.list_owned(
        operator_id=admission.operator_id,
        candidate_record_id=admission.candidate_record_id,
    )
    assert persisted == (record,)
