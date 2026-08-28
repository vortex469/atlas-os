import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
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

    it("renders loading, empty, and redacted error states", async () => {
        let reject: (error: Error) => void = () => undefined;
        vi.mocked(listInstallationCandidateRecords).mockReturnValueOnce(new Promise((_, rejectPromise) => { reject = rejectPromise; }));
        const view = render(<InstallationCandidateLifecycle admission={null} itemId="example" selectionId={null} csrfToken={null} />);
        expect(screen.getByText(/loading saved candidate records/i)).toBeInTheDocument();
        reject(new Error("secret 10.0.0.1 /internal/path"));
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/currently unavailable/i));
        expect(view.container).not.toHaveTextContent(/secret|10\.0\.0\.1|internal\/path/i);
        view.unmount();
        vi.mocked(listInstallationCandidateRecords).mockResolvedValueOnce([]);
        render(<InstallationCandidateLifecycle admission={null} itemId="example" selectionId={null} csrfToken={null} />);
        expect(await screen.findByText("No saved candidate records.")).toBeInTheDocument();
    });

    it("lists active and expired records, gets details, and visibly preserves five false flags", async () => {
        vi.mocked(listInstallationCandidateRecords).mockResolvedValueOnce([envelope("active"), envelope("expired")]);
        vi.mocked(getInstallationCandidateRecord).mockResolvedValueOnce(envelope("expired"));
        const user = userEvent.setup();
        const { container } = render(<InstallationCandidateLifecycle admission={admission()} itemId="example" selectionId="selection-1" csrfToken="csrf" />);
        expect(await screen.findByText("example · active")).toBeInTheDocument();
        expect(screen.getByText("example · expired")).toBeInTheDocument();
        await user.click(screen.getAllByRole("button", { name: "Review saved record" })[1]);
        expect(await screen.findByText("candidate-fingerprint")).toBeInTheDocument();
        const flags = container.querySelector<HTMLElement>('[aria-label="Saved candidate record authority flags"]');
        expect(flags).not.toBeNull();
        expect(within(flags!).getAllByText("false")).toHaveLength(5);
    });

    it("preserves only a positive candidate with non-authorizing language", async () => {
        vi.mocked(preserveInstallationCandidateRecord).mockResolvedValueOnce(envelope());
        const user = userEvent.setup();
        render(<InstallationCandidateLifecycle admission={admission()} itemId="example" selectionId="selection-1" csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Preserve candidate record" }));
        expect(preserveInstallationCandidateRecord).toHaveBeenCalledWith({ item_id: "example", selection_id: "selection-1" }, "csrf", "preserve-key");
        expect(screen.getByText(/preservation is not approval/i)).toBeInTheDocument();
    });

    it("keeps Home Assistant not preserved and exposes no authority control or navigation", async () => {
        const { container } = render(<InstallationCandidateLifecycle admission={admission(false)} itemId="home-assistant" selectionId="selection-1" csrfToken="csrf" />);
        expect(await screen.findByText(/cannot be preserved/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /preserve/i })).not.toBeInTheDocument();
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
        expect(container.textContent).not.toMatch(/start workflow|send to agent|convert candidate|approve candidate/i);
        expect(preserveInstallationCandidateRecord).not.toHaveBeenCalled();
    });

    it("deletes explicitly and shows terminal no-replay language", async () => {
        vi.mocked(listInstallationCandidateRecords).mockResolvedValueOnce([envelope()]);
        vi.mocked(deleteInstallationCandidateRecord).mockResolvedValueOnce();
        const user = userEvent.setup();
        render(<InstallationCandidateLifecycle admission={null} itemId="example" selectionId={null} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Delete saved record" }));
        expect(deleteInstallationCandidateRecord).toHaveBeenCalledWith("record-active", "csrf");
        expect(await screen.findByText(/advisory record is gone and cannot be replayed/i)).toBeInTheDocument();
    });
});
