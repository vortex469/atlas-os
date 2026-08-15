import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getWorkflowOperationalLifecycle,
    listWorkflows,
} from "../api/atlas-agent";
import { operationalLifecycle } from "../test/operationalLifecycle";
import { OperationalHistoryPage } from "./OperationalHistoryPage";

vi.mock("../api/atlas-agent", () => ({
    getWorkflowOperationalLifecycle: vi.fn(),
    listWorkflows: vi.fn(),
}));

const mockedLifecycle = vi.mocked(getWorkflowOperationalLifecycle);
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
    });

    it("loads bounded operational workflows and links to lifecycle detail", async () => {
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);

        expect(await screen.findByText("proxmox/qemu/110")).toBeInTheDocument();
        expect(mockedList).toHaveBeenCalledWith({ effect_kind: "operational_action", limit: 10, offset: 0 });
        expect(screen.getByRole("link", { name: "Open lifecycle" })).toHaveAttribute("href", "/workflows/workflow-operational-1");
        expect(screen.queryByRole("button", { name: /retry|run again/i })).not.toBeInTheDocument();
    });

    it("does not expose lifecycle-native material in history rows", async () => {
        render(<MemoryRouter><OperationalHistoryPage /></MemoryRouter>);

        await screen.findByText("proxmox/qemu/110");
        expect(document.body.textContent).not.toMatch(/vmgenid|Authorization|Bearer|CSRF|cookie/i);
    });
});
