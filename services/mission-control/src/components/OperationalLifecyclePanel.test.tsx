import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { operationalLifecycle } from "../test/operationalLifecycle";
import { OperationalLifecyclePanel } from "./OperationalLifecyclePanel";

function renderLifecycle(overrides = {}) {
    render(<OperationalLifecyclePanel lifecycle={operationalLifecycle(overrides)} isLoading={false} isRefreshing={false} error={null} onRefresh={vi.fn()} />);
}

describe("OperationalLifecyclePanel", () => {
    it("keeps the maintenance outcome prominent and technical evidence collapsed", () => {
        renderLifecycle();

        expect(screen.getByRole("heading", { name: "Maintenance status" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Verified" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Refresh maintenance status" })).toBeInTheDocument();
        expect(screen.getByText(/Atlas recorded one maintenance run and no replay/i)).toBeInTheDocument();
        const details = screen.getByText("Technical evidence").closest("details") as HTMLDetailsElement;
        expect(details).not.toHaveAttribute("open");
        expect(within(details).getByText("proxmox/qemu/110")).not.toBeVisible();
        fireEvent.click(within(details).getByText("Technical evidence"));
        expect(within(details).getByText("proxmox/qemu/110")).toBeVisible();
        const dispatchStarted = within(details).getByText("Dispatch Started").parentElement?.querySelector("time");
        expect(dispatchStarted).toHaveAttribute("datetime", "2026-08-16T00:02:00Z");
        expect(dispatchStarted).toHaveTextContent("(local time)");
        expect(screen.getByText("UPID:sanitized")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /retry|run again/i })).not.toBeInTheDocument();
    });

    it("marks impossible technical timestamps unavailable", () => {
        renderLifecycle({ dispatch_started_at: "2026-02-30T17:00:00Z" });
        const details = screen.getByText("Technical evidence").closest("details") as HTMLDetailsElement;
        fireEvent.click(within(details).getByText("Technical evidence"));

        const dispatchStarted = within(details).getByText("Dispatch Started").parentElement;
        expect(dispatchStarted).toHaveTextContent("Time unavailable");
        expect(dispatchStarted?.querySelector("time")).toBeNull();
    });

    it.each([
        { provider_operation_captured: false },
        { provider_operation_capture_count: 0 },
        { provider_operation_capture_count: 2 },
        { barrier_crossing_count: 2 },
    ])("does not claim a single recorded maintenance run without matching evidence %#", (overrides) => {
        renderLifecycle(overrides);

        expect(screen.queryByText("Atlas recorded one maintenance run and no replay.")).not.toBeInTheDocument();
    });

    it.each([
        [{ agent_execution_stage: "verification_pending", core_record_state: "verifying", verification_status: null, terminal: false }, "Verification in progress"],
        [{ controlled_reason: "verification_failed", verification_status: "verification_failed" }, "Verification failed"],
        [{ controlled_reason: "target_replaced", verification_status: "target_replaced" }, "Approved target changed"],
        [{ controlled_reason: "outcome_unknown", verification_status: "outcome_unknown" }, "Run result unknown"],
        [{ agent_execution_stage: "submission_outcome_unknown", terminal: false }, "Request result unknown"],
        [{ availability: "unavailable", consistency_status: "core_unavailable", terminal: false }, "Maintenance status unavailable"],
        [{ availability: "agent_only", consistency_status: "agent_only", core_record_state: null, terminal: false }, "Run status not yet recorded"],
        [{ consistency_status: "mismatch" }, "Maintenance records do not match"],
    ] as const)("renders controlled outcome %#", (overrides, heading) => {
        renderLifecycle(overrides);

        expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
        expect(screen.getByText("Do not repeat this request. Check its status first.")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /retry|run again/i })).not.toBeInTheDocument();
    });

    it("offers a read-only retry when lifecycle evidence is unavailable", () => {
        const onRefresh = vi.fn();
        render(<OperationalLifecyclePanel lifecycle={null} isLoading={false} isRefreshing={false} error="Bearer lifecycle-canary-secret" onRefresh={onRefresh} />);

        const alert = screen.getByRole("alert");
        expect(alert).toHaveTextContent("Maintenance status unavailable");
        expect(alert).toHaveTextContent("the result may still be unknown");
        expect(alert).toHaveTextContent("Checking status again does not repeat the maintenance action.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("[Sensitive text withheld]")).not.toBeVisible();
        expect(within(alert).queryByText(/lifecycle-canary-secret/)).not.toBeInTheDocument();
        fireEvent.click(within(alert).getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("[Sensitive text withheld]")).toBeVisible();
        fireEvent.click(screen.getByRole("button", { name: "Check status again" }));
        expect(onRefresh).toHaveBeenCalledOnce();
        expect(document.body.textContent).not.toMatch(/Authorization|Bearer|vmgenid|CSRF|cookie|command|environment/i);
    });
});
