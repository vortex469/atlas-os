import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    candidateRecordIdempotencyKey,
    deleteInstallationCandidateRecord, getInstallationCandidateRecord, listInstallationCandidateRecords,
    preserveInstallationCandidateRecord,
} from "../../api/installationCandidateLifecycle";
import type { InstallationCandidateAdmissionV1 } from "../../types/installationCandidateAdmission";
import type { InstallationCandidateRecordEnvelopeV1 } from "../../types/installationCandidateLifecycle";
import { InstallationCandidateLifecycle } from "./InstallationCandidateLifecycle";

vi.mock("../../api/installationCandidateLifecycle", () => ({
    listInstallationCandidateRecords: vi.fn(), getInstallationCandidateRecord: vi.fn(),
    preserveInstallationCandidateRecord: vi.fn(), deleteInstallationCandidateRecord: vi.fn(),
    candidateRecordIdempotencyKey: vi.fn(() => "preserve-key"),
}));
vi.mock("./InstallationApprovalIntents", () => ({ InstallationApprovalIntents: () => null }));

const candidate = {
    schema: "installation-candidate-record-v1" as const, item_id: "example", catalog_entry_id: "catalog-example",
    plan_fingerprint: "plan-fingerprint", selection_id: "selection-1", selected_destination_fingerprint: "selected-fingerprint",
    current_destination_fingerprint: "current-fingerprint", capability_assessment_fingerprint: "assessment-fingerprint",
    provider_fact_set_fingerprint: "facts-fingerprint", evaluated_at: "2026-08-27T12:00:00Z", valid_until: "2026-08-27T12:05:00Z",
    approved: false as const, executable: false as const, deployable: false as const, dispatchable: false as const,
    agent_execution_supported: false as const, record_fingerprint: "candidate-fingerprint",
};
const envelope = (state: "active" | "expired" = "active"): InstallationCandidateRecordEnvelopeV1 => ({
    schema: "installation-candidate-record-envelope-v1", candidate_record_id: `record-${state}`, created_at: "2026-08-27T12:00:01Z",
    admission_fingerprint: "admission-fingerprint", candidate_record: candidate, envelope_fingerprint: "envelope-fingerprint", lifecycle_state: state,
});
const admission = (admitted = true): InstallationCandidateAdmissionV1 => ({
    schema: "installation-candidate-admission-v1", plan_fingerprint: "plan", selection_fingerprint: "selection",
    selected_destination_fingerprint: "selected", current_destination_fingerprint: "current", capability_assessment_fingerprint: "assessment",
    provider_fact_set_fingerprint: "facts", evaluated_at: "2026-08-27T12:00:00Z", status: admitted ? "admitted_but_non_executable" : "not_admitted",
    reason_codes: admitted ? [] : ["installation_plan_not_review_ready"], candidate_record: admitted ? candidate : null,
    approved: false, executable: false, deployable: false, dispatchable: false, agent_execution_supported: false,
    candidate_creation_allowed: false, admission_fingerprint: "admission",
});

describe("installation candidate lifecycle", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listInstallationCandidateRecords).mockResolvedValue([]); });

    it("renders loading, redacted list errors, and retries the review-record list", async () => {
        let reject: (error: Error) => void = () => undefined;
        vi.mocked(listInstallationCandidateRecords)
            .mockReturnValueOnce(new Promise((_, rejectPromise) => { reject = rejectPromise; }))
            .mockResolvedValueOnce([]);
        const user = userEvent.setup();
        const view = render(<InstallationCandidateLifecycle admission={null} itemId="example" selectionId={null} csrfToken={null} />);
        expect(screen.getByText(/loading saved review records/i)).toBeInTheDocument();
        reject(new Error("secret 10.0.0.1 /internal/path"));
        const message = await screen.findByText("Atlas could not load the saved review records. Retry to check the list.");
        const alert = message.closest("[role=alert]") as HTMLElement;
        expect(alert.querySelector(":scope > p")).toHaveTextContent("Atlas could not load the saved review records.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("Saved review records are currently unavailable.")).toBeInTheDocument();
        expect(view.container).not.toHaveTextContent(/secret|10\.0\.0\.1|internal\/path/i);
        await user.click(screen.getByRole("button", { name: "Retry list" }));
        expect(await screen.findByText("No saved review records.")).toBeInTheDocument();
        expect(listInstallationCandidateRecords).toHaveBeenCalledTimes(2);
    });

    it("lists current and outdated records, gets details, and visibly preserves five false flags", async () => {
        vi.mocked(listInstallationCandidateRecords).mockResolvedValueOnce([envelope("active"), envelope("expired")]);
        vi.mocked(getInstallationCandidateRecord).mockResolvedValueOnce(envelope("expired"));
        const user = userEvent.setup();
        const { container } = render(<InstallationCandidateLifecycle admission={admission()} itemId="example" selectionId="selection-1" csrfToken="csrf" />);
        expect(await screen.findByText("example · Inputs up to date")).toBeInTheDocument();
        expect(screen.getByText("example · Inputs outdated")).toBeInTheDocument();
        expect(screen.getByText("record-active")).not.toBeVisible();
        await user.click(screen.getAllByRole("button", { name: "View saved record" })[1]);
        expect(await screen.findByText("candidate-fingerprint")).toBeInTheDocument();
        const flags = container.querySelector<HTMLElement>('[aria-label="Saved candidate record authority flags"]');
        expect(flags).not.toBeNull();
        expect(within(flags!).getAllByText("false")).toHaveLength(5);
        const recordDetails = screen.getByText("Record details").closest("details");
        expect(recordDetails).not.toHaveAttribute("open");
        expect(flags).not.toBeVisible();
        await user.click(screen.getByText("Record details"));
        expect(recordDetails).toHaveAttribute("open");
        expect(flags).toBeVisible();
    });

    it("keeps the saved-record list visible after a review read fails and retries that read", async () => {
        const apiError = {
            isAxiosError: true,
            response: { data: { error: { message: "Installation candidate record was not found." } } },
        };
        vi.mocked(listInstallationCandidateRecords).mockResolvedValueOnce([envelope("active"), envelope("expired")]);
        vi.mocked(getInstallationCandidateRecord)
            .mockRejectedValueOnce(apiError)
            .mockResolvedValueOnce(envelope("expired"));
        const user = userEvent.setup();
        render(<InstallationCandidateLifecycle admission={null} itemId="example" selectionId={null} csrfToken="csrf" />);

        await user.click((await screen.findAllByRole("button", { name: "View saved record" }))[1]);
        const message = await screen.findByText("Atlas could not open this review record. Your saved review records are still available.");
        const alert = message.closest("[role=alert]") as HTMLElement;
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("Installation candidate record was not found.")).toBeInTheDocument();
        expect(screen.getByText("example · Inputs up to date")).toBeInTheDocument();
        expect(screen.getByText("example · Inputs outdated")).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Retry opening record" }));
        expect(await screen.findByText("candidate-fingerprint")).toBeInTheDocument();
        expect(getInstallationCandidateRecord).toHaveBeenCalledTimes(2);
        expect(listInstallationCandidateRecords).toHaveBeenCalledTimes(1);
    });

    it("saves only an eligible review record with non-authorizing language", async () => {
        vi.mocked(preserveInstallationCandidateRecord).mockResolvedValueOnce(envelope());
        const user = userEvent.setup();
        render(<InstallationCandidateLifecycle admission={admission()} itemId="example" selectionId="selection-1" csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Save review record" }));
        expect(preserveInstallationCandidateRecord).toHaveBeenCalledWith({ item_id: "example", selection_id: "selection-1" }, "csrf", "preserve-key");
        expect(screen.getByText(/saving one does not approve or start an installation/i)).toBeInTheDocument();
    });

    it("shows a plain save failure and safely retries the same request", async () => {
        const apiError = {
            isAxiosError: true,
            response: { data: { error: { message: "Installation candidate record request conflicts with current state." } } },
        };
        vi.mocked(preserveInstallationCandidateRecord)
            .mockRejectedValueOnce(apiError)
            .mockResolvedValueOnce(envelope());
        const user = userEvent.setup();
        render(<InstallationCandidateLifecycle admission={admission()} itemId="example" selectionId="selection-1" csrfToken="csrf" />);

        await user.click(await screen.findByRole("button", { name: "Save review record" }));

        const message = await screen.findByText("Atlas could not confirm whether it saved the review record. Retry the same request to check.");
        const alert = message.closest("[role=alert]") as HTMLElement;
        expect(alert.querySelector(":scope > p")).toHaveTextContent("Atlas could not confirm whether it saved the review record.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("Installation candidate record request conflicts with current state.")).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Retry save" }));
        expect(await screen.findByText("example · Inputs up to date")).toBeInTheDocument();
        expect(preserveInstallationCandidateRecord).toHaveBeenNthCalledWith(1, { item_id: "example", selection_id: "selection-1" }, "csrf", "preserve-key");
        expect(preserveInstallationCandidateRecord).toHaveBeenNthCalledWith(2, { item_id: "example", selection_id: "selection-1" }, "csrf", "preserve-key");
        expect(candidateRecordIdempotencyKey).toHaveBeenCalledTimes(1);
        expect(screen.queryByText("Atlas could not confirm whether it saved the review record.")).not.toBeInTheDocument();
    });

    it("keeps Home Assistant not preserved and exposes no authority control or navigation", async () => {
        const { container } = render(<InstallationCandidateLifecycle admission={admission(false)} itemId="home-assistant" selectionId="selection-1" csrfToken="csrf" />);
        expect(await screen.findByText(/did not produce a review record that can be saved/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /save review record/i })).not.toBeInTheDocument();
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
        expect(container.textContent).not.toMatch(/start workflow|send to agent|convert candidate|approve candidate/i);
        expect(preserveInstallationCandidateRecord).not.toHaveBeenCalled();
    });

    it("deletes explicitly and confirms the review record was removed", async () => {
        vi.mocked(listInstallationCandidateRecords).mockResolvedValueOnce([envelope()]);
        vi.mocked(deleteInstallationCandidateRecord).mockResolvedValueOnce();
        const user = userEvent.setup();
        render(<InstallationCandidateLifecycle admission={null} itemId="example" selectionId={null} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Delete review record" }));
        expect(deleteInstallationCandidateRecord).toHaveBeenCalledWith("record-active", "csrf");
        expect(await screen.findByText("The saved review record was deleted.")).toBeInTheDocument();
    });

    it("checks saved records before allowing another delete after an uncertain result", async () => {
        const apiError = {
            isAxiosError: true,
            response: { data: { error: { message: "Installation candidate record dependency is unavailable." } } },
        };
        vi.mocked(listInstallationCandidateRecords)
            .mockResolvedValueOnce([envelope()])
            .mockResolvedValueOnce([]);
        vi.mocked(deleteInstallationCandidateRecord).mockRejectedValueOnce(apiError);
        const user = userEvent.setup();
        render(<InstallationCandidateLifecycle admission={null} itemId="example" selectionId={null} csrfToken="csrf" />);

        await user.click(await screen.findByRole("button", { name: "Delete review record" }));
        const message = await screen.findByText("Atlas could not confirm whether the review record was removed. Refresh the list before trying again.");
        const alert = message.closest("[role=alert]") as HTMLElement;
        expect(alert.querySelector(":scope > p")).toHaveTextContent("Atlas could not confirm whether the review record was removed.");
        expect(within(alert).getByText("Technical details").closest("details")).not.toHaveAttribute("open");
        expect(screen.getByRole("button", { name: "Delete review record" })).toBeDisabled();

        await user.click(screen.getByRole("button", { name: "Refresh list" }));
        expect(await screen.findByText("The saved review record was deleted.")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Delete review record" })).not.toBeInTheDocument();
        expect(deleteInstallationCandidateRecord).toHaveBeenCalledTimes(1);
        expect(listInstallationCandidateRecords).toHaveBeenCalledTimes(2);
    });

    it("re-enables deletion only after refresh confirms the record is still present", async () => {
        vi.mocked(listInstallationCandidateRecords)
            .mockResolvedValueOnce([envelope()])
            .mockResolvedValueOnce([envelope()]);
        vi.mocked(deleteInstallationCandidateRecord).mockRejectedValueOnce(new Error("connection lost"));
        const user = userEvent.setup();
        render(<InstallationCandidateLifecycle admission={null} itemId="example" selectionId={null} csrfToken="csrf" />);

        await user.click(await screen.findByRole("button", { name: "Delete review record" }));
        await screen.findByRole("button", { name: "Refresh list" });
        await user.click(screen.getByRole("button", { name: "Refresh list" }));

        expect(await screen.findByRole("status")).toHaveTextContent(/review record is still saved.*try deleting it again/i);
        expect(screen.getByRole("button", { name: "Delete review record" })).toBeEnabled();
        expect(deleteInstallationCandidateRecord).toHaveBeenCalledTimes(1);
        expect(listInstallationCandidateRecords).toHaveBeenCalledTimes(2);
    });
});
