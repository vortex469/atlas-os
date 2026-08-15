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
    getReviewReport,
    getSprintStatus,
    getVerificationReport,
    getWorkflowOperationalLifecycle,
    getWorkflowRecoveryDiagnostic,
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
});
