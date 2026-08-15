import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getWorkflowDetail,
    getWorkflowOperationalLifecycle,
    getWorkflowRecoveryDiagnostic,
    getWorkflowSupportBundle,
    resumeWorkflow,
    submitWorkflowCommitApproval,
    submitWorkflowImplementationApproval,
    submitWorkflowVerificationApproval,
} from "../api/atlas-agent";
import { WorkflowPage } from "./WorkflowPage";
import type { WorkflowDetailResponse } from "../types/atlasAgent";
import { operationalLifecycle } from "../test/operationalLifecycle";

vi.mock("../api/atlas-agent", () => ({
    getAtlasAgentErrorMessage: (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback,
    getWorkflowDetail: vi.fn(),
    getWorkflowOperationalLifecycle: vi.fn(),
    getWorkflowRecoveryDiagnostic: vi.fn(),
    getWorkflowSupportBundle: vi.fn(),
    resumeWorkflow: vi.fn(),
    submitWorkflowCommitApproval: vi.fn(),
    submitWorkflowImplementationApproval: vi.fn(),
    submitWorkflowVerificationApproval: vi.fn(),
}));

const mockedGetWorkflowDetail = vi.mocked(getWorkflowDetail);
const mockedGetWorkflowOperationalLifecycle = vi.mocked(getWorkflowOperationalLifecycle);
const mockedGetWorkflowRecoveryDiagnostic = vi.mocked(getWorkflowRecoveryDiagnostic);
const mockedGetWorkflowSupportBundle = vi.mocked(getWorkflowSupportBundle);
const mockedResumeWorkflow = vi.mocked(resumeWorkflow);
const mockedSubmitWorkflowCommitApproval = vi.mocked(submitWorkflowCommitApproval);
const mockedSubmitWorkflowImplementationApproval = vi.mocked(submitWorkflowImplementationApproval);
const mockedSubmitWorkflowVerificationApproval = vi.mocked(submitWorkflowVerificationApproval);

function workflow(overrides: Partial<WorkflowDetailResponse> = {}): WorkflowDetailResponse {
    return {
        workflow_id: "workflow-123",
        workflow_source: "candidate",
        effect_kind: "repository_change",
        workflow_state: "awaiting_implementation_approval",
        planning_session_id: "candidate-plan-123",
        candidate_id: "candidate-123",
        candidate_fingerprint: "candidate-fingerprint-123",
        plan_fingerprint: "plan-fingerprint-123",
        implementation_approval_status: "pending",
        repository: "/opt/atlas",
        working_directory: "/opt/atlas/services/demo",
        translator_version: "candidate-translator-v1",
        affected_files: ["compose.yaml", "services/demo/Dockerfile"],
        implementation_request: {
            immutable_request_id: "impl-request-123",
            tool: "docker-compose",
            working_directory: "/opt/atlas/services/demo",
            affected_files: ["compose.yaml", "services/demo/Dockerfile"],
            repository: "/opt/atlas",
            translator_version: "candidate-translator-v1",
        },
        operational_action_request: null,
        operational_execution: null,
        approval_presentations: [],
        timeline: [
            { name: "Execution Candidate", status: "completed" },
            { name: "Planning Session", status: "completed" },
            { name: "Candidate Plan", status: "completed" },
            { name: "Workflow", status: "completed" },
            { name: "Implementation Approval", status: "current" },
            { name: "Execution", status: "waiting" },
            { name: "Verification", status: "waiting" },
            { name: "Review", status: "waiting" },
            { name: "Commit", status: "waiting" },
        ],
        execution: {
            execution_status: null,
            started_at: null,
            completed_at: null,
            result: null,
            changed_files_count: 0,
            tool: null,
            working_directory: null,
            repository: "/opt/atlas",
            changed_files: [],
            execution_request_id: null,
        },
        verification_plan: {
            verification_plan_id: "verification-plan-123",
            verifier_version: "verifier-v1",
            changed_files_digest: "changed-digest-123",
            verification_check_ids: ["compose-config", "compose-ps"],
            command_backed_checks: ["compose-config", "compose-ps"],
            working_directory: "/opt/atlas/services/demo",
            repository: "/opt/atlas",
            verification_status: "awaiting_verification_approval",
        },
        verification_evidence: {
            verification_status: "passed",
            completed_time: "2026-08-02T17:40:00Z",
            executed_checks: ["compose-config", "compose-ps"],
            check_results: [{ identifier: "compose-config", status: "passed", return_code: 0, duration_seconds: 1.2, output_truncated: false }],
            repository_head: "abc123",
            changed_files_digest: "changed-digest-123",
        },
        review: {
            review_result: "approved",
            review_status: "approved",
            approved: true,
            evidence_summary: "0 findings, 0 recommendations",
            changed_files: ["compose.yaml"],
            review_fingerprint: "review-fingerprint-123",
            model_assisted_review: "Disabled",
        },
        verification_approval_status: "pending",
        commit_request: null,
        commit_result: {
            commit_sha: null,
            commit_message: null,
            committed_files: [],
            completion_time: null,
        },
        commit_approval_status: "not_requested",
        ...overrides,
    };
}

function workflowAwaitingCommit(overrides: Partial<WorkflowDetailResponse> = {}): WorkflowDetailResponse {
    return workflow({
        workflow_state: "awaiting_commit_approval",
        commit_approval_status: "pending",
        commit_request: {
            commit_request_id: "approval-commit-workflow-123",
            repository: "/opt/atlas",
            branch: "feature/atlas-agent",
            expected_head: "abc123",
            commit_message: "feat(compose): update stack",
            reviewed_files: ["compose.yaml", "services/demo/Dockerfile"],
            reviewed_content_fingerprint: "reviewed-fingerprint-123",
            commit_approval_status: "pending",
        },
        timeline: [
            { name: "Execution Candidate", status: "completed" },
            { name: "Planning Session", status: "completed" },
            { name: "Candidate Plan", status: "completed" },
            { name: "Workflow", status: "completed" },
            { name: "Implementation Approval", status: "completed" },
            { name: "Execution", status: "completed" },
            { name: "Verification", status: "completed" },
            { name: "Review", status: "completed" },
            { name: "Commit", status: "current" },
        ],
        ...overrides,
    });
}

function workflowAwaitingVerification(overrides: Partial<WorkflowDetailResponse> = {}): WorkflowDetailResponse {
    return workflow({
        workflow_state: "awaiting_verification_approval",
        verification_approval_status: "approved",
        ...overrides,
    });
}

function renderPage(path = "/workflows/workflow-123") {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route path="/workflows/:workflowId" element={<WorkflowPage />} />
            </Routes>
        </MemoryRouter>,
    );
}

describe("WorkflowPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedGetWorkflowDetail.mockResolvedValue(workflow());
        mockedGetWorkflowOperationalLifecycle.mockResolvedValue(operationalLifecycle());
        mockedGetWorkflowRecoveryDiagnostic.mockResolvedValue(null);
        mockedGetWorkflowSupportBundle.mockResolvedValue(null);
        mockedResumeWorkflow.mockResolvedValue(undefined);
    });

    it("shows Resume Approved Implementation only when implementation is approved", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "awaiting_implementation_approval",
            implementation_approval_status: "approved",
        }));
        renderPage();

        expect(await screen.findByRole("button", { name: "Resume Approved Implementation" })).toBeInTheDocument();
    });

    it("does not show resume action when implementation is pending", async () => {
        renderPage();

        expect(await screen.findByText(/Implementation approval status: Pending/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Resume Approved Implementation" })).not.toBeInTheDocument();
    });

    it("does not show resume action when implementation is rejected", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "awaiting_implementation_approval",
            implementation_approval_status: "rejected",
        }));
        renderPage();

        expect(await screen.findByText("Implementation approval status: Rejected")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Resume Approved Implementation" })).not.toBeInTheDocument();
    });

    it("does not call resume automatically after approving implementation", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "awaiting_implementation_approval",
        }));
        mockedSubmitWorkflowImplementationApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_implementation_approval",
            implementation_approval_status: "approved",
            message: null,
        });

        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Implementation" }));
        await screen.findByText("Implementation approved. Execution is now available.");

        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
    });

    it("calls resume exactly once and blocks duplicate resume clicks while in flight", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "awaiting_implementation_approval",
            implementation_approval_status: "approved",
        }));
        let resolveResume: () => void = () => undefined;
        mockedResumeWorkflow.mockReturnValue(new Promise((resolve) => {
            resolveResume = resolve as () => void;
        }));

        renderPage();

        const resume = await screen.findByRole("button", { name: "Resume Approved Implementation" });
        fireEvent.click(resume);
        fireEvent.click(resume);

        await waitFor(() => expect(mockedResumeWorkflow).toHaveBeenCalledTimes(1));
        expect(screen.queryByRole("button", { name: "Resume Approved Implementation" })).not.toBeInTheDocument();

        resolveResume();
        await screen.findByText("Implementation");
    });

    it("reloads workflow detail on resume success and uses server-authoritative state", async () => {
        mockedGetWorkflowDetail
            .mockResolvedValueOnce(
                workflow({
                    workflow_state: "awaiting_implementation_approval",
                    implementation_approval_status: "approved",
                }),
            )
            .mockResolvedValueOnce(
                workflow({
                    workflow_state: "awaiting_verification_approval",
                    verification_approval_status: "pending",
                }),
            );

        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Resume Approved Implementation" }));

        expect(await screen.findByText("Awaiting Verification Approval")).toBeInTheDocument();
        expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2);
    });

    it("shows error and stays on page when resume fails, then refetches authoritative state", async () => {
        mockedGetWorkflowDetail
            .mockResolvedValueOnce(
                workflow({
                    workflow_state: "awaiting_verification_approval",
                    verification_approval_status: "approved",
                }),
            )
            .mockResolvedValueOnce(
                workflow({
                    workflow_state: "awaiting_verification_approval",
                    verification_approval_status: "approved",
                }),
            );
        mockedResumeWorkflow.mockRejectedValue(new Error("Workflow blocked"));

        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Resume Approved Verification" }));

        await screen.findByRole("alert");
        expect(screen.getByRole("alert")).toHaveTextContent("Workflow blocked");
        expect(screen.getByRole("button", { name: "Resume Approved Verification" })).toBeInTheDocument();
        expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2);
    });

    it("shows Resume Approved Verification for approved verification state", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflowAwaitingVerification({
            verification_approval_status: "approved",
        }));
        renderPage();

        expect(await screen.findByRole("button", { name: "Resume Approved Verification" })).toBeInTheDocument();
    });

    it("shows Resume Approved Commit for approved commit state", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(
            workflowAwaitingCommit({
                workflow_state: "awaiting_commit_approval",
                commit_approval_status: "approved",
            }),
        );
        renderPage();

        expect(await screen.findByRole("button", { name: "Resume Approved Commit" })).toBeInTheDocument();
    });

    it("never shows resume action for blocked workflow", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(
            workflow({
                workflow_state: "blocked",
            }),
        );
        renderPage();

        expect(screen.queryByRole("button", { name: /Resume Approved/i })).not.toBeInTheDocument();
    });

    it("never shows resume action for completed workflow", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(
            workflow({
                workflow_state: "completed",
            }),
        );
        renderPage();

        expect(await screen.findByText("Implementation approval status: Pending")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /Resume Approved/i })).not.toBeInTheDocument();
    });

    it("renders workflow and immutable implementation request details", async () => {
        renderPage();

        expect(await screen.findByRole("heading", { name: /Workflow workflow-123/i })).toBeInTheDocument();
        expect(screen.getByText("candidate-plan-123")).toBeInTheDocument();
        expect(screen.getByText("candidate-123")).toBeInTheDocument();
        expect(screen.getByText("candidate-fingerprint-123")).toBeInTheDocument();
        expect(screen.getByText("plan-fingerprint-123")).toBeInTheDocument();
        expect(screen.getAllByText("/opt/atlas").length).toBeGreaterThan(0);
        expect(screen.getAllByText("/opt/atlas/services/demo").length).toBeGreaterThan(0);
        expect(screen.getAllByText("candidate-translator-v1").length).toBeGreaterThan(0);
        expect(screen.getByText("impl-request-123")).toBeInTheDocument();
        expect(screen.getByText("docker-compose")).toBeInTheDocument();
        expect(screen.getAllByText("compose.yaml, services/demo/Dockerfile").length).toBeGreaterThan(0);
    });

    it("provides Open Audit link to workflow audit explorer", async () => {
        renderPage();

        expect(await screen.findByRole("link", { name: "Open Audit" })).toHaveAttribute(
            "href",
            "/workflows/workflow-123/audit",
        );
    });

    it("submits approve with only workflow id and decision", async () => {
        mockedSubmitWorkflowImplementationApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_execution",
            implementation_approval_status: "approved",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Implementation" }));

        await screen.findByText("Implementation approved. Execution is now available.");
        expect(mockedSubmitWorkflowImplementationApproval).toHaveBeenCalledTimes(1);
        expect(mockedSubmitWorkflowImplementationApproval).toHaveBeenCalledWith("workflow-123", "approve");
        expect(JSON.stringify(mockedSubmitWorkflowImplementationApproval.mock.calls[0])).not.toMatch(/argv|command|repository|working_directory|implementation_request|candidate_snapshot/);
    });

    it("submits reject with only workflow id and decision", async () => {
        mockedSubmitWorkflowImplementationApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "implementation_rejected",
            implementation_approval_status: "rejected",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Reject" }));

        await screen.findByText("Approval rejected.");
        expect(mockedSubmitWorkflowImplementationApproval).toHaveBeenCalledWith("workflow-123", "reject");
    });

    it("shows pending state and blocks duplicate submissions", async () => {
        let resolveApproval: (value: Awaited<ReturnType<typeof submitWorkflowImplementationApproval>>) => void = () => undefined;
        mockedSubmitWorkflowImplementationApproval.mockReturnValue(new Promise((resolve) => {
            resolveApproval = resolve;
        }));
        renderPage();

        const approve = await screen.findByRole("button", { name: "Approve Implementation" });
        fireEvent.click(approve);
        fireEvent.click(approve);

        expect(await screen.findByText("Submitting approval...")).toBeInTheDocument();
        expect(mockedSubmitWorkflowImplementationApproval).toHaveBeenCalledTimes(1);
        resolveApproval({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_execution",
            implementation_approval_status: "approved",
            message: null,
        });
        await screen.findByText("Implementation approved. Execution is now available.");
    });

    it("hides approval controls outside awaiting implementation approval", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "awaiting_execution",
            implementation_approval_status: "approved",
        }));
        renderPage();

        expect((await screen.findAllByText(/Approval controls are unavailable/i)).length).toBeGreaterThan(0);
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
    });

    it("hides implementation approval controls after an approve response without state transition", async () => {
        mockedGetWorkflowDetail
            .mockResolvedValueOnce(workflow())
            .mockResolvedValueOnce(workflow({ implementation_approval_status: "approved" }));
        mockedSubmitWorkflowImplementationApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_implementation_approval",
            implementation_approval_status: "approved",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Implementation" }));

        await screen.findByText("Implementation approved. Execution is now available.");
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
    });

    it("renders workflow rail and no execution, verification, or commit controls", async () => {
        renderPage();

        expect(await screen.findByText("Implementation")).toBeInTheDocument();
        expect(screen.getAllByText("Execution").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Verification").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Commit").length).toBeGreaterThan(0);
        expect(screen.getByText("current")).toBeInTheDocument();
        expect(screen.getAllByText("waiting").length).toBeGreaterThan(0);
        expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /verify/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /commit/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    });

    it("presents operational action approval without repository-only controls", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            effect_kind: "operational_action",
            operational_action_request: { request_id: "action-request-123" },
        }));
        renderPage();

        expect(await screen.findByRole("heading", { name: "Operational action approval" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Approve Exact Action" })).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Implementation Request" })).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Verification Plan" })).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Commit Request" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /commit/i })).not.toBeInTheDocument();
        expect(await screen.findByRole("heading", { name: "Operational lifecycle" })).toBeInTheDocument();
        expect(screen.getAllByText("resolved (approved)")).toHaveLength(2);
    });

    it("downloads only the sanitized in-memory support bundle", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        mockedGetWorkflowSupportBundle.mockResolvedValue({
            applicable: true,
            metadata: { schema_version: "atlas-operational-support-bundle-v1", generated_at: "2026-08-15T00:00:00Z", agent_version: "0.9", workflow_id: "workflow-123" },
            workflow: { candidate_id: "candidate-123", planning_session_id: "plan-123", effect_kind: "operational_action", execution_intent: "restart-service", target_label: "proxmox/qemu/110" },
            approvals: { preparation: null, operational_action: null },
            lifecycle: { availability: "complete", request_id: "request-1", request_digest: "digest-1", agent_execution_stage: "verified", core_ledger_state: "verified", transitions: [], transition_sequence_valid: true, barrier_crossed: true, barrier_crossing_count: 1, provider_operation_captured: true, provider_operation_capture_count: 1, dispatch_status: "succeeded", dispatch_result_known: true, provider_operation_reference: "UPID:sanitized", verification_status: "succeeded", observed_state: "running", observed_health: "running", terminal: true },
            diagnostic: { applicable: true, diagnostic_status: "healthy", consistency: "consistent", correlation: { workflow_id: "workflow-123", request_id: "request-1", request_digest_match: true, agent_record_present: true, core_record_present: true }, dispatch_evidence: { barrier_crossed: true, provider_operation_captured: true, dispatch_result_known: true, transition_sequence_valid: true }, verification_evidence: { status: "succeeded", target_fingerprint_state: "unchanged", observed_state: "running", observed_health: "running", terminal_evidence: true }, controlled_reason: null, safe_next_action: "none" },
            service_health: [],
            capability_boundary: { production_tuples: ["restart-service/proxmox/qemu"], agent_execution_intents: ["restart-service"], parity_status: "not_evaluated" },
            audit_refs: [],
            truncation: { transitions_truncated: true, audit_references_truncated: false, text_fields_truncated: [] },
            integrity: { digest: "operational-support-bundle-digest-v1:abc", purpose: "integrity_and_correlation_only" },
        });
        const createObjectURL = vi.fn(() => "blob:support-evidence");
        const revokeObjectURL = vi.fn();
        Object.defineProperty(URL, "createObjectURL", { value: createObjectURL, configurable: true });
        Object.defineProperty(URL, "revokeObjectURL", { value: revokeObjectURL, configurable: true });
        const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Prepare support evidence" }));

        await screen.findByText("atlas-operational-support-bundle-v1");
        expect(mockedGetWorkflowSupportBundle).toHaveBeenCalledWith("workflow-123");
        expect(screen.getByText(/integrity and correlation only/i)).toBeInTheDocument();
        expect(screen.getByText("Partial or truncated").nextElementSibling).toHaveTextContent("Yes");
        expect(createObjectURL).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("button", { name: "Download support evidence" }));

        expect(createObjectURL).toHaveBeenCalledOnce();
        expect(click).toHaveBeenCalledOnce();
        expect(revokeObjectURL).toHaveBeenCalledWith("blob:support-evidence");
        expect(screen.queryByRole("button", { name: /retry|run again|reconcile|upload/i })).not.toBeInTheDocument();
    });

    it("never loads operational lifecycle for a repository workflow", async () => {
        renderPage();

        await screen.findByRole("heading", { name: "Implementation approval" });
        expect(mockedGetWorkflowOperationalLifecycle).not.toHaveBeenCalled();
        expect(mockedGetWorkflowRecoveryDiagnostic).not.toHaveBeenCalled();
        expect(mockedGetWorkflowSupportBundle).not.toHaveBeenCalled();
        expect(screen.queryByRole("heading", { name: "Operational lifecycle" })).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Support evidence" })).not.toBeInTheDocument();
        expect(screen.queryByLabelText("Recovery summary")).not.toBeInTheDocument();
    });

    it("deterministically refreshes workflow and operational lifecycle together", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Refresh lifecycle" }));

        await waitFor(() => expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2));
        expect(mockedGetWorkflowOperationalLifecycle).toHaveBeenCalledTimes(2);
    });

    it("shows workflow not found", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(null);
        renderPage();

        expect(await screen.findByRole("alert")).toHaveTextContent("Workflow not found");
    });

    it("renders verification plan, evidence, and deterministic review", async () => {
        renderPage();

        expect(await screen.findByRole("heading", { name: "Verification Plan" })).toBeInTheDocument();
        expect(screen.getByText("verification-plan-123")).toBeInTheDocument();
        expect(screen.getByText("verifier-v1")).toBeInTheDocument();
        expect(screen.getAllByText("changed-digest-123").length).toBeGreaterThan(0);
        expect(screen.getAllByText("compose-config, compose-ps").length).toBeGreaterThan(0);
        expect(screen.getByRole("heading", { name: "Verification Evidence" })).toBeInTheDocument();
        expect(screen.getAllByText("abc123").length).toBeGreaterThan(0);
        expect(screen.getByText("compose-config: passed")).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Review" })).toBeInTheDocument();
        expect(screen.getByText("Deterministic review")).toBeInTheDocument();
        expect(screen.getByText("review-fingerprint-123")).toBeInTheDocument();
        expect(screen.getAllByText("Disabled").length).toBeGreaterThan(0);
    });

    it("submits verification approval with only workflow id and decision", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ workflow_state: "awaiting_verification_approval" }));
        mockedSubmitWorkflowVerificationApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_verification_approval",
            verification_approval_status: "approved",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Verification" }));

        await screen.findByText("Verification approved. Verification is now available.");
        expect(mockedSubmitWorkflowVerificationApproval).toHaveBeenCalledTimes(1);
        expect(mockedSubmitWorkflowVerificationApproval).toHaveBeenCalledWith("workflow-123", "approve");
        expect(JSON.stringify(mockedSubmitWorkflowVerificationApproval.mock.calls[0])).not.toMatch(/command|check|evidence|changed|review|commit/);
    });

    it("hides verification controls after a verification approve response without state transition", async () => {
        mockedGetWorkflowDetail
            .mockResolvedValueOnce(workflow({ workflow_state: "awaiting_verification_approval" }))
            .mockResolvedValueOnce(workflow({
                workflow_state: "awaiting_verification_approval",
                verification_approval_status: "approved",
            }));
        mockedSubmitWorkflowVerificationApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_verification_approval",
            verification_approval_status: "approved",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Verification" }));

        await screen.findByText("Verification approved. Verification is now available.");
        expect(screen.queryByRole("button", { name: "Approve Verification" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Reject Verification" })).not.toBeInTheDocument();
    });

    it("submits verification rejection and blocks duplicate clicks", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ workflow_state: "awaiting_verification_approval" }));
        let resolveApproval: (value: Awaited<ReturnType<typeof submitWorkflowVerificationApproval>>) => void = () => undefined;
        mockedSubmitWorkflowVerificationApproval.mockReturnValue(new Promise((resolve) => {
            resolveApproval = resolve;
        }));
        renderPage();

        const reject = await screen.findByRole("button", { name: "Reject Verification" });
        fireEvent.click(reject);
        fireEvent.click(reject);

        expect(await screen.findByText("Submitting verification approval...")).toBeInTheDocument();
        expect(mockedSubmitWorkflowVerificationApproval).toHaveBeenCalledTimes(1);
        expect(mockedSubmitWorkflowVerificationApproval).toHaveBeenCalledWith("workflow-123", "reject");
        resolveApproval({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_verification_approval",
            verification_approval_status: "rejected",
            message: null,
        });
        await screen.findByText("Verification approval rejected.");
    });

    it("renders commit request and reviewed files read-only", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflowAwaitingCommit());
        renderPage();

        expect(await screen.findByRole("heading", { name: "Commit Request" })).toBeInTheDocument();
        expect(screen.getByText("approval-commit-workflow-123")).toBeInTheDocument();
        expect(screen.getAllByText("/opt/atlas").length).toBeGreaterThan(0);
        expect(screen.getByText("feature/atlas-agent")).toBeInTheDocument();
        expect(screen.getAllByText("abc123").length).toBeGreaterThan(0);
        expect(screen.getByText("feat(compose): update stack")).toBeInTheDocument();
        expect(screen.getAllByText("compose.yaml, services/demo/Dockerfile").length).toBeGreaterThan(0);
        expect(screen.getByText("reviewed-fingerprint-123")).toBeInTheDocument();
        expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    });

    it("submits commit approval with only workflow id and decision", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflowAwaitingCommit());
        mockedSubmitWorkflowCommitApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_commit_approval",
            commit_approval_status: "approved",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Commit" }));

        await screen.findByText("Commit approved. Workflow may now complete through the existing backend resume path.");
        expect(mockedSubmitWorkflowCommitApproval).toHaveBeenCalledTimes(1);
        expect(mockedSubmitWorkflowCommitApproval).toHaveBeenCalledWith("workflow-123", "approve");
        expect(JSON.stringify(mockedSubmitWorkflowCommitApproval.mock.calls[0])).not.toMatch(/message|path|sha|fingerprint|evidence|repository|push|tag/);
    });

    it("hides commit controls after a commit approve response without state transition", async () => {
        mockedGetWorkflowDetail
            .mockResolvedValueOnce(workflowAwaitingCommit())
            .mockResolvedValueOnce(workflowAwaitingCommit({ commit_approval_status: "approved" }));
        mockedSubmitWorkflowCommitApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_commit_approval",
            commit_approval_status: "approved",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Commit" }));

        await screen.findByText("Commit approved. Workflow may now complete through the existing backend resume path.");
        expect(screen.queryByRole("button", { name: "Approve Commit" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Reject Commit" })).not.toBeInTheDocument();
    });

    it("submits commit rejection and blocks duplicate clicks", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflowAwaitingCommit());
        let resolveApproval: (value: Awaited<ReturnType<typeof submitWorkflowCommitApproval>>) => void = () => undefined;
        mockedSubmitWorkflowCommitApproval.mockReturnValue(new Promise((resolve) => {
            resolveApproval = resolve;
        }));
        renderPage();

        const reject = await screen.findByRole("button", { name: "Reject Commit" });
        fireEvent.click(reject);
        fireEvent.click(reject);

        expect(await screen.findByText("Submitting commit approval...")).toBeInTheDocument();
        expect(mockedSubmitWorkflowCommitApproval).toHaveBeenCalledTimes(1);
        expect(mockedSubmitWorkflowCommitApproval).toHaveBeenCalledWith("workflow-123", "reject");
        resolveApproval({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_commit_approval",
            commit_approval_status: "rejected",
            message: null,
        });
        await screen.findByText("Commit approval rejected.");
    });

    it("renders completed workflow commit result read-only", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflowAwaitingCommit({
            workflow_state: "completed",
            commit_approval_status: "approved",
            commit_result: {
                commit_sha: "def456",
                commit_message: "feat(compose): update stack",
                committed_files: ["compose.yaml", "services/demo/Dockerfile"],
                completion_time: "2026-08-02T18:00:00Z",
            },
        }));
        renderPage();

        expect(await screen.findByRole("heading", { name: "Completed workflow" })).toBeInTheDocument();
        expect(screen.getByText("def456")).toBeInTheDocument();
        expect(screen.getAllByText("feat(compose): update stack").length).toBeGreaterThan(0);
        expect(screen.getAllByText("compose.yaml, services/demo/Dockerfile").length).toBeGreaterThan(0);
        expect(screen.getByText("2026-08-02T18:00:00Z")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Approve Commit" })).not.toBeInTheDocument();
    });

    it("does not expose push, tag, amend, release, or rollback controls", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflowAwaitingCommit());
        renderPage();

        await screen.findByRole("heading", { name: "Commit Request" });
        expect(screen.queryByRole("button", { name: /push/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /tag/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /amend/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /release/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /roll back|rollback/i })).not.toBeInTheDocument();
    });

    it("maps approval error states", async () => {
        mockedSubmitWorkflowImplementationApproval.mockRejectedValue(new Error("approval already approved"));
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Implementation" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Approval already approved.");
    });
});
