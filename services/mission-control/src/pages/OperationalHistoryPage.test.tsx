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
        expect(screen.getByRole("link", { name: "Open lifecycle" })).toHaveAttribute("href", "/workflows/workflow-operational-1");
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

        const diagnosticFilter = screen.getByRole("combobox", { name: "Diagnostic" });
        fireEvent.change(diagnosticFilter, { target: { value: "attention_required" } });
        expect(screen.getByText("No workflows on this bounded page match the selected filters.")).toBeInTheDocument();
        expect(mockedList).toHaveBeenCalledTimes(1);
    });

    it("does not expose lifecycle-native material in history rows", async () => {
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);

        await screen.findByText("proxmox/qemu/110");
        expect(document.body.textContent).not.toMatch(/vmgenid|Authorization|Bearer|CSRF|cookie/i);
    });
});
