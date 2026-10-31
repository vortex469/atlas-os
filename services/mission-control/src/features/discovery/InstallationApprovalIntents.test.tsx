import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getInstallationApprovalIntent, listInstallationApprovalIntents, recordInstallationApprovalIntent,
} from "../../api/installationApprovalIntent";
import type { InstallationApprovalIntentV1 } from "../../types/installationApprovalIntent";
import type { InstallationCandidateRecordEnvelopeV1 } from "../../types/installationCandidateLifecycle";
import { InstallationApprovalIntents } from "./InstallationApprovalIntents";

vi.mock("../../api/installationApprovalIntent", () => ({
    listInstallationApprovalIntents: vi.fn(), getInstallationApprovalIntent: vi.fn(),
    recordInstallationApprovalIntent: vi.fn(), approvalIntentIdempotencyKey: vi.fn(() => "approval-key"),
}));

const ids = { intent: "00000000-0000-4000-8000-000000000001", record: "00000000-0000-4000-8000-000000000002" };
const envelope: InstallationCandidateRecordEnvelopeV1 = {
    schema: "installation-candidate-record-envelope-v1", candidate_record_id: ids.record, created_at: "2026-08-27T12:00:00Z",
    admission_fingerprint: "b".repeat(64), envelope_fingerprint: "a".repeat(64), lifecycle_state: "active",
    candidate_record: {
        schema: "installation-candidate-record-v1", item_id: "example", catalog_entry_id: "catalog-example",
        plan_fingerprint: "e".repeat(64), selection_id: "selection", selected_destination_fingerprint: "f".repeat(64),
        current_destination_fingerprint: "f".repeat(64), capability_assessment_fingerprint: "1".repeat(64),
        provider_fact_set_fingerprint: "2".repeat(64), evaluated_at: "2026-08-27T12:00:00Z", valid_until: "2026-08-27T12:05:00Z",
        approved: false, executable: false, deployable: false, dispatchable: false, agent_execution_supported: false,
        record_fingerprint: "c".repeat(64),
    },
};
const intent: InstallationApprovalIntentV1 = {
    schema: "installation-approval-intent-v1", approval_intent_id: ids.intent, operator_id: "operator-a",
    recorded_at: "2026-08-27T12:00:01Z", approved_subject: {
        candidate_record_id: ids.record, candidate_envelope_fingerprint: "a".repeat(64), admission_fingerprint: "b".repeat(64),
        candidate_record_fingerprint: "c".repeat(64),
    }, statement: "operator_approved_exact_non_executable_candidate", intent_fingerprint: "d".repeat(64),
};

describe("installation approval evidence", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listInstallationApprovalIntents).mockResolvedValue([]); });

    it("renders loading, empty, and redacted error states", async () => {
        let reject: (error: Error) => void = () => undefined;
        vi.mocked(listInstallationApprovalIntents)
            .mockReturnValueOnce(new Promise((_, rejectPromise) => { reject = rejectPromise; }))
            .mockResolvedValueOnce([]);
        const user = userEvent.setup();
        const view = render(<InstallationApprovalIntents records={[envelope]} csrfToken="csrf" />);
        expect(screen.getByText(/checking saved approval records/i)).toBeInTheDocument();
        reject(new Error("credential secret /internal/path 10.0.0.1"));
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Atlas could not load the approval records.");
        expect(alert.querySelector(":scope > p")).toHaveTextContent("Retry to check them again.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("Approval evidence is currently unavailable.")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /review approval statement/i })).not.toBeInTheDocument();
        expect(view.container).not.toHaveTextContent(/credential|internal\/path|10\.0\.0\.1/i);
        await user.click(screen.getByRole("button", { name: "Retry approval records" }));
        expect(await screen.findByText(/No approval records have been saved/i)).toBeInTheDocument();
        expect(listInstallationApprovalIntents).toHaveBeenCalledTimes(2);
    });

    it("lists and gets exact operator-scoped linkage with fixed statement", async () => {
        vi.mocked(listInstallationApprovalIntents).mockResolvedValueOnce([intent]);
        vi.mocked(getInstallationApprovalIntent).mockResolvedValueOnce(intent);
        const user = userEvent.setup();
        render(<InstallationApprovalIntents records={[envelope]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /view approval record/i }));
        const detail = screen.getByRole("heading", { name: /approval record history/i }).parentElement!;
        expect(within(detail).getByText(/grants no permission and cannot be used to run the candidate/i)).toBeVisible();
        expect(within(detail).getByText(/source record: available/i)).toBeVisible();
        const evidenceDetails = within(detail).getByText("Evidence details").closest("details");
        expect(evidenceDetails).not.toHaveAttribute("open");
        expect(within(evidenceDetails as HTMLElement).getByText("operator-a")).not.toBeVisible();
        await user.click(within(detail).getByText("Evidence details"));
        expect(within(detail).getByText("operator-a")).toBeVisible();
        expect(within(detail).getByText("2026-08-27T12:00:01Z")).toBeVisible();
        expect(within(detail).getByText("operator_approved_exact_non_executable_candidate")).toBeVisible();
        for (const value of [ids.record, "a".repeat(64), "b".repeat(64), "c".repeat(64), "d".repeat(64)]) {
            expect(within(detail).getByText(value)).toBeVisible();
        }
    });

    it("requires exact-record confirmation and appends approval evidence only", async () => {
        vi.mocked(recordInstallationApprovalIntent).mockResolvedValueOnce(intent);
        const user = userEvent.setup();
        const { container } = render(<InstallationApprovalIntents records={[envelope]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Review approval statement" }));
        expect(recordInstallationApprovalIntent).not.toHaveBeenCalled();
        const confirmation = screen.getByRole("heading", { name: /confirm approval statement/i }).parentElement!;
        expect(within(confirmation).getByText("Candidate item: example")).toBeVisible();
        expect(within(confirmation).getByText(/Candidate record ID:/)).toHaveTextContent(ids.record);
        expect(within(confirmation).getByText(/I approve this exact candidate as a non-executable record/i)).toBeVisible();
        expect(within(confirmation).getByText(/does not authorize or start work/i)).toBeVisible();
        const identityDetails = within(confirmation).getByText("Technical identity details").closest("details");
        expect(identityDetails).not.toHaveAttribute("open");
        expect(within(identityDetails as HTMLElement).getByText("a".repeat(64))).not.toBeVisible();
        await user.click(within(confirmation).getByRole("button", { name: /confirm and save record/i }));
        expect(recordInstallationApprovalIntent).toHaveBeenCalledWith(ids.record, "csrf", "approval-key");
        expect(await screen.findByText(/grants no permission and cannot be used to run the candidate/i)).toBeInTheDocument();
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
    });

    it("withholds approval recording until records load and after an uncertain attempt for the same candidate", async () => {
        let rejectList: (error: Error) => void = () => undefined;
        vi.mocked(listInstallationApprovalIntents).mockReturnValueOnce(new Promise((_, reject) => { rejectList = reject; }));
        const failedRead = render(<InstallationApprovalIntents records={[envelope]} csrfToken="csrf" />);
        rejectList(new Error("list unavailable"));
        await screen.findByText("Approval evidence is currently unavailable.");
        expect(screen.queryByRole("button", { name: /review approval statement/i })).not.toBeInTheDocument();
        failedRead.unmount();

        const otherIntent = { ...intent, approved_subject: { ...intent.approved_subject, candidate_record_id: "00000000-0000-4000-8000-000000000099" } };
        vi.mocked(listInstallationApprovalIntents).mockResolvedValueOnce([otherIntent]);
        vi.mocked(recordInstallationApprovalIntent).mockRejectedValueOnce(new Error("request outcome unknown"));
        vi.mocked(getInstallationApprovalIntent).mockResolvedValueOnce(otherIntent);
        const user = userEvent.setup();
        render(<InstallationApprovalIntents records={[envelope]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Review approval statement" }));
        await user.click(screen.getByRole("button", { name: /confirm and save record/i }));
        expect(await screen.findByText("Atlas could not confirm whether it saved this record. This screen will not send the request again.")).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: /confirm approval statement/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review approval statement" })).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Check saved record" }));
        expect(await screen.findByText(/No matching approval record was found.*will not send the request again/i)).toBeInTheDocument();
        expect(recordInstallationApprovalIntent).toHaveBeenCalledTimes(1);
        expect(listInstallationApprovalIntents).toHaveBeenCalledTimes(3);
    });

    it("keeps Home Assistant non-approvable and exposes no prohibited controls or navigation", async () => {
        const { container } = render(<InstallationApprovalIntents records={[]} csrfToken="csrf" />);
        await screen.findByText(/No approval records have been saved/i);
        expect(screen.queryByRole("button", { name: /review approval statement/i })).not.toBeInTheDocument();
        expect(recordInstallationApprovalIntent).not.toHaveBeenCalled();
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
        const controls = Array.from(container.querySelectorAll("button, a")).map((node) => node.textContent).join(" ");
        expect(controls).not.toMatch(/install|run|execute|deploy|dispatch|send to agent|start workflow|prepare install|convert|rollback/i);
    });

    it("distinguishes unavailable source without reconstructing it", async () => {
        vi.mocked(listInstallationApprovalIntents).mockResolvedValueOnce([intent]);
        vi.mocked(getInstallationApprovalIntent).mockResolvedValueOnce(intent);
        const user = userEvent.setup();
        render(<InstallationApprovalIntents records={[]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /view approval record/i }));
        expect(await screen.findByText(/unavailable or deleted; the historical identity is not reconstructed/i)).toBeInTheDocument();
    });

    it("keeps the evidence list visible after a review read fails and retries that read", async () => {
        const apiError = {
            isAxiosError: true,
            response: { data: { error: { message: "Approval evidence record is unavailable." } } },
        };
        vi.mocked(listInstallationApprovalIntents).mockResolvedValueOnce([intent]);
        vi.mocked(getInstallationApprovalIntent)
            .mockRejectedValueOnce(apiError)
            .mockResolvedValueOnce(intent);
        const user = userEvent.setup();
        render(<InstallationApprovalIntents records={[envelope]} csrfToken="csrf" />);

        await user.click(await screen.findByRole("button", { name: "View approval record" }));
        const message = await screen.findByText("Atlas could not load this approval record. The list is still available.");
        const alert = message.closest("[role=alert]") as HTMLElement;
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("Approval evidence record is unavailable.")).toBeInTheDocument();
        expect(screen.getByText("Approval record saved")).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Retry record review" }));
        expect(await screen.findByRole("heading", { name: "Approval record history" })).toBeInTheDocument();
        expect(getInstallationApprovalIntent).toHaveBeenCalledTimes(2);
        expect(listInstallationApprovalIntents).toHaveBeenCalledTimes(1);
    });

    it("recovers an uncertain approval write when a read finds the saved evidence", async () => {
        vi.mocked(listInstallationApprovalIntents)
            .mockResolvedValueOnce([])
            .mockResolvedValueOnce([intent]);
        vi.mocked(recordInstallationApprovalIntent).mockRejectedValueOnce(new Error("response was lost"));
        const user = userEvent.setup();
        render(<InstallationApprovalIntents records={[envelope]} csrfToken="csrf" />);

        await user.click(await screen.findByRole("button", { name: "Review approval statement" }));
        await user.click(screen.getByRole("button", { name: /confirm and save record/i }));
        await screen.findByText("Atlas could not confirm whether it saved this record. This screen will not send the request again.");

        await user.click(screen.getByRole("button", { name: "Check saved record" }));
        expect(await screen.findByText("Atlas found the saved approval record. Review its details below.")).toBeInTheDocument();
        expect(await screen.findByRole("heading", { name: "Approval record history" })).toBeInTheDocument();
        expect(recordInstallationApprovalIntent).toHaveBeenCalledTimes(1);
        expect(listInstallationApprovalIntents).toHaveBeenCalledTimes(2);
    });
});
