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
    getWorkflowAudit,
    getWorkflowOperationalLifecycle,
    getWorkflowRecoveryDiagnostic,
    getWorkflowSupportBundle,
    listWorkflows,
} from "./atlas-agent";
import { operationalDiagnostic, operationalLifecycle } from "../test/operationalLifecycle";
import { workflowAudit } from "../test/workflowAudit";

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

    it("returns valid workflow list entries with the requested effect kind", async () => {
        const workflowList = {
            items: [{
                workflow_id: "workflow/one",
                workflow_source: "manual",
                workflow_state: "completed",
                effect_kind: "operational_action",
                execution_intent: "restart-service",
                candidate_id: null,
                planning_session_id: null,
                repository: null,
                target_id: "qemu/110",
                last_result_summary: "Completed",
                timeline: [],
            }],
            total: 1,
            limit: 10,
            offset: 0,
        };
        mockGet.mockResolvedValueOnce({ data: workflowList });

        await expect(listWorkflows({ effect_kind: "operational_action", limit: 10, offset: 0 }))
            .resolves.toEqual(workflowList);
        expect(mockGet).toHaveBeenCalledWith("/api/v1/agent/workflows", {
            params: { effect_kind: "operational_action", limit: 10, offset: 0 },
        });
    });

    it("rejects malformed workflow list entries", async () => {
        mockGet.mockResolvedValueOnce({ data: {
            items: [null], total: 1, limit: 10, offset: 0,
        } });

        await expect(listWorkflows()).rejects.toThrow("Malformed workflow list payload.");
    });

    it("rejects workflow entries outside the requested effect kind", async () => {
        mockGet.mockResolvedValueOnce({ data: {
            items: [{
                workflow_id: "workflow-1", workflow_source: "candidate", workflow_state: "completed",
                effect_kind: "repository_change", execution_intent: "update-compose-stack",
                candidate_id: "candidate-1", planning_session_id: "plan-1", repository: "/workspace",
                target_id: "stack-1", last_result_summary: "Completed", timeline: [],
            }],
            total: 1, limit: 10, offset: 0,
        } });

        await expect(listWorkflows({ effect_kind: "operational_action" }))
            .rejects.toThrow("Malformed workflow list payload.");
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
        const lifecycle = operationalLifecycle({ workflow_id: "workflow/one" });
        mockGet.mockResolvedValueOnce({ data: lifecycle });

        await expect(getWorkflowOperationalLifecycle("workflow/one")).resolves.toBe(lifecycle);
        expect(mockGet).toHaveBeenCalledWith(
            "/api/v1/agent/workflows/workflow%2Fone/operational-lifecycle",
        );
    });

    it("rejects malformed operational lifecycle details", async () => {
        mockGet.mockResolvedValueOnce({ data: { ...operationalLifecycle(), target_label: 42 } });

        await expect(getWorkflowOperationalLifecycle("workflow/one")).rejects.toThrow(
            "Malformed operational lifecycle payload.",
        );
    });

    it("reads a workflow-scoped recovery diagnostic contract", async () => {
        const diagnostic = operationalDiagnostic({
            correlation: { ...operationalDiagnostic().correlation, workflow_id: "workflow/one" },
        });
        mockGet.mockResolvedValueOnce({ data: diagnostic });

        await expect(getWorkflowRecoveryDiagnostic("workflow/one")).resolves.toBe(diagnostic);
        expect(mockGet).toHaveBeenCalledWith(
            "/api/v1/agent/workflows/workflow%2Fone/recovery-diagnostic",
        );
    });

    it("rejects unknown recovery diagnostic states", async () => {
        mockGet.mockResolvedValueOnce({ data: { ...operationalDiagnostic(), diagnostic_status: "executed" } });

        await expect(getWorkflowRecoveryDiagnostic("workflow/one")).rejects.toThrow(
            "Malformed workflow recovery diagnostic payload.",
        );
    });

    it("reads a complete workflow audit response", async () => {
        const audit = workflowAudit();
        mockGet.mockResolvedValueOnce({ data: audit });

        await expect(getWorkflowAudit("workflow/one")).resolves.toBe(audit);
        expect(mockGet).toHaveBeenCalledWith(
            "/api/v1/agent/workflows/workflow%2Fone/audit",
        );
    });

    it("rejects malformed workflow audit stage data", async () => {
        mockGet.mockResolvedValueOnce({ data: { ...workflowAudit(), timeline: [null] } });

        await expect(getWorkflowAudit("workflow/one")).rejects.toThrow(
            "Malformed workflow audit payload.",
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
