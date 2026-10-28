import { StrictMode } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
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

describe("OperationalHistoryPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedList.mockResolvedValue({
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
        });
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

    it("loads bounded operational workflows and links to lifecycle detail", async () => {
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);

        expect(await screen.findByRole("heading", { name: "Virtual machine 110" })).toBeVisible();
        expect(screen.getByText(/^Requested \(local time\):/)).toBeVisible();
        const targetReference = screen.getByText("proxmox/qemu/110");
        expect(targetReference).not.toBeVisible();
        fireEvent.click(screen.getByText("Request details", { exact: true }));
        expect(targetReference).toBeVisible();
        expect(screen.getByText("Result recorded (local time)")).toBeVisible();
        expect(screen.getByText("Request stage", { exact: true })).toBeVisible();
        expect(mockedList).toHaveBeenCalledWith({ effect_kind: "operational_action", limit: 10, offset: 0 });
        expect(mockedDiagnostic).toHaveBeenCalledTimes(1);
        expect(screen.getByRole("link", { name: "Open workflow" })).toHaveAttribute("href", "/workflows/workflow-operational-1");
        expect(screen.queryByRole("button", { name: /retry|run again/i })).not.toBeInTheDocument();
    });

    it("shows diagnostic failure as unavailable rather than operational failure", async () => {
        mockedDiagnostic.mockRejectedValue(new Error("native secret exception"));
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);

        expect(await screen.findByText("A diagnostic network failure is not an operational failure.")).toBeInTheDocument();
        expect(document.body.textContent).not.toContain("native secret exception");
    });

    it("keeps history visible and identifies incomplete details when lifecycle read fails", async () => {
        mockedLifecycle.mockRejectedValue(new Error("private lifecycle exception"));
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);

        expect(await screen.findByRole("heading", { name: "Maintenance target 110" })).toBeVisible();
        expect(screen.getByText("Could not load request details. Target and timing information may be incomplete. Use Refresh history to try again.")).toBeVisible();
        expect(screen.getByText(/Restart service · Healthy/)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Refresh history" })).toBeEnabled();
        expect(document.body.textContent).not.toContain("private lifecycle exception");
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
        expect(await screen.findByRole("heading", { name: "Virtual machine 110" })).toBeVisible();
        expect(screen.getByText(/Restart service · Status unavailable/)).toBeInTheDocument();
        expect(screen.getByText("Could not load the latest status for this request.")).toBeInTheDocument();
    });

    it("keeps a matching diagnostic when lifecycle details belong to another workflow", async () => {
        mockedLifecycle.mockResolvedValue(operationalLifecycle({ workflow_id: "foreign-workflow", target_label: "Foreign target" }));
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        await screen.findByRole("link", { name: "Open workflow" });
        expect(screen.queryByText("Foreign target")).not.toBeInTheDocument();
        expect(screen.getByText(/Restart service · Healthy/)).toBeInTheDocument();
        expect(screen.getByText("Could not load request details. Target and timing information may be incomplete. Use Refresh history to try again.")).toBeVisible();
    });

    it("filters only the bounded current page by controlled diagnostic status", async () => {
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        await screen.findByRole("heading", { name: "Virtual machine 110" });

        expect(screen.getByText("Filters only narrow the requests shown on this page. Use Previous and Next to check other pages.")).toBeVisible();
        const diagnosticFilter = screen.getByRole("combobox", { name: "Latest result" });
        const moreFilters = screen.getByText("More filters", { exact: true });
        expect(moreFilters.closest("details")).not.toHaveAttribute("open");
        expect(screen.queryByRole("combobox", { name: "Requested action" })).not.toBeInTheDocument();
        fireEvent.click(moreFilters);
        const completionFilter = screen.getByRole("combobox", { name: "Completion" });
        expect(screen.queryByRole("combobox", { name: "Requested action" })).not.toBeInTheDocument();
        expect(screen.queryByRole("combobox", { name: "Provider" })).not.toBeInTheDocument();
        expect(screen.queryByRole("combobox", { name: "Resource type" })).not.toBeInTheDocument();
        fireEvent.change(completionFilter, { target: { value: "non_terminal" } });
        expect(screen.getByText("Additional filters are applied")).toBeVisible();
        fireEvent.change(diagnosticFilter, { target: { value: "attention_required" } });
        expect(screen.getByText("No requests on this page match your filters.")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
        expect(screen.getByRole("heading", { name: "Virtual machine 110" })).toBeVisible();
        expect(diagnosticFilter).toHaveValue("all");
        expect(completionFilter).toHaveValue("all");
        expect(mockedList).toHaveBeenCalledTimes(1);
    });

    it("shows an optional filter only when the current page has multiple values", async () => {
        const first = {
            workflow_id: "workflow-operational-1", workflow_source: "candidate" as const,
            workflow_state: "completed" as const, effect_kind: "operational_action" as const,
            execution_intent: "restart-service", candidate_id: "candidate-1", planning_session_id: "planning-1",
            repository: null, target_id: "110", last_result_summary: "verified", timeline: [],
        };
        mockedList.mockResolvedValue({
            items: [first, { ...first, workflow_id: "workflow-operational-2", execution_intent: "start-service" }],
            total: 2, limit: 10, offset: 0,
        });
        mockedLifecycle
            .mockResolvedValueOnce(operationalLifecycle())
            .mockResolvedValueOnce(operationalLifecycle({
                workflow_id: "workflow-operational-2",
                provider_id: "libvirt",
                resource_type: "lxc",
                target_label: "libvirt/lxc/110",
            }));

        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);
        await screen.findByRole("heading", { name: "Virtual machine 110" });
        fireEvent.click(screen.getByText("More filters", { exact: true }));

        const actionFilter = screen.getByRole("combobox", { name: "Requested action" });
        expect(actionFilter).toBeVisible();
        expect(within(actionFilter).getByRole("option", { name: "Restart service" })).toBeInTheDocument();
        expect(within(actionFilter).getByRole("option", { name: "Start Service" })).toBeInTheDocument();
        const providerFilter = screen.getByRole("combobox", { name: "Provider" });
        expect(within(providerFilter).getByRole("option", { name: "Proxmox" })).toBeInTheDocument();
        expect(within(providerFilter).getByRole("option", { name: "Libvirt" })).toBeInTheDocument();
        const resourceTypeFilter = screen.getByRole("combobox", { name: "Resource type" });
        expect(within(resourceTypeFilter).getByRole("option", { name: "Virtual machine" })).toBeInTheDocument();
        expect(within(resourceTypeFilter).getByRole("option", { name: "Container" })).toBeInTheDocument();
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
        expect(await screen.findByRole("heading", { name: "VM 110" })).toBeVisible();
        expect(mockedList).toHaveBeenLastCalledWith({ effect_kind: "operational_action", limit: 10, offset: 0 });
    });

    it("does not expose lifecycle-native material in history rows", async () => {
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);

        await screen.findByRole("heading", { name: "Virtual machine 110" });
        expect(document.body.textContent).not.toMatch(/vmgenid|Authorization|Bearer|CSRF|cookie/i);
    });

    it.each([
        ["awaiting_implementation_approval", "Waiting for maintenance approval"],
        ["executing", "Running"],
        ["completed", "Completed"],
        ["blocked", "Blocked"],
    ])("shows a readable request stage for %s", async (workflow_state, label) => {
        mockedList.mockResolvedValue({
            items: [{ workflow_id: "workflow-operational-1", workflow_source: "candidate", workflow_state,
                effect_kind: "operational_action", execution_intent: "restart-service", candidate_id: "candidate-1",
                planning_session_id: "planning-1", repository: null, target_id: "110", last_result_summary: "verified", timeline: [] }],
            total: 1, limit: 10, offset: 0,
        });
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);

        const details = await screen.findByText("Request details", { exact: true });
        expect(details.closest("details")).not.toHaveAttribute("open");
        fireEvent.click(details);
        const disclosure = details.closest("details") as HTMLElement;
        expect(within(disclosure).getByText("Request stage", { exact: true })).toBeVisible();
        expect(within(disclosure).getByText(label, { exact: true })).toBeVisible();
        expect(within(disclosure).queryByText(workflow_state, { exact: true })).not.toBeInTheDocument();
    });
});

describe("maintenance history recovery", () => {
    it("keeps recovery to one refresh control and separates load failure from maintenance outcome", async () => {
        mockedList.mockRejectedValue(new Error("private diagnostic"));
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Could not load maintenance history.");
        expect(alert).not.toHaveTextContent("Refresh to try again.");
        expect(alert).toHaveTextContent("The maintenance outcome is unknown. Use Refresh history to check again.");
        expect(screen.getByRole("button", { name: "Refresh history" })).toBeEnabled();
        expect(document.body.textContent).not.toContain("private diagnostic");
    });

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
        fireEvent.change(screen.getByRole("combobox", { name: "Latest result" }), { target: { value: "unavailable" } });
        expect(screen.getByRole("link", { name: "Open workflow" })).toHaveAttribute("href", "/workflows/history-unreadable");
        expect(screen.getByText("A diagnostic network failure is not an operational failure.")).toBeInTheDocument();
    });
});
