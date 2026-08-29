import { deliveryActivationPreflightFixture } from "./deliveryActivationPreflight";
import type { DeliveryEnablementOperationV1 } from "../types/deliveryEnablement";
import { DELIVERY_ENABLEMENT_CONFIRMATION } from "../types/deliveryEnablement";

const preflight = deliveryActivationPreflightFixture.result;
const fp = (character: string) => ({ algorithm: "sha256" as const, canonicalization: "atlas-jcs-nfc-v1" as const, value: character.repeat(64) });
const enablementId = "00000000-0000-4000-8000-000000000a01";
const linkage = {
    ...preflight.linkage,
    delivery_preparation_id: preflight.delivery_preparation_id,
    preparation_fingerprint: preflight.preparation_fingerprint,
    preflight_id: preflight.preflight_id,
    preflight_fingerprint: preflight.preflight_fingerprint,
};

export const deliveryEnablementFixture: DeliveryEnablementOperationV1 = {
    disposition: "created",
    record: {
        schema: "operator-controlled-delivery-enablement-record-v1", enablement_id: enablementId,
        enabled_at: "2026-08-29T12:00:01Z", expires_at: "2026-08-29T12:00:30Z",
        preflight_id: preflight.preflight_id, preflight_fingerprint: preflight.preflight_fingerprint,
        delivery_preparation_id: preflight.delivery_preparation_id, preparation_fingerprint: preflight.preparation_fingerprint,
        linkage, status_at_creation: "operator_enabled_for_later_delivery_consideration",
        confirmation: DELIVERY_ENABLEMENT_CONFIRMATION, statement: "operator_enablement_evidence_only_no_delivery_activation",
        source: "core_operator_controlled_delivery_enablement_v1", default_enabled: false, operator_enabled: true,
        agent_contacted: false, credentials_loaded: false, production_transport_registered: false,
        delivery_activated: false, delivery_sent: false, delivery_authorized: false,
        execution_admission_granted: false, execution_authorized: false, dispatch_allowed: false,
        worker_allowed: false, workflow_allowed: false, installation_allowed: false,
        deployment_allowed: false, mutation_allowed: false, replay_allowed: false,
        enablement_fingerprint: fp("e"),
    },
    status: {
        schema: "operator-controlled-delivery-enablement-status-v1", enablement_id: enablementId,
        enablement_fingerprint: fp("e"), observed_at: "2026-08-29T12:00:02Z", lifecycle: "enabled",
        operator_enabled: true, delivery_activated: false, delivery_sent: false,
        delivery_authorized: false, execution_authorized: false, replay_allowed: false,
    },
    audit_evidence: {
        schema: "operator-controlled-delivery-enablement-audit-evidence-v1", enablement_id: enablementId,
        enablement_fingerprint: fp("e"), preflight_id: preflight.preflight_id,
        preflight_fingerprint: preflight.preflight_fingerprint,
        delivery_preparation_id: preflight.delivery_preparation_id,
        preparation_fingerprint: preflight.preparation_fingerprint,
        enabled_at: "2026-08-29T12:00:01Z", expires_at: "2026-08-29T12:00:30Z",
        lifecycle: "enabled", status: "operator_enabled_for_later_delivery_consideration",
        confirmation: DELIVERY_ENABLEMENT_CONFIRMATION,
        provenance: "core_operator_controlled_delivery_enablement_v1",
        delivery_activated: false, delivery_sent: false, delivery_authorized: false,
        execution_authorized: false, mutation_allowed: false, replay_allowed: false,
        evidence_fingerprint: fp("f"),
    },
    error: null, default_enabled: false, agent_contacted: false, credentials_loaded: false,
    delivery_activated: false, delivery_sent: false, delivery_authorized: false,
    execution_attempted: false, mutation_attempted: false, replay_allowed: false,
};
