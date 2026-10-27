import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { WorkflowRecoveryDiagnostic } from "../types/atlasAgent";
import { operationalDiagnostic as diagnostic } from "../test/operationalLifecycle";
import { OperationalRecoverySummary } from "./OperationalRecoverySummary";


describe("OperationalRecoverySummary", () => {
    it.each(["healthy", "attention_required"])("qualifies retained %s status and guidance", (diagnosticStatus) => {
        render(<OperationalRecoverySummary diagnostic={diagnostic({ diagnostic_status: diagnosticStatus as WorkflowRecoveryDiagnostic["diagnostic_status"] })} supportEvidenceAvailable compact retained />);
        const title = diagnosticStatus === "healthy" ? "Healthy" : "Attention required";
        expect(screen.getByRole("heading", { name: `Last loaded: ${title}` })).toBeVisible();
        expect(screen.queryByRole("heading", { name: title })).not.toBeInTheDocument();
        expect(screen.getByText(/Current status and guidance have not been confirmed/)).toBeVisible();
        expect(screen.getByText("Last loaded guidance:", { exact: true })).toBeVisible();
        expect(screen.queryByText("Safe next action:", { exact: true })).not.toBeInTheDocument();
        expect(screen.getByRole("region", { name: "Recovery summary" })).toHaveClass("bg-slate-800/60");
    });

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
        const report = diagnostic(overrides);
        const { rerender } = render(<OperationalRecoverySummary diagnostic={report} supportEvidenceAvailable />);

        expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
        expect(screen.getByText(/Safe next action:/)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /retry|run again|reconcile|execute/i })).not.toBeInTheDocument();
        expect(screen.getByText(/Read-only guidance only/)).toBeVisible();
        if (report.controlled_reason === null) expect(screen.getByText("No recovery reason was reported.", { exact: true })).toBeVisible();
        rerender(<OperationalRecoverySummary diagnostic={report} supportEvidenceAvailable compact />);
        expect(screen.getByRole("heading", { name: heading })).toBeVisible();
        expect(screen.getByText(/Safe next action:/)).toBeVisible();
        expect(screen.queryByText(/Read-only guidance only/)).not.toBeInTheDocument();
        if (report.consistency === "consistent") expect(screen.queryByText("consistent", { exact: true })).not.toBeInTheDocument();
        else expect(screen.getByText(report.consistency.replaceAll("_", " "), { exact: true })).toBeVisible();
        if (report.controlled_reason === null) {
            if (report.diagnostic_status === "healthy") expect(screen.queryByText("No recovery reason was reported.", { exact: true })).not.toBeInTheDocument();
            else expect(screen.getByText("No recovery reason was reported.", { exact: true })).toBeVisible();
        }
    });

    it.each([
        ["none", "No recovery action is required."],
        ["wait_for_verification", "Wait for Atlas verification to complete; do not replay the operation."],
        ["restore_core_availability", "Restore Atlas Core availability and refresh the read-only lifecycle."],
        ["inspect_target_read_only", "Inspect the target using read-only status information."],
        ["preserve_evidence", "Preserve the current lifecycle and support evidence before changing system state."],
        ["operator_review_required", "Operator review is required before any new maintenance request."],
        ["new_request_only_after_terminal", "Do not create a replacement request until the current lifecycle is terminal."],
    ] as Array<[WorkflowRecoveryDiagnostic["safe_next_action"], string]>)("maps safe action %s", (safe_next_action, expected) => {
        render(<OperationalRecoverySummary diagnostic={diagnostic({ safe_next_action })} supportEvidenceAvailable={false} />);
        expect(screen.getByText((content) => content.includes(expected))).toBeInTheDocument();
    });

    it("keeps a diagnostic fetch failure distinct from an operational failure", () => {
        render(<OperationalRecoverySummary diagnostic={null} error="Mission Control could not read the recovery diagnostic." supportEvidenceAvailable={false} />);
        expect(screen.getByText("An unavailable report does not mean maintenance failed.")).toBeInTheDocument();
    });

    it("renders no forbidden secret or provider-native fields", () => {
        render(<OperationalRecoverySummary diagnostic={diagnostic()} supportEvidenceAvailable />);
        expect(document.body.textContent).not.toMatch(/Authorization|Bearer|cookie|CSRF|vmgenid|identity token|native payload|command|environment/i);
    });
});
