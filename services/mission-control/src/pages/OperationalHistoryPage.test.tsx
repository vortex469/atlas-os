import { StrictMode } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getWorkflowOperationalLifecycle,
    getWorkflowRecoveryDiagnostic,
    listWorkflows,
} from "../api/atlas-agent";
import { operationalDiagnostic, operationalLifecycle } from "../test/operationalLifecycle";
import { OperationalHistoryPage } from "./OperationalHistoryPage";

vi.mock("../api/atlas-agent", () => ({
    getWorkflowOperationalLifecycle: vi.fn(),
    getWorkflowRecoveryDiagnostic: vi.fn(),
    listWorkflows: vi.fn(),
}));

const mockedLifecycle = vi.mocked(getWorkflowOperationalLifecycle);
const mockedDiagnostic = vi.mocked(getWorkflowRecoveryDiagnostic);
const mockedList = vi.mocked(listWorkflows);

function historyPage(): Awaited<ReturnType<typeof listWorkflows>> {
    return {
            items: [{
                workflow_id: "workflow-operational-1",
                workflow_source: "candidate",
                workflow_state: "completed",
                effect_kind: "operational_action",
                execution_intent: "restart-service",
                candidate_id: "candidate-1",
                planning_session_id: "planning-1",
                repository: null,
                target_id: "110",
                last_result_summary: "verified",
                timeline: [],
            }],
            total: 1,
            limit: 10,
            offset: 0,
        };
}

describe("OperationalHistoryPage", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        mockedList.mockResolvedValue(historyPage());
        mockedLifecycle.mockResolvedValue(operationalLifecycle());
        mockedDiagnostic.mockResolvedValue({
            applicable: true,
            diagnostic_status: "healthy",
            consistency: "consistent",
            correlation: { workflow_id: "workflow-operational-1", request_id: "request-1", request_digest_match: true, agent_record_present: true, core_record_present: true },
            dispatch_evidence: { barrier_crossed: true, provider_operation_captured: true, dispatch_result_known: true, transition_sequence_valid: true },
            verification_evidence: { status: "succeeded", target_fingerprint_state: "unchanged", observed_state: "running", observed_health: "running", terminal_evidence: true },
            controlled_reason: null,
            safe_next_action: "none",
        });
    });

    it.each(["2026-02-30T00:00:00Z", "2026-08-16T00:00:00", "2026-08-16", "2099-01-01T00:00:00Z"])("keeps unconfirmed history time %s unknown", async (timestamp) => {
        mockedLifecycle.mockResolvedValue(operationalLifecycle({ request_created_at: timestamp, verification_completed_at: timestamp }));
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        expect(await screen.findByText("Requested: Unknown time")).toBeVisible();
        fireEvent.click(screen.getByText("Workflow details", { exact: true }));
        expect(screen.getByText("Result recorded", { exact: true }).parentElement).toHaveTextContent("Unknown time");
        expect(mockedList).toHaveBeenCalledTimes(1);
    });

    it.each(["2024-02-29T12:00:00.123456Z", "2026-08-16T14:00:00+02:00"])("preserves valid timezone-aware history time %s", async (timestamp) => {
        mockedLifecycle.mockResolvedValue(operationalLifecycle({ request_created_at: timestamp, verification_completed_at: timestamp }));
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        const formatted = new Date(timestamp).toLocaleString();
        expect(await screen.findByText(`Requested: ${formatted}`)).toBeVisible();
        fireEvent.click(screen.getByText("Workflow details", { exact: true }));
        expect(screen.getByText("Result recorded", { exact: true }).parentElement).toHaveTextContent(formatted);
    });

    it("retains qualified records through pending, failed and retried refreshes", async () => {
        const page = historyPage();
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        await screen.findByRole("heading", { name: "Healthy" });
        let fail!: (error: Error) => void;
        mockedList.mockImplementationOnce(() => new Promise((_, reject) => { fail = reject; }));
        fireEvent.click(screen.getByRole("button", { name: "Refresh history" }));
        expect(screen.getByText("proxmox/qemu/110")).toBeVisible();
        expect(screen.getByRole("heading", { name: "Last loaded: Healthy" })).toBeVisible();
        expect(screen.queryByRole("heading", { name: "Healthy" })).not.toBeInTheDocument();
        expect(screen.getByText(/Current status and guidance have not been confirmed/)).toBeVisible();
        await act(async () => fail(new Error("unavailable")));
        expect(await screen.findByRole("alert")).toBeVisible();
        expect(screen.getByText("proxmox/qemu/110")).toBeVisible();
        let finish!: (value: Awaited<ReturnType<typeof listWorkflows>>) => void;
        mockedList.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
        fireEvent.click(screen.getByRole("button", { name: "Refresh history" }));
        expect(screen.getByRole("heading", { name: "Last loaded: Healthy" })).toBeVisible();
        await act(async () => finish(page));
        expect(await screen.findByRole("heading", { name: "Healthy" })).toBeVisible();
        expect(screen.queryByText(/Current status and guidance have not been confirmed/)).not.toBeInTheDocument();
        expect(mockedList).toHaveBeenCalledTimes(3);
    });

    it("retains the displayed page and retries a failed Next without skipping a page", async () => {
        const page = historyPage();
        const item = page.items[0];
        mockedList.mockReset()
            .mockResolvedValueOnce({ ...page, items: Array.from({ length: 10 }, (_, index) => ({ ...item, workflow_id: `old-${index}`, target_id: `Previous target ${index}` })), total: 11 })
            .mockRejectedValueOnce(new Error("unavailable"))
            .mockResolvedValueOnce({ ...page, items: [{ ...item, workflow_id: "new-page", target_id: "New page target" }], total: 11, offset: 10 });
        mockedLifecycle.mockResolvedValue(null);
        mockedDiagnostic.mockResolvedValue(null);
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        fireEvent.click(await screen.findByRole("button", { name: "Next" }));
        await screen.findByRole("alert");
        expect(screen.getByText("Previous target 0")).toBeVisible();
        expect(screen.getByText("Last loaded: Showing 1–10 of 11")).toBeVisible();
        fireEvent.click(screen.getByRole("button", { name: "Next" }));
        expect(await screen.findByText("New page target")).toBeVisible();
        expect(screen.getByText("Showing 11–11 of 11")).toBeVisible();
        expect(mockedList.mock.calls.map(([query]) => query?.offset)).toEqual([0, 10, 10]);
    });

    it("qualifies a retained empty page instead of claiming current emptiness", async () => {
        mockedList.mockResolvedValueOnce({ items: [], total: 0, limit: 10, offset: 0 }).mockRejectedValueOnce(new Error("unavailable"));
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        await screen.findByText("No maintenance requests yet.");
        fireEvent.click(screen.getByRole("button", { name: "Refresh history" }));
        await screen.findByRole("alert");
        expect(screen.getByText("No requests in the last loaded page. Current results have not been confirmed.")).toBeVisible();
        expect(screen.queryByText("No maintenance requests yet.")).not.toBeInTheDocument();
    });

    it("keeps missing reports in the unavailable filter without claiming a network failure", async () => {
        mockedDiagnostic.mockResolvedValue(null);
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        expect(await screen.findByText(/Restart service · Status unavailable/)).toBeInTheDocument();
        fireEvent.change(screen.getByRole("combobox", { name: "Status" }), { target: { value: "unavailable" } });
        expect(screen.getByRole("link", { name: "Open workflow" })).toBeInTheDocument();
        expect(screen.queryByText("An unavailable report does not mean maintenance failed.")).not.toBeInTheDocument();
        expect(mockedList).toHaveBeenCalledTimes(1);
        expect(mockedDiagnostic).toHaveBeenCalledTimes(1);
    });

    it("does not classify missing completion evidence as in progress or finished", async () => {
        mockedLifecycle.mockResolvedValue(null);
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        await screen.findByRole("link", { name: "Open workflow" });
        for (const value of ["non_terminal", "terminal"]) {
            fireEvent.change(screen.getByRole("combobox", { name: "Completion" }), { target: { value } });
            expect(screen.getByText("No requests on this page match your filters.")).toBeInTheDocument();
        }
        fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
        expect(screen.getByRole("link", { name: "Open workflow" })).toBeInTheDocument();
        expect(mockedLifecycle).toHaveBeenCalledTimes(1);
    });

    it("loads bounded operational workflows and links to lifecycle detail", async () => {
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);

        expect(await screen.findByText("proxmox/qemu/110")).toBeInTheDocument();
        expect(mockedList).toHaveBeenCalledWith({ effect_kind: "operational_action", limit: 10, offset: 0 });
        expect(mockedDiagnostic).toHaveBeenCalledTimes(1);
        expect(screen.getByRole("link", { name: "Open workflow" })).toHaveAttribute("href", "/workflows/workflow-operational-1");
        expect(screen.queryByRole("button", { name: /retry|run again/i })).not.toBeInTheDocument();
    });

    it("shows diagnostic failure as unavailable rather than operational failure", async () => {
        mockedDiagnostic.mockRejectedValue(new Error("native secret exception"));
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);

        expect(await screen.findByText("An unavailable report does not mean maintenance failed.")).toBeInTheDocument();
        expect(document.body.textContent).not.toContain("native secret exception");
    });

    it("does not show another workflow's target or successful outcome", async () => {
        mockedLifecycle.mockResolvedValue(operationalLifecycle({ workflow_id: "foreign-workflow", target_label: "Foreign target" }));
        mockedDiagnostic.mockResolvedValue(operationalDiagnostic({ correlation: { workflow_id: "foreign-workflow", request_id: "request-1", request_digest_match: true, agent_record_present: true, core_record_present: true } }));
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);

        expect(await screen.findByText(/Restart service · Status unavailable/)).toBeInTheDocument();
        expect(screen.queryByText("Foreign target")).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Healthy" })).not.toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Open workflow" })).toHaveAttribute("href", "/workflows/workflow-operational-1");
    });

    it("keeps matching lifecycle details when a diagnostic belongs to another workflow", async () => {
        mockedDiagnostic.mockResolvedValue(operationalDiagnostic());
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        expect(await screen.findByText("proxmox/qemu/110")).toBeInTheDocument();
        expect(screen.getByText(/Restart service · Status unavailable/)).toBeInTheDocument();
        expect(screen.getByText("Could not load the latest status for this request.")).toBeInTheDocument();
    });

    it("keeps a matching diagnostic when lifecycle details belong to another workflow", async () => {
        mockedLifecycle.mockResolvedValue(operationalLifecycle({ workflow_id: "foreign-workflow", target_label: "Foreign target" }));
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        await screen.findByRole("link", { name: "Open workflow" });
        expect(screen.queryByText("Foreign target")).not.toBeInTheDocument();
        expect(screen.getByText(/Restart service · Healthy/)).toBeInTheDocument();
    });

    it("filters only the bounded current page by controlled diagnostic status", async () => {
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        await screen.findByText("proxmox/qemu/110");

        const diagnosticFilter = screen.getByRole("combobox", { name: "Status" });
        fireEvent.change(diagnosticFilter, { target: { value: "attention_required" } });
        expect(screen.getByText("No requests on this page match your filters.")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
        expect(screen.getByText("proxmox/qemu/110")).toBeInTheDocument();
        expect(diagnosticFilter).toHaveValue("all");
        expect(mockedList).toHaveBeenCalledTimes(1);
    });

    it("keeps Previous available when a later page becomes empty", async () => {
        const item = {
            workflow_id: "page-item", workflow_source: "candidate" as const,
            workflow_state: "completed" as const, effect_kind: "operational_action" as const,
            execution_intent: "restart-service", candidate_id: null, planning_session_id: null,
            repository: null, target_id: "VM 110", last_result_summary: "", timeline: [],
        };
        mockedList.mockReset()
            .mockResolvedValueOnce({ items: Array.from({ length: 10 }, (_, index) => ({ ...item, workflow_id: `page-${index}` })), total: 11, limit: 10, offset: 0 })
            .mockResolvedValueOnce({ items: [], total: 1, limit: 10, offset: 10 })
            .mockResolvedValueOnce({ items: [item], total: 1, limit: 10, offset: 0 });
        mockedLifecycle.mockRejectedValue(new Error("unavailable"));
        mockedDiagnostic.mockRejectedValue(new Error("unavailable"));
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        fireEvent.click(await screen.findByRole("button", { name: "Next" }));
        await screen.findByText("No requests on this page. Go back to an earlier page.");
        const previous = screen.getByRole("button", { name: "Previous" });
        expect(previous).toBeEnabled();
        expect(screen.getByText("1 request total")).toBeInTheDocument();
        fireEvent.click(previous);
        expect(await screen.findByText("VM 110")).toBeInTheDocument();
        expect(mockedList).toHaveBeenLastCalledWith({ effect_kind: "operational_action", limit: 10, offset: 0 });
    });

    it("does not expose lifecycle-native material in history rows", async () => {
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);

        await screen.findByText("proxmox/qemu/110");
        expect(document.body.textContent).not.toMatch(/vmgenid|Authorization|Bearer|CSRF|cookie/i);
    });
});

describe("maintenance history recovery", () => {
    it("loads once during Strict Mode initialization", async () => {
        vi.clearAllMocks();
        mockedList.mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });
        render(<StrictMode><MemoryRouter><OperationalHistoryPage /></MemoryRouter></StrictMode>);
        expect(await screen.findByText("No maintenance requests yet.")).toBeInTheDocument();
        expect(mockedList).toHaveBeenCalledTimes(1);
    });

    it("keeps unreadable diagnostics visible when filtering for unavailable status", async () => {
        mockedList.mockResolvedValue({
            items: [{ workflow_id: "history-unreadable", workflow_source: "candidate",
                workflow_state: "completed", effect_kind: "operational_action",
                execution_intent: "restart-service", candidate_id: null,
                planning_session_id: null, repository: null, target_id: "unreadable-target",
                last_result_summary: "", timeline: [] }],
            total: 1, limit: 10, offset: 0,
        });
        mockedLifecycle.mockResolvedValue(operationalLifecycle({ target_label: "unreadable-target" }));
        mockedDiagnostic.mockRejectedValue(new Error("not available"));
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        await screen.findByText("unreadable-target");
        fireEvent.change(screen.getByRole("combobox", { name: "Status" }), { target: { value: "unavailable" } });
        expect(screen.getByRole("link", { name: "Open workflow" })).toHaveAttribute("href", "/workflows/history-unreadable");
        expect(screen.getByText("An unavailable report does not mean maintenance failed.")).toBeInTheDocument();
    });
});
