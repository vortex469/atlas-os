import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockGet } = vi.hoisted(() => ({
    mockGet: vi.fn(),
}));

vi.mock("axios", () => ({
    default: {
        create: () => ({ get: mockGet }),
    },
    isAxiosError: (error: unknown): error is { response?: { status?: number } } => {
        return !!error && typeof error === "object" && "isAxiosError" in (error as { isAxiosError?: boolean });
    },
}));

import { operationalDiagnostic } from "../test/operationalLifecycle";

import {
    getAgentInfo,
    getAtlasAgentErrorMessage,
    getCandidateWorkflowShell,
    getReviewReport,
    getSprintStatus,
    getVerificationReport,
    getWorkflowOperationalLifecycle,
    getWorkflowRecoveryDiagnostic,
    getWorkflowSupportBundle,
} from "./atlas-agent";

function axiosError(status: number): unknown {
    const error = new Error(`Request failed with status code ${status}`) as unknown as {
        isAxiosError: boolean;
        response: { status: number };
    };

    error.isAxiosError = true;
    error.response = { status };

    return error;
}

describe("Atlas Agent optional summary endpoints", () => {
    beforeEach(() => {
        mockGet.mockReset();
    });

    it("treats 404 sprint/verification/review as not published", async () => {
        mockGet
            .mockRejectedValueOnce(axiosError(404))
            .mockRejectedValueOnce(axiosError(404))
            .mockRejectedValueOnce(axiosError(404));

        await expect(getSprintStatus()).resolves.toBeNull();
        await expect(getVerificationReport()).resolves.toBeNull();
        await expect(getReviewReport()).resolves.toBeNull();
    });

    it("reads only the closed default-disabled install-container diagnostic", async () => {
        mockGet.mockResolvedValueOnce({ data: {
            app_name: "Atlas Agent", version: "0.22.0", environment: "test", repository_root: "/opt/atlas",
            supported_workflow_phases: [], supported_verification_statuses: [],
            install_container: {
                contract_schema: "agent-install-container-validation-v1", operation: "install-container", mode: "validate-only",
                capability_status: "unsupported", default_enabled: false, execution_supported: false, dispatch_allowed: false,
                mutation_allowed: false, replay_allowed: false, runtime: "rootless-podman", filesystem: "read-only", network: "none",
                home_assistant_status: "blocked", validation_result_available: false,
            },
        } });
        await expect(getAgentInfo()).resolves.toMatchObject({ install_container: { capability_status: "unsupported", default_enabled: false } });
        expect(mockGet).toHaveBeenCalledWith("/api/v1/agent/info");
    });

    it("rejects diagnostics that claim install-container authority", async () => {
        mockGet.mockResolvedValueOnce({ data: { install_container: { execution_supported: true } } });
        await expect(getAgentInfo()).rejects.toThrow("Malformed Atlas Agent information payload.");
    });

    it("treats 5xx responses as failures", async () => {
        mockGet
            .mockRejectedValueOnce(axiosError(503))
            .mockRejectedValueOnce(axiosError(503))
            .mockRejectedValueOnce(axiosError(503));

        await expect(getSprintStatus()).rejects.toBeInstanceOf(Error);
        await expect(getVerificationReport()).rejects.toBeInstanceOf(Error);
        await expect(getReviewReport()).rejects.toBeInstanceOf(Error);
    });

    it("throws on malformed sprint success responses", async () => {
        mockGet.mockResolvedValueOnce({
            data: {
                checkpoint_id: 123,
                title: "No phase",
                goal: "Missing phase",
            },
        });

        await expect(getSprintStatus()).rejects.toThrow(
            "Malformed sprint status payload.",
        );
    });

    it("throws on malformed verification success responses", async () => {
        mockGet.mockResolvedValueOnce({
            data: {
                repository_root: "/workspace",
                status: "passed",
                duration_seconds: 0.5,
                results: [1],
            },
        });

        await expect(getVerificationReport()).rejects.toThrow(
            "Malformed verification report payload.",
        );
    });

    it("throws on malformed review success responses", async () => {
        mockGet.mockResolvedValueOnce({
            data: {
                request_id: "review-1",
                checkpoint_id: "A7",
                status: "approved",
                recommendations: ["update docs"],
                findings: [{ request_id: "bad" }],
            },
        });

        await expect(getReviewReport()).rejects.toThrow(
            "Malformed review report payload.",
        );
    });

    it("reads a workflow-scoped operational lifecycle contract", async () => {
        const lifecycle = { applicable: true, workflow_id: "workflow/one" };
        mockGet.mockResolvedValueOnce({ data: lifecycle });

        await expect(getWorkflowOperationalLifecycle("workflow/one")).resolves.toBe(lifecycle);
        expect(mockGet).toHaveBeenCalledWith(
            "/api/v1/agent/workflows/workflow%2Fone/operational-lifecycle",
        );
    });

    it("reads a workflow-scoped recovery diagnostic contract", async () => {
        const diagnostic = operationalDiagnostic();
        diagnostic.correlation.workflow_id = "workflow/one";
        mockGet.mockResolvedValueOnce({ data: diagnostic });

        await expect(getWorkflowRecoveryDiagnostic("workflow/one")).resolves.toBe(diagnostic);
        expect(mockGet).toHaveBeenCalledWith(
            "/api/v1/agent/workflows/workflow%2Fone/recovery-diagnostic",
        );
    });

    it.each([
        ["missing report", null],
        ["partial healthy report", { applicable: true, diagnostic_status: "healthy" }],
        ["foreign request", { correlation: { ...operationalDiagnostic().correlation, workflow_id: "foreign" } }],
        ["unknown status", { diagnostic_status: "perfect" }],
        ["unknown consistency", { consistency: "perfect" }],
        ["unknown reason", { controlled_reason: "secret exception" }],
        ["unknown next action", { safe_next_action: "retry_operation" }],
        ["missing verification", { verification_evidence: null }],
        ["invalid dispatch", { dispatch_evidence: { ...operationalDiagnostic().dispatch_evidence, barrier_crossed: "true" } }],
        ["missing correlation fact", { correlation: { workflow_id: "workflow-1" } }],
        ["invalid verification", { verification_evidence: { ...operationalDiagnostic().verification_evidence, terminal_evidence: "true" } }],
    ])("rejects %s without exposing response contents", async (_name, patch) => {
        const data = patch === null || _name === "partial healthy report" ? patch : { ...operationalDiagnostic(), ...patch };
        mockGet.mockResolvedValueOnce({ data });
        await expect(getWorkflowRecoveryDiagnostic("workflow-1")).rejects.toThrow(
            "Maintenance status report is incomplete or does not match this request.",
        );
        expect(mockGet).toHaveBeenCalledTimes(1);
    });

    it.each(["healthy", "pending", "attention_required", "recovery_in_progress", "outcome_uncertain", "unavailable"] as const)("accepts a complete %s report", async (diagnostic_status) => {
        const data = operationalDiagnostic({ diagnostic_status });
        mockGet.mockResolvedValueOnce({ data });
        await expect(getWorkflowRecoveryDiagnostic("workflow-1")).resolves.toEqual(data);
    });

    it.each([
        "applicable", "diagnostic_status", "consistency", "controlled_reason", "safe_next_action",
        "correlation.request_id", "correlation.request_digest_match", "correlation.agent_record_present", "correlation.core_record_present",
        "dispatch_evidence.barrier_crossed", "dispatch_evidence.provider_operation_captured", "dispatch_evidence.dispatch_result_known", "dispatch_evidence.transition_sequence_valid",
        "verification_evidence.status", "verification_evidence.target_fingerprint_state", "verification_evidence.observed_state", "verification_evidence.observed_health", "verification_evidence.terminal_evidence",
    ])("rejects a report missing required field %s", async (path) => {
        const data = operationalDiagnostic();
        const parts = path.split(".");
        const parent = parts.length === 1 ? data : data[parts[0] as keyof typeof data];
        delete (parent as Record<string, unknown>)[parts.at(-1)!];
        mockGet.mockResolvedValueOnce({ data });
        await expect(getWorkflowRecoveryDiagnostic("workflow-1")).rejects.toThrow("Maintenance status report is incomplete");
    });

    it("accepts nullable evidence and non-applicable reports without inventing facts", async () => {
        const data = operationalDiagnostic({ applicable: false, diagnostic_status: "unavailable", controlled_reason: "not_applicable",
            correlation: { workflow_id: "workflow-1", request_id: null, request_digest_match: null, agent_record_present: false, core_record_present: false },
            dispatch_evidence: { barrier_crossed: false, provider_operation_captured: false, dispatch_result_known: false, transition_sequence_valid: null },
            verification_evidence: { status: null, target_fingerprint_state: "not_applicable", observed_state: null, observed_health: null, terminal_evidence: false },
        });
        mockGet.mockResolvedValueOnce({ data: { ...data, future_metadata: "ignored additive response field" } });
        await expect(getWorkflowRecoveryDiagnostic("workflow-1")).resolves.toMatchObject(data);
    });

    it("preserves missing reports and service failures as distinct outcomes", async () => {
        mockGet.mockRejectedValueOnce(axiosError(404)).mockRejectedValueOnce(axiosError(503));
        await expect(getWorkflowRecoveryDiagnostic("workflow-1")).resolves.toBeNull();
        await expect(getWorkflowRecoveryDiagnostic("workflow-1")).rejects.toBeInstanceOf(Error);
    });

    it("reads a workflow-scoped support bundle contract", async () => {
        const bundle = { applicable: true, metadata: { schema_version: "atlas-operational-support-bundle-v1" } };
        mockGet.mockResolvedValueOnce({ data: bundle });

        await expect(getWorkflowSupportBundle("workflow/one")).resolves.toBe(bundle);
        expect(mockGet).toHaveBeenCalledWith(
            "/api/v1/agent/workflows/workflow%2Fone/support-bundle",
        );
    });
});


it("reads an encoded saved workflow path without treating missing as an empty success", async () => {
    mockGet.mockResolvedValueOnce({ data: { workflow_session_id: "saved" } });
    await expect(getCandidateWorkflowShell("session/one")).resolves.toEqual({ workflow_session_id: "saved" });
    expect(mockGet).toHaveBeenLastCalledWith("/candidate-planning/session%2Fone/workflow");
    const missing = axiosError(404);
    mockGet.mockRejectedValueOnce(missing);
    await expect(getCandidateWorkflowShell("missing")).rejects.toBe(missing);
});


describe("Atlas Agent readable errors", () => {
    const fallback = "The saved result could not be loaded.";
    const failure = (detail: unknown, code?: string) => ({ isAxiosError: true, code,
        message: "Opaque Axios diagnostic", response: { data: { detail } } });

    it.each([
        ["plain message", "Planning is temporarily unavailable.", "Planning is temporarily unavailable."],
        ["structured message", { code: "unavailable", message: "Try loading the saved result." }, "Try loading the saved result."],
        ["missing detail", undefined, fallback], ["null detail", null, fallback], ["number detail", 42, fallback],
        ["boolean detail", false, fallback], ["empty detail", "", fallback], ["blank detail", " \n ", fallback],
        ["unknown object", { code: "unavailable", extra: true }, fallback],
        ["non-text message", { message: {} }, fallback], ["empty message", { message: "" }, fallback],
        ["blank message", { message: "  " }, fallback],
        ["validation list", [{ loc: ["body", "credential"], msg: "Input rejected", input: "SECRET-CANARY" }], fallback],
        ["string list", ["do not display arbitrary lists"], fallback],
    ])("formats %s as readable text", (_name, detail, expected) => {
        expect(getAtlasAgentErrorMessage(failure(detail), fallback)).toBe(expected);
    });

    it.each(["ECONNABORTED", "ETIMEDOUT"])("explains a %s timeout without claiming an action outcome", code => {
        expect(getAtlasAgentErrorMessage(failure(undefined, code), fallback)).toBe("Atlas Agent did not respond before the request timed out.");
    });

    it("explains a lost network response", () => {
        expect(getAtlasAgentErrorMessage(failure(undefined, "ERR_NETWORK"), fallback)).toBe("No response was received from Atlas Agent.");
    });

    it("keeps the public API message ahead of transport diagnostics", () => {
        expect(getAtlasAgentErrorMessage(failure({ message: "Saved information is unavailable." }, "ECONNABORTED"), fallback)).toBe("Saved information is unavailable.");
    });

    it.each([null, undefined, false, "opaque", {}, new Error("")])("uses the contextual fallback for an unreadable error: %j", error => {
        expect(getAtlasAgentErrorMessage(error, fallback)).toBe(fallback);
    });

    it("preserves a readable client error", () => {
        expect(getAtlasAgentErrorMessage(new Error("The saved reply did not match this session."), fallback)).toBe("The saved reply did not match this session.");
    });

    it("does not return a non-text client error message", () => {
        const error = new Error("placeholder");
        Object.assign(error, { message: { private: true } });
        expect(getAtlasAgentErrorMessage(error, fallback)).toBe(fallback);
    });
});
