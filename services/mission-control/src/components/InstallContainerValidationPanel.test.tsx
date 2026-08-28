import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { InstallContainerCapability, InstallContainerValidation } from "../types/atlasAgent";
import { InstallContainerValidationPanel } from "./InstallContainerValidationPanel";

const hex = "a".repeat(64);
const fingerprint = { algorithm: "sha256" as const, canonicalization: "atlas-jcs-nfc-v1" as const, value: hex };
const capability: InstallContainerCapability = {
    contract_schema: "agent-install-container-validation-v1", operation: "install-container", mode: "validate-only",
    capability_status: "unsupported", default_enabled: false, execution_supported: false, dispatch_allowed: false,
    mutation_allowed: false, replay_allowed: false, runtime: "rootless-podman; fixed limits; no runtime invocation",
    filesystem: "read-only root; bounded /tmp tmpfs; no host mounts", network: "none; no ingress, egress, DNS, ports, or image pull",
    home_assistant_status: "blocked", validation_result_available: false,
};

function validation(status: "valid_but_unsupported" | "rejected" = "valid_but_unsupported"): InstallContainerValidation {
    const reasons = status === "rejected" ? ["network_boundary_violated"] : [];
    const authority = { execution_supported: false as const, dispatch_allowed: false as const, mutation_allowed: false as const, replay_allowed: false as const };
    return {
        schema: "agent-install-container-validation-v1", request_id: "00000000-0000-4000-8000-000000000001", request_fingerprint: fingerprint,
        validated_at: "2026-08-28T12:00:00Z", status, reason_codes: reasons, ...authority, validation_fingerprint: fingerprint,
        evidence: {
            evidence_schema: "agent-install-container-audit-evidence-v1", request_id: "00000000-0000-4000-8000-000000000001", request_fingerprint: fingerprint,
            approval: { candidate_record_id: "00000000-0000-4000-8000-000000000002", candidate_envelope_fingerprint: fingerprint, admission_fingerprint: fingerprint, candidate_record_fingerprint: fingerprint, approval_intent_id: "00000000-0000-4000-8000-000000000003", approval_intent_fingerprint: fingerprint },
            subject: { provider: "proxmox", resource_type: "qemu", placement_kind: "existing-guest", resource_id: "vm-101", destination_fingerprint: hex },
            artifact_kind: "single-oci-container-v1", source_plan_fingerprint: fingerprint, source_repository_path: "compose/example.yaml", source_service: "example",
            source_content_digest: `sha256:${hex}`, image_digest: `sha256:${hex}`, runtime_limit_policy_fingerprint: fingerprint,
            validated_at: "2026-08-28T12:00:00Z", status, reason_codes: reasons, ...authority, evidence_fingerprint: fingerprint,
        },
    };
}

describe("InstallContainerValidationPanel", () => {
    it("shows default-disabled, non-authorizing empty diagnostics and the blocked Home Assistant golden", () => {
        render(<InstallContainerValidationPanel capability={capability} validation={null} error={null} />);
        expect(screen.getByText(/Unsupported · default-disabled/)).toBeInTheDocument();
        expect(screen.getByText(/Validation is not installation, execution approval, dispatch, deployment, rollback/)).toBeInTheDocument();
        expect(screen.getByText(/Home Assistant remains blocked/)).toBeInTheDocument();
        expect(screen.getByText(/No validation result is locally available/)).toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
        expect(screen.queryByRole("link")).not.toBeInTheDocument();
    });

    it("renders validation, proof, artifact, bounds, and audit evidence without controls", () => {
        render(<InstallContainerValidationPanel capability={capability} validation={validation()} error={null} />);
        expect(screen.getByText("Validation status: valid_but_unsupported")).toBeInTheDocument();
        expect(screen.getByText(/compose\/example.yaml · example/)).toBeInTheDocument();
        expect(screen.getByText(/Execution supported: no · Dispatch allowed: no/)).toBeInTheDocument();
        expect(screen.getByText("Audit evidence fingerprint")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /install|run|execute|deploy|dispatch|rollback|send|start/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("link")).not.toBeInTheDocument();
    });

    it("renders rejected reasons and only the closed redacted error vocabulary", () => {
        const { rerender } = render(<InstallContainerValidationPanel capability={capability} validation={validation("rejected")} error={null} />);
        expect(screen.getByText("Reasons: network_boundary_violated")).toBeInTheDocument();
        rerender(<InstallContainerValidationPanel capability={capability} validation={null} error={{ schema: "agent-install-container-error-v1", reason_code: "validation_contract_failure", request_id: null, request_fingerprint: null, correlation_id: "corr-1", redacted: true }} />);
        expect(screen.getByRole("alert")).toHaveTextContent("validation_contract_failure");
        expect(screen.getByRole("alert")).toHaveTextContent("corr-1");
        expect(screen.getByRole("alert")).toHaveTextContent("No request content, credentials, provider payload, paths, or exception details are shown.");
    });
});
