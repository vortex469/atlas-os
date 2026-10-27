import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getInstallationCandidateAdmission } from "../../api/installationCandidateAdmission";
import type { InstallationCandidateAdmissionV1 } from "../../types/installationCandidateAdmission";
import { InstallationCandidateAdmission } from "./InstallationCandidateAdmission";

vi.mock("../../api/installationCandidateAdmission", () => ({ getInstallationCandidateAdmission: vi.fn() }));
vi.mock("../../api/installationCandidateLifecycle", () => ({
    listInstallationCandidateRecords: vi.fn(() => Promise.resolve([])),
    getInstallationCandidateRecord: vi.fn(), preserveInstallationCandidateRecord: vi.fn(),
    deleteInstallationCandidateRecord: vi.fn(), candidateRecordIdempotencyKey: vi.fn(() => "key"),
}));

function fixture(admitted = false): InstallationCandidateAdmissionV1 {
    const candidate_record = admitted ? {
        schema: "installation-candidate-record-v1" as const, item_id: "example", catalog_entry_id: "catalog-example",
        plan_fingerprint: "plan-fingerprint", selection_id: "selection-1",
        selected_destination_fingerprint: "destination-fingerprint", current_destination_fingerprint: "destination-fingerprint",
        capability_assessment_fingerprint: "assessment-fingerprint", provider_fact_set_fingerprint: "fact-set-fingerprint",
        evaluated_at: "2026-08-27T12:00:00Z", valid_until: "2026-08-27T12:05:00Z",
        approved: false as const, executable: false as const, deployable: false as const,
        dispatchable: false as const, agent_execution_supported: false as const, record_fingerprint: "record-fingerprint",
    } : null;
    return {
        schema: "installation-candidate-admission-v1", plan_fingerprint: "plan-fingerprint",
        selection_fingerprint: "selection-fingerprint", selected_destination_fingerprint: "destination-fingerprint",
        current_destination_fingerprint: "destination-fingerprint", capability_assessment_fingerprint: "assessment-fingerprint",
        provider_fact_set_fingerprint: "fact-set-fingerprint", evaluated_at: "2026-08-27T12:00:00Z",
        status: admitted ? "admitted_but_non_executable" : "not_admitted",
        reason_codes: admitted ? [] : ["installation_plan_not_review_ready", "capability_assessment_not_admissible"],
        candidate_record, approved: false, executable: false, deployable: false, dispatchable: false,
        agent_execution_supported: false, candidate_creation_allowed: false, admission_fingerprint: "admission-fingerprint",
    };
}

describe("installation candidate admission", () => {
    beforeEach(() => vi.resetAllMocks());

    it("shows the review-only outcome first and keeps linkage and authority details available", async () => {
        vi.mocked(getInstallationCandidateAdmission).mockResolvedValueOnce(fixture(true));
        const user = userEvent.setup();
        const { container } = render(<InstallationCandidateAdmission itemId="example" selectionId="selection-1" />);
        expect(await screen.findByText("A review-only candidate record is available. It cannot be executed, deployed, or dispatched.", { selector: 'p[role="status"]' })).toBeInTheDocument();
        expect(screen.getByText(/does not approve or start an installation/i)).toBeInTheDocument();
        expect(document.body).not.toHaveTextContent("admitted_but_non_executable");
        const linkageSummary = screen.getByText("Source linkage and technical identifiers");
        const linkage = linkageSummary.closest("details");
        expect(linkage).not.toHaveAttribute("open");
        await user.click(linkageSummary);
        for (const fingerprint of ["plan-fingerprint", "selection-fingerprint", "destination-fingerprint", "assessment-fingerprint", "fact-set-fingerprint"]) {
            expect(within(linkage!).getAllByText(fingerprint).length).toBeGreaterThan(0);
        }
        const recordDetails = screen.getByText("Record details");
        await user.click(recordDetails);
        const flags = container.querySelector<HTMLElement>('[aria-label="Candidate record authority flags"]');
        expect(flags).not.toBeNull();
        if (!flags) throw new Error("candidate authority flags were not rendered");
        expect(within(flags).getAllByText("false")).toHaveLength(5);
        expect(container.querySelectorAll("button, a, form")).toHaveLength(0);
    });

    it("explains why Home Assistant has no candidate record and keeps ordered codes available", async () => {
        vi.mocked(getInstallationCandidateAdmission).mockResolvedValueOnce(fixture(false));
        const user = userEvent.setup();
        render(<InstallationCandidateAdmission itemId="home-assistant" selectionId="selection-1" />);
        expect(await screen.findByText("No candidate record is available yet. Review the reasons below.", { selector: 'p[role="status"]' })).toBeInTheDocument();
        expect(document.body).not.toHaveTextContent("not_admitted");
        const reasons = screen.getByRole("list", { name: "Candidate record check reasons" });
        expect(reasons.textContent).toMatch(/plan is not ready for review.*capability check does not support a review record/i);
        expect(reasons).not.toHaveTextContent("installation_plan_not_review_ready");
        const diagnostics = screen.getByText("Technical reason codes");
        const disclosure = diagnostics.closest("details");
        expect(disclosure).not.toHaveAttribute("open");
        await user.click(diagnostics);
        expect(within(disclosure!).getByText("installation_plan_not_review_ready")).toBeInTheDocument();
        expect(within(disclosure!).getByText("capability_assessment_not_admissible")).toBeInTheDocument();
    });

    it("renders empty, loading, error, and no-response states with redacted errors", async () => {
        const empty = render(<InstallationCandidateAdmission itemId="example" selectionId={null} />);
        expect(screen.getByText(/select a prospective destination above/i)).toBeInTheDocument();
        empty.unmount();

        let rejectRequest: (reason: Error) => void = () => undefined;
        vi.mocked(getInstallationCandidateAdmission).mockReturnValueOnce(new Promise((_, reject) => { rejectRequest = reject; }));
        const loading = render(<InstallationCandidateAdmission itemId="example" selectionId="selection-1" />);
        expect(await screen.findByText(/checking candidate record availability/i)).toBeInTheDocument();
        rejectRequest(new Error("credential secret at /internal/path and 10.0.0.1"));
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/currently unavailable/i));
        expect(loading.container).not.toHaveTextContent(/secret|internal\/path|10\.0\.0\.1/i);
        loading.unmount();

        vi.mocked(getInstallationCandidateAdmission).mockResolvedValueOnce(null as unknown as InstallationCandidateAdmissionV1);
        render(<InstallationCandidateAdmission itemId="example" selectionId="selection-1" />);
        expect(await screen.findByText(/no candidate review result was returned/i)).toBeInTheDocument();
    });

    it("does not expose injected provider data, controls, navigation, or authority actions", async () => {
        const value = fixture(true) as InstallationCandidateAdmissionV1 & { raw_provider_payload?: unknown };
        value.raw_provider_payload = { address: "10.0.0.1", credential: "secret", command: "rm data", logs: "/internal/path" };
        vi.mocked(getInstallationCandidateAdmission).mockResolvedValueOnce(value);
        const { container } = render(<InstallationCandidateAdmission itemId="example" selectionId="selection-1" />);
        await screen.findByText(/record-fingerprint/i);
        expect(container).not.toHaveTextContent(/10\.0\.0\.1|secret|rm data|internal\/path/i);
        expect(container.querySelectorAll("button, a, form")).toHaveLength(0);
        expect(container.textContent).not.toMatch(/create candidate|start workflow|retry action|install now|prepare now|execute now/i);
    });
});
