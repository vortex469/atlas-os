import { executionRequestFixture } from "./installationExecutionRequest";

export const dispatchHandoffFixture = {
    schema: "installation-dispatch-envelope-v1",
    dispatch_envelope_id: "99999999-9999-4999-8999-999999999999",
    prepared_at: "2026-08-28T12:00:00Z",
    valid_until: "2026-08-28T12:01:00Z",
    operation: "install-container",
    mode: "handoff-only",
    recipient: { service: "atlas-agent", intake_contract: "agent-installation-dispatch-intake-v1" },
    linkage: { ...executionRequestFixture.linkage, execution_request_id: executionRequestFixture.execution_request_id, execution_request_fingerprint: executionRequestFixture.execution_request_fingerprint },
    statement: "core_prepared_non_executing_agent_handoff",
    delivery_authorized: false,
    agent_admission_authorized: false,
    execution_authorized: false,
    mutation_authorized: false,
    replay_allowed: false,
    dispatch_envelope_fingerprint: { algorithm: "sha256", canonicalization: "atlas-jcs-nfc-v1", value: "9".repeat(64) },
    lifecycle_state: "prepared",
    evidence_provenance: "core_prepared_not_delivered",
} as const;
