import { StrictMode } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getWorkflowOperationalLifecycle,
    getWorkflowRecoveryDiagnostic,
    listWorkflows,
} from "../api/atlas-agent";
import { operationalLifecycle } from "../test/operationalLifecycle";
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

        expect(await screen.findByText("proxmox/qemu/110")).toBeInTheDocument();
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
        expect(screen.getByText("A diagnostic network failure is not an operational failure.")).toBeInTheDocument();
    });
});
