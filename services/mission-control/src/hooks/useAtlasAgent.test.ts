import { getPendingApprovals } from "../api/approval";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getRepositoryStatus,
    getReviewReport,
    getSprintStatus,
    getVerificationReport,
} from "../api/atlas-agent";
import { useAtlasAgent } from "./useAtlasAgent";

vi.mock("../api/atlas-agent", () => ({
    getRepositoryStatus: vi.fn(),
    getSprintStatus: vi.fn(),
    getVerificationReport: vi.fn(),
    getReviewReport: vi.fn(),
    getAtlasAgentErrorMessage: (
        error: unknown,
        fallback: string,
    ) => (error instanceof Error ? error.message : fallback),
}));

vi.mock("../api/approval", () => ({
    getPendingApprovals: vi.fn(),
}));

const mockedGetRepositoryStatus = vi.mocked(
    getRepositoryStatus,
);
const mockedGetSprintStatus = vi.mocked(getSprintStatus);
const mockedGetVerificationReport = vi.mocked(
    getVerificationReport,
);
const mockedGetReviewReport = vi.mocked(getReviewReport);
const mockedGetPendingApprovals = vi.mocked(getPendingApprovals);

describe("useAtlasAgent", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("loads repository and published workflow status", async () => {
        mockedGetRepositoryStatus.mockResolvedValue({
            root: "/opt/atlas",
            branch: "feature/atlas-agent",
            head_commit: "7661770",
            is_clean: true,
            modified_files: [],
            staged_files: [],
            untracked_files: [],
        });
        mockedGetSprintStatus.mockResolvedValue({
            checkpoint_id: "A7B",
            title: "Mission Control integration",
            goal: "Display Atlas Agent status.",
            phase: "implementation",
        });
        mockedGetVerificationReport.mockResolvedValue({
            repository_root: "/opt/atlas",
            status: "passed",
            duration_seconds: 1.5,
            results: [],
        });
        mockedGetReviewReport.mockResolvedValue({
            request_id: "review-1",
            checkpoint_id: "A7B",
            status: "approved",
            findings: [],
            recommendations: [],
        });
        mockedGetPendingApprovals.mockResolvedValue([
            {
                identifier: "approval-1",
                checkpoint_id: "A12.5",
                request: {
                    checkpoint_id: "A12.5",
                    title: "Test Approval",
                    requested_tool: "git",
                    requested_command: ["clone"],
                    rationale: "Testing approval flow",
                },
                status: "pending",
            },
        ]);

        const { result } = renderHook(() => useAtlasAgent());

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false);
        });

        expect(result.current.error).toBeNull();
        expect(result.current.repository?.branch).toBe(
            "feature/atlas-agent",
        );
        expect(result.current.sprint?.checkpoint_id).toBe("A7B");
        expect(result.current.verification?.status).toBe("passed");
        expect(result.current.review?.status).toBe("approved");
        expect(result.current.approvals).toHaveLength(1);
    });

    it("preserves unpublished workflow resources as null", async () => {
        mockedGetRepositoryStatus.mockResolvedValue({
            root: "/opt/atlas",
            branch: "feature/atlas-agent",
            head_commit: "7661770",
            is_clean: true,
            modified_files: [],
            staged_files: [],
            untracked_files: [],
        });
        mockedGetSprintStatus.mockResolvedValue(null);
        mockedGetVerificationReport.mockResolvedValue(null);
        mockedGetReviewReport.mockResolvedValue(null);
        mockedGetPendingApprovals.mockResolvedValue([]);

        const { result } = renderHook(() => useAtlasAgent());

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false);
        });

        expect(result.current.repository).not.toBeNull();
        expect(result.current.sprint).toBeNull();
        expect(result.current.verification).toBeNull();
        expect(result.current.review).toBeNull();
        expect(result.current.error).toBeNull();
    });

    it("returns an unavailable state when a request fails", async () => {
        mockedGetRepositoryStatus.mockRejectedValue(
            new Error("Atlas Agent unavailable."),
        );
        mockedGetSprintStatus.mockResolvedValue(null);
        mockedGetVerificationReport.mockResolvedValue(null);
        mockedGetReviewReport.mockResolvedValue(null);
        mockedGetPendingApprovals.mockResolvedValue([]);

        const { result } = renderHook(() => useAtlasAgent());

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false);
        });

        expect(result.current.repository).toBeNull();
        expect(result.current.error).toBe(
            "Atlas Agent unavailable.",
        );
    });
});
