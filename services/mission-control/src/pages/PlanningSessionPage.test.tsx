import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    createCandidateWorkflowShell,
    generateCandidatePlan,
    getCandidatePlan,
    getCandidatePlanningSession,
} from "../api/atlas-agent";
import type {
    CandidatePlanApiResponse,
    CandidatePlanningResponse,
    CandidateWorkflowResponse,
    OperationalCandidatePlanApiResponse,
} from "../types/atlasAgent";
import { unreadableWorkflowFields } from "../test/workflowSummary";
import { operationalPlan } from "../test/operationalPlanning";
import { PlanningSessionPage } from "./PlanningSessionPage";

vi.mock("../api/atlas-agent", () => ({
    createCandidateWorkflowShell: vi.fn(),
    generateCandidatePlan: vi.fn(),
    getAtlasAgentErrorMessage: (error: unknown, fallback: string) =>
        error instanceof Error ? error.message : fallback,
    getCandidatePlan: vi.fn(),
    getCandidatePlanningSession: vi.fn(),
}));

const mockedGetCandidatePlanningSession = vi.mocked(getCandidatePlanningSession);
const mockedCreateCandidateWorkflowShell = vi.mocked(createCandidateWorkflowShell);
const mockedGenerateCandidatePlan = vi.mocked(generateCandidatePlan);
const mockedGetCandidatePlan = vi.mocked(getCandidatePlan);

function session(overrides: Partial<CandidatePlanningResponse> = {}): CandidatePlanningResponse {
    return {
        session_id: "candidate-plan-1",
        candidate_id: "candidate-1",
        status: "ready_for_planning",
        planning_allowed: true,
        intake_status: "accepted_for_planning",
        intake_reason_codes: [],
        candidate_fingerprint: "fingerprint-1",
        unsupported_reason: null,
        plan: null,
        planning_failure: null,
        ...overrides,
    };
}

function plan(overrides: Partial<CandidatePlanApiResponse> = {}): CandidatePlanApiResponse {
    return {
        identifier: "plan-1",
        session_id: "candidate-plan-1",
        candidate_id: "candidate-1",
        candidate_fingerprint: "fingerprint-1",
        title: "Update Home Assistant compose stack",
        objective: "Update the compose stack safely.",
        assumptions: ["Operator has reviewed the candidate."],
        constraints: ["No implementation commands are included."],
        proposed_steps: ["Review compose changes.", "Prepare validation."],
        likely_affected_components: ["home-assistant"],
        likely_affected_files: ["compose/home-assistant.yaml"],
        verification_strategy: ["Run configuration validation."],
        rollback_considerations: ["Restore previous compose file."],
        unresolved_questions: ["Confirm maintenance window."],
        evidence_ids: ["evidence-1"],
        created_at: "2026-01-01T00:00:00Z",
        repository_branch: "feature/atlas-agent",
        repository_head: "abc123",
        revalidated_candidate_fingerprint: "fingerprint-1",
        ...overrides,
    };
}

function workflow(overrides: Partial<CandidateWorkflowResponse> = {}): CandidateWorkflowResponse {
    return {
        candidate_planning_session_id: "candidate-plan-1",
        candidate_id: "candidate-1",
        candidate_fingerprint: "fingerprint-1",
        candidate_plan_id: "plan-1",
        candidate_plan_fingerprint: "plan-fingerprint-1",
        workflow_session_id: "workflow-1",
        workflow_status: "approval_pending",
        implementation_approval_request_id: "approval-1",
        conversion_status: "workflow_created",
        core_revalidation_status: "accepted_for_planning",
        reason_codes: [],
        failure: null,
        ...overrides,
    };
}

function renderPage(path = "/candidate-planning/candidate-plan-1") {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route path="/candidate-planning/:sessionId" element={<PlanningSessionPage />} />
            </Routes>
        </MemoryRouter>,
    );
}

const unreadablePlans: [string, unknown][] = [
    ["title", { title: {} }], ["objective", { objective: [] }],
    ["assumptions", { assumptions: null }], ["constraints", { constraints: {} }],
    ["steps", { proposed_steps: [{}] }], ["files", { likely_affected_files: [null] }],
    ["verification", { verification_strategy: undefined }], ["rollback", { rollback_considerations: [42] }],
    ["questions", { unresolved_questions: "none" }], ["evidence", { evidence_ids: [{}] }],
    ["branch", { repository_branch: {} }], ["commit", { repository_head: [] }],
    ["non-object", false],
];

const unreadableSessions: [string, object][] = [
    ["status", { status: {} }], ["blank status", { status: " " }],
    ["planning flag", { planning_allowed: "true" }], ["fingerprint", { candidate_fingerprint: {} }],
    ["predecessor", { predecessor_session_id: {} }], ["successor", { successor_session_id: {} }],
    ["successor traversal", { successor_session_id: ".." }], ["successor Unicode", { successor_session_id: "\ud800" }],
    ["successor whitespace", { successor_session_id: " leading" }], ["successor control", { successor_session_id: "bad\u0000id" }],
    ["unsupported reason", { unsupported_reason: {} }], ["missing failure", { planning_failure: undefined }],
    ["failure", { planning_failure: {} }], ["failure message", { planning_failure: { code: "failed", message: {} } }],
    ["failure code", { planning_failure: { code: {}, message: "failed" } }],
    ["workflow Unicode", { workflow_session_id: "\ud800" }],
];

describe("PlanningSessionPage", () => {
    it.each(unreadableWorkflowFields)("recovers an unreadable workflow creation %s without repeating it", async (_field, fields) => {
        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "plan_ready", plan: plan() }))
            .mockResolvedValueOnce(session({ status: "workflow_created", planning_allowed: false, workflow_session_id: "workflow-1" }));
        mockedCreateCandidateWorkflowShell.mockResolvedValue(workflow(fields as Partial<CandidateWorkflowResponse>));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Create Workflow" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("The workflow summary response is incomplete or unreadable.");
        expect(screen.queryByRole("link", { name: "Review workflow" })).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Check saved planning" }));
        expect(await screen.findByRole("link", { name: "Open existing workflow" })).toHaveAttribute("href", "/workflows/workflow-1");
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledExactlyOnceWith("candidate-plan-1");
        expect(mockedGetCandidatePlanningSession).toHaveBeenCalledTimes(2);
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
    });

    it("keeps readable future workflow labels and unused metadata reviewable", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: plan() }));
        mockedCreateCandidateWorkflowShell.mockResolvedValue(workflow({ workflow_status: "future_state", conversion_status: "future_conversion",
            candidate_plan_id: {}, core_revalidation_status: {}, future_metadata: { extra: true } } as unknown as Partial<CandidateWorkflowResponse>));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Create Workflow" }));
        expect(await screen.findByRole("link", { name: "Review workflow" })).toHaveAttribute("href", "/candidate-planning/candidate-plan-1/workflow");
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledTimes(1);
    });

    for (const source of ["saved", "generated"] as const) {
        it.each(unreadableSessions)(`recovers unreadable ${source} session %s using only a new read`, async (_field, fields) => {
            const untrusted = session({ status: "plan_ready", ...fields } as Partial<CandidatePlanningResponse>);
            if (source === "saved") mockedGetCandidatePlanningSession.mockResolvedValueOnce(untrusted);
            else mockedGenerateCandidatePlan.mockResolvedValueOnce(untrusted);
            const user = userEvent.setup();
            renderPage();
            if (source === "generated") await user.click(await screen.findByRole("button", { name: "Generate Plan" }));
            expect(await screen.findByRole("alert")).toHaveTextContent("The planning session response is incomplete or unreadable.");
            expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
            expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
            expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
            await user.click(screen.getByRole("button", { name: source === "saved" ? "Try again" : "Check saved planning" }));
            await screen.findByRole("button", { name: "Generate Plan" });
            expect(mockedGetCandidatePlanningSession).toHaveBeenCalledTimes(2);
            expect(mockedGenerateCandidatePlan).toHaveBeenCalledTimes(source === "saved" ? 0 : 1);
        });
    }

    it.each([{}, "", "..", "\ud800", "bad\u0000id"])("does not use an unreadable proposal reference: %j", async candidate_id => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ candidate_id } as unknown as Partial<CandidatePlanningResponse>));
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("The planning session response is incomplete or unreadable.");
        expect(screen.queryByRole("link", { name: "Review original proposal" })).not.toBeInTheDocument();
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
    });

    it("rejects a non-object planning session through the read recovery view", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(false as unknown as CandidatePlanningResponse);
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("The planning session response is incomplete or unreadable.");
        expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
    });

    it.each(["", "next/é"])("accepts readable future session labels and optional lineage: %j", async successor_session_id => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "future_state", planning_allowed: false,
            candidate_id: "proposal/é", successor_session_id, predecessor_session_id: "previous", candidate_fingerprint: null,
            intake_status: {}, intake_reason_codes: null, future_metadata: { extra: true } } as unknown as Partial<CandidatePlanningResponse>));
        renderPage();
        expect(await screen.findByRole("link", { name: "Review original proposal" })).toHaveAttribute("href", "/execution-candidates/proposal%2F%C3%A9");
        if (successor_session_id) expect(screen.getByRole("link", { name: "Open newer session" })).toHaveAttribute("href", "/candidate-planning/next%2F%C3%A9");
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    for (const source of ["embedded", "generated"] as const) {
        it.each(unreadablePlans)(`recovers from unreadable ${source} plan %s without creating a workflow`, async (_field, override) => {
            const untrusted = (override === false ? false : { ...plan(), ...override as object }) as unknown as CandidatePlanApiResponse;
            const response = session({ status: "plan_ready", plan: untrusted });
            if (source === "embedded") mockedGetCandidatePlanningSession.mockResolvedValueOnce(response);
            else mockedGenerateCandidatePlan.mockResolvedValueOnce(response);
            const user = userEvent.setup();
            renderPage();
            if (source === "generated") await user.click(await screen.findByRole("button", { name: "Generate Plan" }));
            expect(await screen.findByRole("alert")).toHaveTextContent("The repository plan response is incomplete or unreadable.");
            expect(screen.queryByText("Generate a plan to review. This does not apply changes or grant approval.")).not.toBeInTheDocument();
            expect(screen.queryByText("Plan is ready.")).not.toBeInTheDocument();
            expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
            expect(screen.queryByText("Plan details")).not.toBeInTheDocument();
            expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
            expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
            await user.click(screen.getByRole("button", { name: source === "embedded" ? "Try again" : "Check saved planning" }));
            await screen.findByRole("button", { name: "Generate Plan" });
            expect(mockedGetCandidatePlanningSession).toHaveBeenCalledTimes(2);
            expect(mockedGenerateCandidatePlan).toHaveBeenCalledTimes(source === "embedded" ? 0 : 1);
        });
    }

    it.each([false, { ...plan(), proposed_steps: null }])("rejects an unreadable separately loaded repository plan: %j", async untrusted => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready" }));
        mockedGetCandidatePlan.mockResolvedValue(untrusted as unknown as CandidatePlanApiResponse);
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("The repository plan response is incomplete or unreadable.");
        expect(mockedGetCandidatePlan).toHaveBeenCalledExactlyOnceWith("candidate-plan-1");
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
    });

    it("accepts readable plans with richer unused metadata", async () => {
        const compatible = { ...plan(), identifier: { future: true }, likely_affected_components: [{}], created_at: {}, future_metadata: { extra: true } } as unknown as CandidatePlanApiResponse;
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: compatible }));
        renderPage();
        expect(await screen.findByRole("heading", { name: "Review saved plan" })).toBeVisible();
        expect(screen.getByText("Review compose changes.")).toBeVisible();
        expect(screen.getByRole("button", { name: "Create Workflow" })).toBeEnabled();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it.each(["workflow-1", null])("opens an existing workflow using reads only (reference: %s)", async workflow_session_id => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "workflow_created", planning_allowed: false, workflow_session_id }));
        renderPage();
        const link = await screen.findByRole("link", { name: workflow_session_id ? "Open existing workflow" : "Browse workflows" });
        expect(link).toHaveAttribute("href", workflow_session_id ? "/workflows/workflow-1" : "/workflows");
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
    });

    it.each(["missing", "unavailable"])("retries a %s planning read without submitting an action", async state => {
        if (state === "missing") mockedGetCandidatePlanningSession.mockResolvedValueOnce(null);
        else mockedGetCandidatePlanningSession.mockRejectedValueOnce(new Error("Read unavailable"));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Try again" }));
        await screen.findByRole("button", { name: "Generate Plan" });
        expect(mockedGetCandidatePlanningSession).toHaveBeenCalledTimes(2);
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it("hides old planning actions during refresh and applies the latest read", async () => {
        let finish!: (value: CandidatePlanningResponse) => void;
        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session()).mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Refresh planning" }));
        expect(screen.getByRole("status")).toHaveTextContent("Loading planning session");
        expect(screen.getByRole("link", { name: "← Change proposals" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Refresh planning" })).not.toBeInTheDocument();
        await act(async () => finish(session({ status: "workflow_created", planning_allowed: false, workflow_session_id: "workflow-1" })));
        expect(await screen.findByRole("link", { name: "Open existing workflow" })).toHaveAttribute("href", "/workflows/workflow-1");
        expect(mockedGetCandidatePlanningSession).toHaveBeenCalledTimes(2);
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it.each(["plan", "workflow"])("checks a saved %s after a lost reply without repeating the action", async action => {
        const ready = action === "workflow";
        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session(ready ? { status: "plan_ready", plan: plan() } : {}))
            .mockResolvedValueOnce(session({ status: ready ? "workflow_created" : "plan_ready", planning_allowed: false, plan: plan(), workflow_session_id: ready ? "workflow-1" : null }));
        if (ready) mockedCreateCandidateWorkflowShell.mockRejectedValueOnce(new Error("Reply lost"));
        else mockedGenerateCandidatePlan.mockRejectedValueOnce(new Error("Reply lost"));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: ready ? "Create Workflow" : "Generate Plan" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(ready ? "Workflow result unavailable" : "Plan result unavailable");
        await user.click(screen.getByRole("button", { name: "Check saved planning" }));
        if (ready) await screen.findByRole("link", { name: "Open existing workflow" });
        else await screen.findByText("Plan details");
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(mockedGetCandidatePlanningSession).toHaveBeenCalledTimes(2);
        expect(mockedGenerateCandidatePlan).toHaveBeenCalledTimes(ready ? 0 : 1);
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledTimes(ready ? 1 : 0);
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
    });

    it("keeps a converted maintenance plan available for review without offering another workflow", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", operational_plan: operationalPlan(), workflow_session_id: "workflow-1" }));
        renderPage();
        await screen.findByRole("heading", { name: "Maintenance plan" });
        expect(screen.getByRole("link", { name: "Open existing workflow" })).toHaveAttribute("href", "/workflows/workflow-1");
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
    });

    it.each(["", "..", "invalid\u0000id", { unexpected: true }])("does not build a workflow link from an unusable reference: %j", async reference => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "workflow_created", planning_allowed: false, workflow_session_id: reference as string }));
        renderPage();
        expect(await screen.findByRole("link", { name: "Browse workflows" })).toHaveAttribute("href", "/workflows");
        expect(screen.queryByRole("link", { name: "Open existing workflow" })).not.toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it("renders the existing maintenance plan without requesting a repository plan", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", operational_plan: operationalPlan() }));
        renderPage();
        await screen.findByRole("heading", { name: "Maintenance plan" });
        expect(screen.getByText("proxmox/qemu/110")).toBeVisible();
        expect(screen.getByText("Temporary service interruption.")).toBeVisible();
        expect(screen.getByText(/Stop and require operator review/)).toBeVisible();
        expect(screen.getByRole("link", { name: "Review original proposal" })).toHaveAttribute("href", "/execution-candidates/candidate-1");
        expect(screen.queryByText("Supported intent")).not.toBeInTheDocument();
        expect(screen.queryByText("update-compose-stack")).not.toBeInTheDocument();
        expect(screen.queryByText("Affected repository")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Create Workflow" })).toBeEnabled();
        expect(screen.getByRole("heading", { name: "Review saved plan", level: 1 })).toBeVisible();
        expect(screen.getByRole("heading", { name: "Saved plan", level: 2 })).toBeVisible();
        expect(screen.getByRole("heading", { name: "Create a workflow", level: 2 })).toBeVisible();
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it("displays a generated maintenance plan without falling back to the repository endpoint", async () => {
        mockedGenerateCandidatePlan.mockResolvedValue(session({ status: "plan_ready", operational_plan: operationalPlan() }));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));
        await screen.findByRole("heading", { name: "Maintenance plan" });
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
        expect(mockedGenerateCandidatePlan).toHaveBeenCalledExactlyOnceWith("candidate-plan-1");
        await user.click(screen.getByRole("button", { name: "Create Workflow" }));
        await screen.findByRole("link", { name: "Review workflow" });
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledExactlyOnceWith("candidate-plan-1");
    });

    it("keeps maintenance review read-only when planning is unavailable", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", planning_allowed: false, operational_plan: operationalPlan() }));
        renderPage();
        await screen.findByRole("heading", { name: "Maintenance plan" });
        expect(screen.getByRole("heading", { name: "Review saved plan", level: 1 })).toBeVisible();
        expect(screen.getByRole("heading", { name: "Workflow creation unavailable", level: 2 })).toBeVisible();
        expect(screen.getByText("Creating a workflow is not available for this session. You can review this plan and refresh planning to check the latest status.")).toBeVisible();
        expect(screen.queryByRole("heading", { name: "Create a workflow" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
    });

    it.each([
        ["session", { session_id: "different-session" }],
        ["candidate", { candidate_id: "different-candidate" }],
        ["effect", { effect_kind: "repository_change" }],
        ["verification identity", { verification: { ...operationalPlan().verification, identity_fingerprint: "different-target" } }],
        ["starting state", { verification: { ...operationalPlan().verification, pre_state: "stopped" } }],
        ["missing verification", { verification: null }],
        ["malformed considerations", { failure_considerations: null }],
    ])("refuses an invalid maintenance plan %s without creating a workflow", async (_name, override) => {
        const untrusted = { ...operationalPlan(), ...override } as OperationalCandidatePlanApiResponse;
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", operational_plan: untrusted }));
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("does not match this planning session or target");
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
    });

    it("refuses conflicting repository and maintenance plans", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: plan(), operational_plan: operationalPlan() }));
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("conflicting plan types");
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
    });

    it("refuses mismatched maintenance verification returned by generation", async () => {
        mockedGenerateCandidatePlan.mockResolvedValue(session({ status: "plan_ready", operational_plan: operationalPlan({ verification: { ...operationalPlan().verification, identity_fingerprint: "different-target" } }) }));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("does not match this planning session or target");
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
    });

    beforeEach(() => {
        vi.resetAllMocks();
        mockedGetCandidatePlanningSession.mockResolvedValue(session());
        mockedGenerateCandidatePlan.mockResolvedValue(session({ status: "plan_ready", plan: plan() }));
        mockedCreateCandidateWorkflowShell.mockResolvedValue(workflow());
        mockedGetCandidatePlan.mockResolvedValue(plan());
    });

    it("renders planning session metadata, workflow rail, and no execution controls", async () => {
        const user = userEvent.setup();
        renderPage();

        expect(await screen.findByText("Planning Session ID", { exact: true })).toBeInTheDocument();
        expect(screen.getByText("candidate-plan-1", { exact: true })).not.toBeVisible();
        expect(screen.getByRole("heading", { name: "Plan this change" })).toBeVisible();
        expect(screen.getByText("candidate-1")).toBeInTheDocument();
        expect(screen.getAllByText("Ready For Planning").length).toBeGreaterThan(0);
        expect(screen.queryByText("Not exposed by Atlas Agent API")).not.toBeInTheDocument();
        expect(screen.queryByText("Supported intent")).not.toBeInTheDocument();
        expect(screen.getByText("fingerprint-1")).toBeInTheDocument();
        expect(screen.getByText("Proposal")).toBeInTheDocument();
        expect(screen.getByText("Planning").closest("li")).toHaveAttribute("aria-current", "step");
        expect(within(screen.getByRole("region", { name: "Planning progress" })).getByText("Plan")).toBeInTheDocument();
        expect(screen.queryByText("Disabled")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /execute|approve|create workflow|implementation|commit/i })).not.toBeInTheDocument();
        const disclosure = screen.getByText("Technical details", { exact: true });
        expect(disclosure.closest("details")).not.toHaveAttribute("open");
        expect(screen.getByText("fingerprint-1")).not.toBeVisible();
        expect(screen.getByRole("button", { name: "Generate Plan" })).toBeVisible();
        await user.click(disclosure);
        expect(screen.getByText("candidate-plan-1", { exact: true })).toBeVisible();
        expect(screen.getByText("fingerprint-1")).toBeVisible();
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it("renders lineage links for successor sessions and predecessor metadata", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(
            session({
                session_id: "candidate-plan-2",
                predecessor_session_id: "candidate-plan-1",
                successor_session_id: "candidate-plan-3",
            }),
        );
        renderPage("/candidate-planning/candidate-plan-2");

        expect(await screen.findByText("This session follows an earlier planning session.")).toBeInTheDocument();
        const earlierLink = screen.getByRole("link", { name: "Open earlier session" });
        expect(earlierLink).toHaveAttribute("href", "/candidate-planning/candidate-plan-1");
        expect(screen.getByText("A newer planning session is available.")).toBeInTheDocument();
        const newerLink = screen.getByRole("link", { name: "Open newer session" });
        expect(newerLink).toHaveAttribute("href", "/candidate-planning/candidate-plan-3");
        expect(screen.getByText("candidate-plan-1", { exact: true })).not.toBeVisible();
        expect(screen.getByText("candidate-plan-3", { exact: true })).not.toBeVisible();
        await userEvent.setup().click(screen.getByText("Technical details", { exact: true }));
        expect(screen.getByText("candidate-plan-1", { exact: true })).toBeVisible();
        expect(screen.getByText("candidate-plan-3", { exact: true })).toBeVisible();
    });

    it("generates a plan and renders the read-only plan viewer", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByRole("button", { name: "Generate Plan" });
        await user.click(screen.getByRole("button", { name: "Generate Plan" }));

        await waitFor(() => expect(mockedGenerateCandidatePlan).toHaveBeenCalledWith("candidate-plan-1"));
        expect(await screen.findByText("Plan details")).toBeVisible();
        expect(screen.getByText("Update Home Assistant compose stack")).toBeVisible();
        expect(screen.getByText("Objective: Update the compose stack safely.")).toBeVisible();
        expect(screen.getByText("Operator has reviewed the candidate.")).toBeVisible();
        expect(screen.getByText("No implementation commands are included.")).toBeVisible();
        expect(screen.getByText("Review compose changes.")).toBeVisible();
        expect(screen.getByText("Branch: feature/atlas-agent")).not.toBeVisible();
        expect(screen.getByText("compose/home-assistant.yaml")).toBeVisible();
        expect(screen.getByText("Run configuration validation.")).toBeVisible();
        expect(screen.getByText("Restore previous compose file.")).toBeVisible();
        expect(screen.getByText("Confirm maintenance window.")).toBeVisible();
        expect(screen.getByText("evidence-1")).not.toBeVisible();
        const references = screen.getByText("Plan references", { exact: true });
        expect(references.closest("details")).not.toHaveAttribute("open");
        await user.click(references);
        expect(screen.getByText("Branch: feature/atlas-agent")).toBeVisible();
        expect(screen.getByText("Commit: abc123")).toBeVisible();
        expect(screen.getByText("evidence-1")).toBeVisible();
        await user.click(references);
        expect(screen.getByText("Branch: feature/atlas-agent")).not.toBeVisible();
        expect(mockedGetCandidatePlanningSession).toHaveBeenCalledTimes(1);
        expect(mockedGenerateCandidatePlan).toHaveBeenCalledExactlyOnceWith("candidate-plan-1");
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
        expect(screen.queryByText(/argv|execution metadata/i)).not.toBeInTheDocument();
    });

    it("blocks duplicate Generate Plan requests", async () => {
        const user = userEvent.setup();
        let resolveRequest!: (value: CandidatePlanningResponse) => void;
        mockedGenerateCandidatePlan.mockReturnValue(new Promise((resolve) => {
            resolveRequest = resolve;
        }));

        renderPage();
        const button = await screen.findByRole("button", { name: "Generate Plan" });
        await user.dblClick(button);

        expect(mockedGenerateCandidatePlan).toHaveBeenCalledTimes(1);
        expect(screen.getAllByText("Generating plan...").length).toBeGreaterThan(0);
        expect(screen.getByRole("button", { name: "Refresh planning" })).toBeDisabled();
        resolveRequest(session({ status: "plan_ready", plan: plan() }));
        expect(await screen.findByText("Plan details")).toBeInTheDocument();
    });

    it("loads an existing plan when session is already plan_ready", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready" }));
        renderPage();

        expect(await screen.findByText("Plan details")).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Review saved plan", level: 1 })).toBeVisible();
        expect(screen.getByText("Review the saved plan below. Later changes still need separate approvals.")).toBeVisible();
        expect(screen.queryByText("Generate a plan to review. This does not apply changes or grant approval.")).not.toBeInTheDocument();
        expect(mockedGetCandidatePlan).toHaveBeenCalledWith("candidate-plan-1");
    });

    it("renders planning failure, unsupported, stale, Core unavailable, persistence, and Agent unavailable states", async () => {
        const user = userEvent.setup();
        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "planning_failed", planning_failure: { code: "planning_validation_failed", message: "Plan validation failed" } }));
        renderPage();
        expect(await screen.findByText("Planning failed.")).toBeInTheDocument();
        expect(screen.getByText("Atlas could not produce a plan that passed safety checks. Refresh the proposal and try again.")).toBeVisible();
        const failureMessage = screen.getByText("Plan validation failed", { exact: true });
        expect(failureMessage).not.toBeVisible();
        const technicalDetails = screen.getByText("Technical details", { exact: true });
        expect(technicalDetails.closest("details")).not.toHaveAttribute("open");
        await user.click(technicalDetails);
        expect(failureMessage).toBeVisible();

        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "unsupported_intent", unsupported_reason: "Unsupported intent" }));
        cleanup();
        renderPage();
        expect(await screen.findByText("Planning unavailable.")).toBeVisible();
        expect(screen.getByText("This change type is not supported for planning.")).toBeVisible();
        const unsupportedReason = screen.getByText("Unsupported intent", { exact: true });
        expect(unsupportedReason).not.toBeVisible();
        await user.click(screen.getByText("Technical details", { exact: true }));
        expect(unsupportedReason).toBeVisible();

        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "stale_before_planning" }));
        cleanup();
        renderPage();
        expect(await screen.findByText("Proposal needs refresh.")).toBeVisible();
        expect(screen.getByText("The proposal changed or expired. Refresh it before planning again.")).toBeVisible();

        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "planning_failed", planning_failure: { code: "atlas_core_unavailable", message: "Core unavailable" } }));
        cleanup();
        renderPage();
        expect(await screen.findByText("Atlas Core is unavailable.")).toBeVisible();
        expect(screen.getByText("Atlas Core is unavailable. Try again later.")).toBeVisible();

        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "planning_failed", planning_failure: { code: "persistence_failed", message: "Persistence failed" } }));
        cleanup();
        renderPage();
        expect(await screen.findByText("Planning session could not be saved.")).toBeVisible();
        expect(screen.getByText("Atlas Agent could not save the planning session. Reload before trying again.")).toBeVisible();

        mockedGetCandidatePlanningSession.mockRejectedValueOnce(new Error("Agent unavailable"));
        cleanup();
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("Agent unavailable");
    });

    it("creates a workflow shell from a plan-ready session", async () => {
        const user = userEvent.setup();
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: plan() }));
        renderPage();

        await user.click(await screen.findByRole("button", { name: "Create Workflow" }));

        await waitFor(() => expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledWith("candidate-plan-1"));
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledTimes(1);
        expect(await screen.findByText("Workflow available for review.")).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Workflow result", level: 2 })).toBeVisible();
        expect(screen.queryByRole("heading", { name: "Create a workflow" })).not.toBeInTheDocument();
        expect(screen.getByText("Workflow ID")).toBeInTheDocument();
        expect(screen.getByText("workflow-1")).not.toBeVisible();
        const details = screen.getByText("Workflow details", { exact: true });
        expect(details.closest("details")).not.toHaveAttribute("open");
        expect(screen.getByRole("link", { name: "Review workflow" })).toBeVisible();
        await user.click(details);
        expect(screen.getByText("workflow-1")).toBeVisible();
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledTimes(1);
        expect(screen.getByText("Approval Pending")).toBeInTheDocument();
        expect(screen.getByText("Implementation approval pending")).toBeInTheDocument();
        expect(screen.getByText("Yes")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Review workflow" })).toHaveAttribute("href", "/candidate-planning/candidate-plan-1/workflow");
        expect(screen.getByText("Workflow").closest("li")).toHaveAttribute("aria-current", "step");
        expect(screen.queryByRole("button", { name: /approve|execute|implementation|commit/i })).not.toBeInTheDocument();
    });

    it("blocks duplicate Create Workflow submissions", async () => {
        const user = userEvent.setup();
        let resolveRequest!: (value: CandidateWorkflowResponse) => void;
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: plan() }));
        mockedCreateCandidateWorkflowShell.mockReturnValue(new Promise((resolve) => {
            resolveRequest = resolve;
        }));
        renderPage();

        const button = await screen.findByRole("button", { name: "Create Workflow" });
        await user.dblClick(button);

        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledTimes(1);
        expect(screen.getAllByText("Creating workflow...").length).toBeGreaterThan(0);
        expect(screen.getByRole("button", { name: "Refresh planning" })).toBeDisabled();
        resolveRequest(workflow());
        expect(await screen.findByText("Workflow available for review.")).toBeInTheDocument();
    });

    it("handles workflow creation errors and rejected conversion states", async () => {
        const user = userEvent.setup();
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: plan() }));
        mockedCreateCandidateWorkflowShell.mockResolvedValueOnce(workflow({
            workflow_session_id: null,
            workflow_status: null,
            conversion_status: "workflow_exists",
            implementation_approval_request_id: null,
            failure: { code: "conflicting_active_session", message: "Workflow already exists" },
        }));
        renderPage();

        await user.click(await screen.findByRole("button", { name: "Create Workflow" }));
        expect(await screen.findByText("Workflow already exists.")).toBeVisible();
        expect(screen.getByText("Failure: conflicting_active_session - Workflow already exists")).toBeVisible();

        mockedCreateCandidateWorkflowShell.mockResolvedValueOnce(workflow({ conversion_status: "workflow_exists" }));
        cleanup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Create Workflow" }));
        expect(await screen.findByText("Workflow already exists.")).toBeVisible();
        expect(screen.getByRole("link", { name: "Review workflow" })).toBeVisible();
        expect(screen.queryByText("Workflow available for review.")).not.toBeInTheDocument();

        mockedCreateCandidateWorkflowShell.mockRejectedValueOnce(new Error("Agent unavailable"));
        cleanup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Create Workflow" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("Agent unavailable");
    });

    it("shows generation errors without creating workflow controls", async () => {
        const user = userEvent.setup();
        mockedGenerateCandidatePlan.mockRejectedValueOnce(new Error("Generation failed"));
        renderPage();

        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Generation failed");
        expect(screen.queryByRole("button", { name: /create workflow|approve|execute|implementation|commit/i })).not.toBeInTheDocument();
    });
    it("clears an older session while a different session is loading", async () => {
        let resolveNext!: (value: CandidatePlanningResponse) => void;
        mockedGetCandidatePlanningSession.mockImplementation((id) => id === "candidate-plan-1"
            ? Promise.resolve(session()) : new Promise((resolve) => { resolveNext = resolve; }));
        const router = createMemoryRouter([{ path: "/candidate-planning/:sessionId", element: <PlanningSessionPage /> }], { initialEntries: ["/candidate-planning/candidate-plan-1"] });
        render(<RouterProvider router={router} />);
        await screen.findByText("candidate-plan-1", { exact: true });
        await act(() => router.navigate("/candidate-planning/candidate-plan-2"));
        expect(screen.queryByText("candidate-plan-1", { exact: true })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        resolveNext(session({ session_id: "candidate-plan-2" }));
        expect(await screen.findByText("candidate-plan-2", { exact: true })).toBeInTheDocument();
    });

    it("does not attach a late generated plan to the next session", async () => {
        const user = userEvent.setup();
        let resolvePlan!: (value: CandidatePlanningResponse) => void;
        mockedGetCandidatePlanningSession.mockImplementation(async (id) => session({ session_id: id }));
        mockedGenerateCandidatePlan.mockImplementationOnce(() => new Promise((resolve) => { resolvePlan = resolve; }));
        const router = createMemoryRouter([{ path: "/candidate-planning/:sessionId", element: <PlanningSessionPage /> }], { initialEntries: ["/candidate-planning/candidate-plan-1"] });
        render(<RouterProvider router={router} />);
        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));
        await act(() => router.navigate("/candidate-planning/candidate-plan-2"));
        await screen.findByText("candidate-plan-2", { exact: true });
        await act(async () => resolvePlan(session({ status: "plan_ready", plan: plan() })));
        expect(screen.queryByText("Update Home Assistant compose stack")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Generate Plan" })).toBeEnabled();
    });

    it("rejects a planning session returned for a different URL identity", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ session_id: "other-session" }));
        renderPage();
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
    });

    it("does not show a ready plan belonging to another session", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: plan({ session_id: "other-session" }) }));
        renderPage();
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByText("Update Home Assistant compose stack")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
    });

    it("rejects a generated result for a different session", async () => {
        const user = userEvent.setup();
        mockedGenerateCandidatePlan.mockResolvedValue(session({ session_id: "other-session", status: "plan_ready", plan: plan({ session_id: "other-session" }) }));
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByText("Update Home Assistant compose stack")).not.toBeInTheDocument();
    });

    it("does not open a workflow result from another planning session", async () => {
        const user = userEvent.setup();
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: plan() }));
        mockedCreateCandidateWorkflowShell.mockResolvedValue(workflow({ candidate_planning_session_id: "other-session" }));
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Create Workflow" }));
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByRole("link", { name: "Review workflow" })).not.toBeInTheDocument();
    });

    it("does not offer generation when planning is explicitly disallowed", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ planning_allowed: false }));
        renderPage();
        await screen.findByText("candidate-plan-1", { exact: true });
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
    });

    it("keeps a saved plan read-only when planning is disallowed", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ planning_allowed: false, status: "plan_ready", plan: plan() }));
        renderPage();
        await screen.findByText("Update Home Assistant compose stack");
        expect(screen.getByRole("heading", { name: "Review saved plan", level: 1 })).toBeVisible();
        expect(screen.getByRole("heading", { name: "Workflow creation unavailable", level: 2 })).toBeVisible();
        expect(screen.getByText("Creating a workflow is not available for this session. You can review this plan and refresh planning to check the latest status.")).toBeVisible();
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it("shows recovery instead of an empty ready screen when a saved plan is missing", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready" }));
        mockedGetCandidatePlan.mockResolvedValue(null);
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("The saved plan could not be loaded");
        expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
    });

    it("does not repeat generation when the server reports ready but its plan read fails", async () => {
        const user = userEvent.setup();
        mockedGenerateCandidatePlan.mockResolvedValue(session({ status: "plan_ready" }));
        mockedGetCandidatePlan.mockRejectedValue(new Error("read unavailable"));
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));
        await screen.findByRole("alert");
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Check saved planning" })).toBeInTheDocument();
        expect(mockedGenerateCandidatePlan).toHaveBeenCalledTimes(1);
    });

});
