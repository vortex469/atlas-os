"""P5 authority-isolation and release-closure locks for v0.65."""

from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.control_plane import contract as c
from app.control_plane.test_contract import _input

ROOT = Path(__file__).resolve().parents[4]

SUCCESSOR_MARKERS = (
    "control_plane_decision_recorded", "control-plane-decision-recorded",
    "controlPlaneDecisionRecorded", "ControlPlaneDecisionRecorded",
    "CONTROL_PLANE_DECISION_RECORDED", "control_plane_activation_authorized",
    "control-plane-activation-authorized", "controlPlaneActivationAuthorized",
    "ControlPlaneActivationAuthorized", "CONTROL_PLANE_ACTIVATION_AUTHORIZED",
    "control_plane_runtime_contact", "control-plane-runtime-contact",
    "controlPlaneRuntimeContact", "ControlPlaneRuntimeContact",
    "CONTROL_PLANE_RUNTIME_CONTACT", "control_plane_queue_consumption",
    "control-plane-queue-consumption", "controlPlaneQueueConsumption",
    "ControlPlaneQueueConsumption", "CONTROL_PLANE_QUEUE_CONSUMPTION",
    "control_plane_execution_authorized", "control-plane-execution-authorized",
    "controlPlaneExecutionAuthorized", "ControlPlaneExecutionAuthorized",
    "CONTROL_PLANE_EXECUTION_AUTHORIZED", "control_plane_installation_authorized",
    "control-plane-installation-authorized", "controlPlaneInstallationAuthorized",
    "ControlPlaneInstallationAuthorized", "CONTROL_PLANE_INSTALLATION_AUTHORIZED",
)

EFFECT_MARKERS = (
    *SUCCESSOR_MARKERS,
    "control_plane_evidence_client", "control-plane-evidence-client",
    "ControlPlaneEvidenceClient", "CONTROL_PLANE_EVIDENCE_CLIENT",
    "control_plane_evidence_consumer", "control-plane-evidence-consumer",
    "ControlPlaneEvidenceConsumer", "CONTROL_PLANE_EVIDENCE_CONSUMER",
)


def _production_files(area: str):
    directory = ROOT / area
    assert directory.is_dir()
    paths = list(directory.rglob("*"))
    if area == "deploy":
        paths.extend((*ROOT.glob("compose*.yaml"), ROOT / ".env.example"))
    for path in paths:
        if not path.is_file() or path.suffix not in {
            "", ".py", ".ts", ".tsx", ".json", ".yaml", ".yml", ".sh", ".example",
        }:
            continue
        relative = path.relative_to(ROOT)
        if path.name.startswith("test_") or ".test." in path.name or "test" in relative.parts:
            continue
        yield path, relative


def test_shared_v065_envelopes_reject_successor_authority() -> None:
    item = _input()
    evaluation = c.evaluate_control_plane(
        item,
        expected_lineage_fingerprint=item.lineage.lineage_fingerprint,
        expected_policy_fingerprint=c.policy_fingerprint(item.policy),
        evaluated_at="2026-09-23T12:00:00Z",
    )
    for model, value in (
        (c.ControlPlaneInputV1, item.model_dump(mode="python")),
        (c.ControlPlaneEvaluationV1, evaluation.model_dump(mode="python")),
    ):
        for marker in SUCCESSOR_MARKERS:
            forged = deepcopy(value)
            forged[marker] = False
            with pytest.raises(ValidationError):
                model.model_validate(forged)


def test_reference_only_ceiling_remains_fixed() -> None:
    item = _input()
    evaluation = c.evaluate_control_plane(
        item,
        expected_lineage_fingerprint=item.lineage.lineage_fingerprint,
        expected_policy_fingerprint=c.policy_fingerprint(item.policy),
        evaluated_at="2026-09-23T12:00:00Z",
    )
    assert evaluation.evidence_only is True
    assert evaluation.reference_only is True
    assert evaluation.authority_granted is False
    assert evaluation.effect_allowed is False
    assert evaluation.runtime_creation_allowed is False
    assert evaluation.credential_present is False
    assert evaluation.payload_bytes == 0


def test_no_effect_plane_v065_consumers_in_production_surfaces() -> None:
    for area in (
        "services/atlas-agent/app",
        "services/atlas-execution-worker/atlas_execution_worker",
        "scripts",
        "deploy",
    ):
        for path, relative in _production_files(area):
            source = path.read_text()
            for marker in EFFECT_MARKERS:
                assert marker not in source, (relative, marker)


def test_core_has_no_v065_runtime_or_effect_adapter() -> None:
    allowed_files = {
        Path("services/atlas-core/app/api/v1/router.py"),
        Path("services/atlas-core/app/main.py"),
        Path("services/atlas-core/app/config/settings.py"),
        Path("services/atlas-core/app/operator_auth/models.py"),
        Path("services/atlas-core/app/routes/control_plane_evidence.py"),
    }
    allowed_directory = Path("services/atlas-core/app/control_plane")
    for path, relative in _production_files("services/atlas-core/app"):
        if relative in allowed_files or relative.is_relative_to(allowed_directory):
            continue
        source = path.read_text()
        assert "control_plane" not in source and "ControlPlane" not in source, relative
