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

import {
    getAgentInfo,
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
        const diagnostic = { applicable: true, diagnostic_status: "healthy" };
        mockGet.mockResolvedValueOnce({ data: diagnostic });

        await expect(getWorkflowRecoveryDiagnostic("workflow/one")).resolves.toBe(diagnostic);
        expect(mockGet).toHaveBeenCalledWith(
            "/api/v1/agent/workflows/workflow%2Fone/recovery-diagnostic",
        );
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
