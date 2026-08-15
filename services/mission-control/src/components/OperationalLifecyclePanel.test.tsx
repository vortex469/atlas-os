import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { operationalLifecycle } from "../test/operationalLifecycle";
import { OperationalLifecyclePanel } from "./OperationalLifecyclePanel";

function renderLifecycle(overrides = {}) {
    render(<OperationalLifecyclePanel lifecycle={operationalLifecycle(overrides)} isLoading={false} isRefreshing={false} error={null} onRefresh={vi.fn()} />);
}

describe("OperationalLifecyclePanel", () => {
    it("renders verified identity, approvals, exactly-once, and verification evidence", () => {
        renderLifecycle();

        expect(screen.getByRole("heading", { name: "Verified" })).toBeInTheDocument();
        expect(screen.getByText("proxmox/qemu/110")).toBeInTheDocument();
        expect(screen.getByText(/one dispatch barrier crossing and no replay/i)).toBeInTheDocument();
        expect(screen.getByText("UPID:sanitized")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /retry|run again/i })).not.toBeInTheDocument();
    });

    it.each([
        [{ agent_execution_stage: "verification_pending", core_record_state: "verifying", verification_status: null, terminal: false }, "Verification pending"],
        [{ controlled_reason: "verification_failed", verification_status: "verification_failed" }, "Verification failed"],
        [{ controlled_reason: "target_replaced", verification_status: "target_replaced" }, "Target replaced"],
        [{ controlled_reason: "outcome_unknown", verification_status: "outcome_unknown" }, "Outcome unknown"],
        [{ agent_execution_stage: "submission_outcome_unknown", terminal: false }, "Submission outcome unknown"],
        [{ availability: "unavailable", consistency_status: "core_unavailable", terminal: false }, "Core lifecycle unavailable"],
        [{ availability: "agent_only", consistency_status: "agent_only", core_record_state: null, terminal: false }, "Agent-only lifecycle"],
        [{ consistency_status: "mismatch" }, "Immutable lifecycle mismatch"],
    ] as const)("renders controlled outcome %#", (overrides, heading) => {
        renderLifecycle(overrides);

        expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /retry|run again/i })).not.toBeInTheDocument();
    });

    it("renders a sanitized controlled network error", () => {
        render(<OperationalLifecyclePanel lifecycle={null} isLoading={false} isRefreshing={false} error="Mission Control could not read the operational lifecycle." onRefresh={vi.fn()} />);

        expect(screen.getByRole("alert")).toHaveTextContent("A network failure is not an operational failure");
        expect(document.body.textContent).not.toMatch(/Authorization|Bearer|vmgenid|CSRF|cookie|command|environment/i);
    });
});
