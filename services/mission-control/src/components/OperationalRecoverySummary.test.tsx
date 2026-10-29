import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { WorkflowRecoveryDiagnostic } from "../types/atlasAgent";
import { operationalDiagnostic as diagnostic } from "../test/operationalLifecycle";
import { OperationalRecoverySummary } from "./OperationalRecoverySummary";


describe("OperationalRecoverySummary", () => {
    it.each([
        [{ diagnostic_status: "healthy" }, "Healthy"],
        [{ diagnostic_status: "pending", controlled_reason: "verification_pending", safe_next_action: "wait_for_verification" }, "Pending"],
        [{ diagnostic_status: "recovery_in_progress", controlled_reason: "verification_pending", safe_next_action: "wait_for_verification" }, "Recovery in progress"],
        [{ diagnostic_status: "attention_required", controlled_reason: "verification_failed", safe_next_action: "inspect_target_read_only" }, "Attention required"],
        [{ diagnostic_status: "outcome_uncertain", controlled_reason: "dispatch_outcome_unknown", safe_next_action: "preserve_evidence" }, "Outcome uncertain"],
        [{ diagnostic_status: "unavailable", consistency: "core_unavailable", controlled_reason: "core_unavailable", safe_next_action: "restore_core_availability" }, "Diagnostic unavailable"],
        [{ diagnostic_status: "attention_required", controlled_reason: "target_replaced", safe_next_action: "new_request_only_after_terminal", verification_evidence: { ...diagnostic().verification_evidence, target_fingerprint_state: "replaced" } }, "Attention required"],
        [{ diagnostic_status: "attention_required", consistency: "immutable_mismatch", controlled_reason: "immutable_request_mismatch", safe_next_action: "operator_review_required" }, "Attention required"],
        [{ diagnostic_status: "attention_required", consistency: "transition_mismatch", controlled_reason: "invalid_transition_sequence", safe_next_action: "preserve_evidence" }, "Attention required"],
        [{ diagnostic_status: "attention_required", consistency: "terminal_mismatch", controlled_reason: "terminal_state_disagreement", safe_next_action: "operator_review_required" }, "Attention required"],
    ] as Array<[Partial<WorkflowRecoveryDiagnostic>, string]>)("renders controlled diagnostic %# distinctly", (overrides, heading) => {
        render(<OperationalRecoverySummary diagnostic={diagnostic(overrides)} supportEvidenceAvailable />);

        expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
        expect(screen.getByText(/Safe next action:/)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /retry|run again|reconcile|execute/i })).not.toBeInTheDocument();
    });

    it.each([
        ["none", "No further action is needed."],
        ["wait_for_verification", "Wait for Atlas to finish checking the service. Do not run the request again."],
        ["restore_core_availability", "Restore Atlas Core, then refresh this page."],
        ["inspect_target_read_only", "Check the current service status without changing it."],
        ["preserve_evidence", "Keep the current request details. Ask an operator to review them before making changes."],
        ["operator_review_required", "Ask an operator to review this before creating a new maintenance request."],
        ["new_request_only_after_terminal", "Wait for this request to finish before creating another one."],
    ] as Array<[WorkflowRecoveryDiagnostic["safe_next_action"], string]>)("maps safe action %s", (safe_next_action, expected) => {
        render(<OperationalRecoverySummary diagnostic={diagnostic({ safe_next_action })} supportEvidenceAvailable={false} />);
        expect(screen.getByText((content) => content.includes(expected))).toBeInTheDocument();
    });

    it.each([
        ["missing_core_record", "The request is recorded, but no matching service run was found."],
        ["dispatch_outcome_unknown", "The request was sent, but the service result is unknown."],
        ["terminal_state_disagreement", "Atlas has conflicting records about whether the request is finished."],
    ] as const)("explains %s in plain language", (controlled_reason, reason) => {
        render(<OperationalRecoverySummary diagnostic={diagnostic({ controlled_reason })} supportEvidenceAvailable={false} />);
        expect(screen.getByText(reason)).toBeInTheDocument();
    });

    it("keeps an unknown reported reason readable", () => {
        render(<OperationalRecoverySummary diagnostic={diagnostic({ controlled_reason: "future_reason" as never })} supportEvidenceAvailable={false} />);
        expect(screen.getByText("Mission Control could not interpret the reported reason.")).toBeVisible();
    });

    it("does not omit an unknown next step", () => {
        render(<OperationalRecoverySummary diagnostic={diagnostic({ safe_next_action: "future_action" as never })} supportEvidenceAvailable={false} />);
        expect(screen.getByText("Next step unavailable. Ask an operator to review before acting.")).toBeVisible();
    });

    it("keeps technical evidence closed until an operator asks to see it", () => {
        render(<OperationalRecoverySummary diagnostic={diagnostic()} supportEvidenceAvailable />);

        const summary = screen.getByRole("region", { name: "Maintenance status summary" });
        const evidence = within(summary).getByText("Diagnostic evidence").closest("details");
        expect(evidence).not.toHaveAttribute("open");
        expect(within(summary).getByText("Target fingerprint")).not.toBeVisible();
        expect(within(summary).getByText("Healthy")).toBeVisible();
        expect(within(summary).getByText(/Safe next action:/)).toBeVisible();

        fireEvent.click(within(summary).getByText("Diagnostic evidence"));

        expect(within(summary).getByText("Target fingerprint")).toBeVisible();
        expect(within(summary).getByText("unchanged")).toBeVisible();
    });

    it("keeps the compact history summary focused on status and next steps", () => {
        render(<OperationalRecoverySummary diagnostic={diagnostic()} supportEvidenceAvailable compact />);

        expect(screen.getByRole("region", { name: "Maintenance status summary" })).toBeInTheDocument();
        expect(screen.getByText("Healthy")).toBeVisible();
        expect(screen.getByText(/Safe next action:/)).toBeVisible();
        expect(screen.queryByText("Diagnostic evidence")).not.toBeInTheDocument();
        expect(screen.queryByText("Target fingerprint")).not.toBeInTheDocument();
    });

    it("keeps a status read failure distinct from the maintenance outcome", () => {
        render(<OperationalRecoverySummary diagnostic={null} error="Mission Control could not check the latest recovery status." supportEvidenceAvailable={false} />);
        expect(screen.getByRole("heading", { name: "Maintenance status details unavailable" })).toBeInTheDocument();
        expect(screen.getByText("A problem checking status does not mean the maintenance request failed.")).toBeInTheDocument();
    });

    it("renders no forbidden secret or provider-native fields", () => {
        render(<OperationalRecoverySummary diagnostic={diagnostic()} supportEvidenceAvailable />);
        expect(document.body.textContent).not.toMatch(/Authorization|Bearer|cookie|CSRF|vmgenid|identity token|native payload|command|environment/i);
    });
});
