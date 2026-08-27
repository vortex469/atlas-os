import { render, screen, waitFor, within } from "@testing-library/react";
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
        vi.mocked(listInstallationApprovalIntents).mockReturnValueOnce(new Promise((_, rejectPromise) => { reject = rejectPromise; }));
        const view = render(<InstallationApprovalIntents records={[]} csrfToken={null} />);
        expect(screen.getByText(/loading installation approval evidence/i)).toBeInTheDocument();
        reject(new Error("credential secret /internal/path 10.0.0.1"));
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/currently unavailable/i));
        expect(view.container).not.toHaveTextContent(/credential|internal\/path|10\.0\.0\.1/i);
        view.unmount();
        vi.mocked(listInstallationApprovalIntents).mockResolvedValueOnce([]);
        render(<InstallationApprovalIntents records={[]} csrfToken={null} />);
        expect(await screen.findByText(/no installation approval evidence has been recorded/i)).toBeInTheDocument();
    });

    it("lists and gets exact operator-scoped linkage with fixed statement", async () => {
        vi.mocked(listInstallationApprovalIntents).mockResolvedValueOnce([intent]);
        vi.mocked(getInstallationApprovalIntent).mockResolvedValueOnce(intent);
        const user = userEvent.setup();
        render(<InstallationApprovalIntents records={[envelope]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /review approval evidence/i }));
        const detail = screen.getByRole("heading", { name: /immutable operator-scoped/i }).parentElement!;
        expect(within(detail).getByText("operator-a")).toBeInTheDocument();
        expect(within(detail).getByText("2026-08-27T12:00:01Z")).toBeInTheDocument();
        expect(within(detail).getByText("operator_approved_exact_non_executable_candidate")).toBeInTheDocument();
        for (const value of [ids.record, "a".repeat(64), "b".repeat(64), "c".repeat(64), "d".repeat(64)]) {
            expect(within(detail).getByText(value)).toBeInTheDocument();
        }
    });

    it("requires exact-record confirmation and appends approval evidence only", async () => {
        vi.mocked(recordInstallationApprovalIntent).mockResolvedValueOnce(intent);
        const user = userEvent.setup();
        const { container } = render(<InstallationApprovalIntents records={[envelope]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Record approval intent" }));
        expect(recordInstallationApprovalIntent).not.toHaveBeenCalled();
        const confirmation = screen.getByRole("heading", { name: /confirm exact non-executable candidate identity/i }).parentElement!;
        expect(within(confirmation).getByText(ids.record)).toBeInTheDocument();
        expect(within(confirmation).getByText(/does not authorize or initiate any work/i)).toBeInTheDocument();
        await user.click(within(confirmation).getByRole("button", { name: /confirm and record approval evidence only/i }));
        expect(recordInstallationApprovalIntent).toHaveBeenCalledWith(ids.record, "csrf", "approval-key");
        expect(await screen.findByText(/historical evidence only/i)).toBeInTheDocument();
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
    });

    it("keeps Home Assistant non-approvable and exposes no prohibited controls or navigation", async () => {
        const { container } = render(<InstallationApprovalIntents records={[]} csrfToken="csrf" />);
        await screen.findByText(/no installation approval evidence/i);
        expect(screen.queryByRole("button", { name: /record approval intent/i })).not.toBeInTheDocument();
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
        await user.click(await screen.findByRole("button", { name: /review approval evidence/i }));
        expect(await screen.findByText(/unavailable or deleted; the historical identity is not reconstructed/i)).toBeInTheDocument();
    });
});
