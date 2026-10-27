import json
from pathlib import Path

from app.models.provider_management import ProviderManagementDescriptorV3


def _expected_fixture() -> list[dict[str, object]]:
    snapshots = []
    for readiness in (
        "ready",
        "not_activated",
        "authority_unavailable",
        "store_migration_required",
        "store_unavailable",
        "resource_missing",
        "identity_unavailable",
        "resource_type_unsupported",
        "denied",
        "configured",
        "replacement",
        "empty",
    ):
        ready = readiness in {"ready", "denied", "configured", "replacement"}
        missing = readiness == "resource_missing"
        unsupported = readiness == "resource_type_unsupported"
        authoritative = readiness not in {
            "resource_missing",
            "identity_unavailable",
            "resource_type_unsupported",
        }
        configured = readiness in {"configured", "resource_missing"}
        replacement = readiness == "replacement"
        resource_type = "lxc" if unsupported else "qemu"
        row = {
            "provider_id": "proxmox",
            "resource_id": "110",
            "resource_type": resource_type,
            "display_name": "Camera archive",
            "current_state": "running",
            "missing": missing,
            "resource_live": not missing,
            "identity_assurance": "authoritative"
            if authoritative
            else "unsupported"
            if unsupported
            else "unavailable",
            "management_fingerprint": f"provider-management-fingerprint-v1:{'a' * 64}"
            if authoritative
            else None,
            "intent_authority": "provider_intent",
            "intent_status": "missing"
            if missing
            else "configured"
            if configured
            else "unsupported"
            if unsupported
            else "needs_review",
            "intent_reason": "resource_missing"
            if missing
            else "matching_active_intent"
            if configured
            else "resource_type_unsupported"
            if unsupported
            else "identity_unavailable"
            if not authoritative
            else "incarnation_mismatch"
            if replacement
            else "no_active_intent",
            "expectation": "running" if configured else None,
            "record_version": 7 if configured else None,
            "legacy_review_available": replacement,
            "legacy_expectation": "stopped" if replacement else None,
            "replacement_detected": replacement,
            "provider_intent_mutation_supported": not unsupported,
            "mutation_readiness": "ready" if ready else readiness,
            "editable_in_principle": ready,
            "caller_can_mutate": ready and readiness != "denied",
        }
        value = {
            "provider_id": "proxmox",
            "provider_name": "Proxmox",
            "sections": [
                {"section": section, "availability": "available"}
                for section in (
                    "connection",
                    "discovery",
                    "resources",
                    "monitoring",
                    "diagnostics",
                    "actions",
                )
            ],
            "resource_types": []
            if readiness == "empty"
            else [
                {
                    "provider_id": "proxmox",
                    "resource_type": resource_type,
                    "resource_readable": True,
                    "authoritative_identity_supported": not unsupported,
                    "provider_intent_capability_supported": not unsupported,
                    "provider_intent_mutation_supported": not unsupported,
                    "supported_expectations": []
                    if unsupported
                    else ["running", "stopped", "ignored"],
                }
            ],
            "resources": [] if readiness == "empty" else [row],
            "provider_intent_activation": "not_activated"
            if readiness == "not_activated"
            else "activated",
            "provider_intent_authority_status": "unavailable"
            if readiness == "authority_unavailable"
            else "available",
            "caller_has_provider_intent_update": readiness != "denied",
        }
        snapshots.append(
            ProviderManagementDescriptorV3.model_validate_json(
                json.dumps(value)
            ).model_dump(mode="json")
        )
    return snapshots


def test_mission_control_operator_fixture_matches_public_model() -> None:
    fixture = (
        Path(__file__).resolve().parents[4]
        / "services/mission-control/src/test/operatorManagement.fixture.json"
    )
    assert json.loads(fixture.read_text()) == _expected_fixture()
