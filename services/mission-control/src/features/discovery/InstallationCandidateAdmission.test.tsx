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

describe("review record check", () => {
    beforeEach(() => vi.resetAllMocks());

    it("leads with a plain-language result and keeps exact linkage collapsed", async () => {
        vi.mocked(getInstallationCandidateAdmission).mockResolvedValueOnce(fixture(true));
        const { container } = render(<InstallationCandidateAdmission itemId="example" selectionId="selection-1" />);
        expect(await screen.findByText("A review record is available to save")).toBeInTheDocument();
        expect(screen.getByText("Checks whether Atlas can save a review record for this plan and VM. It does not approve or start an installation.")).toBeInTheDocument();
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        for (const fingerprint of ["plan-fingerprint", "selection-fingerprint", "destination-fingerprint", "assessment-fingerprint", "fact-set-fingerprint"]) {
            for (const value of within(technicalDetails as HTMLElement).getAllByText(fingerprint)) expect(value).not.toBeVisible();
        }
        await userEvent.setup().click(screen.getByText("Technical details"));
        for (const fingerprint of ["plan-fingerprint", "selection-fingerprint", "destination-fingerprint", "assessment-fingerprint", "fact-set-fingerprint"]) {
            for (const value of within(technicalDetails as HTMLElement).getAllByText(fingerprint)) expect(value).toBeVisible();
            expect(screen.getAllByText(fingerprint).length).toBeGreaterThan(0);
        }
        const flags = container.querySelector<HTMLElement>('[aria-label="Candidate record authority flags"]');
        expect(flags).not.toBeNull();
        if (!flags) throw new Error("candidate authority flags were not rendered");
        expect(within(flags).getAllByText("false")).toHaveLength(5);
        const buttonLabels = Array.from(container.querySelectorAll("button"), (button) => button.textContent?.trim());
        expect(buttonLabels).toEqual(["Retry approval records", "Retry request records"]);
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
    });

    it("shows plain-language reasons and keeps their exact codes collapsed", async () => {
        vi.mocked(getInstallationCandidateAdmission).mockResolvedValueOnce(fixture(false));
        render(<InstallationCandidateAdmission itemId="home-assistant" selectionId="selection-1" />);
        expect(await screen.findByText("This plan is not ready to save for review")).toBeInTheDocument();
        const reasons = screen.getByRole("list", { name: /review record check reasons/i });
        expect(reasons.textContent).toMatch(/plan is not ready for review.*capability check did not confirm that requirements are met/i);
        expect(reasons.textContent).not.toMatch(/installation_plan_not_review_ready|capability_assessment_not_admissible/);
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("installation_plan_not_review_ready")).not.toBeVisible();
        await userEvent.setup().click(screen.getByText("Technical details"));
        expect(within(technicalDetails as HTMLElement).getByText("installation_plan_not_review_ready")).toBeVisible();
    });

    it("renders empty, loading, error, and no-response states with redacted errors", async () => {
        const empty = render(<InstallationCandidateAdmission itemId="example" selectionId={null} />);
        expect(screen.getByText(/select a vm above before checking whether a review record can be saved/i)).toBeInTheDocument();
        empty.unmount();

        let rejectRequest: (reason: Error) => void = () => undefined;
        vi.mocked(getInstallationCandidateAdmission).mockReturnValueOnce(new Promise((_, reject) => { rejectRequest = reject; }));
        vi.mocked(getInstallationCandidateAdmission).mockResolvedValueOnce(fixture(false));
        const loading = render(<InstallationCandidateAdmission itemId="example" selectionId="selection-1" />);
        expect(await screen.findByText(/checking whether a review record can be saved/i)).toBeInTheDocument();
        rejectRequest(new Error("credential secret at /internal/path and 10.0.0.1"));
        await waitFor(() => expect(screen.getByRole("alert").querySelector(":scope > p")).toHaveTextContent("Atlas could not check whether a review record can be saved for this VM."));
        expect(loading.container).not.toHaveTextContent(/secret|internal\/path|10\.0\.0\.1/i);
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("Review record check is currently unavailable.")).toBeInTheDocument();
        await userEvent.setup().click(screen.getByRole("button", { name: "Retry check" }));
        expect(await screen.findByText("This plan is not ready to save for review")).toBeInTheDocument();
        expect(getInstallationCandidateAdmission).toHaveBeenCalledTimes(2);
        loading.unmount();

        vi.mocked(getInstallationCandidateAdmission).mockResolvedValueOnce(null as unknown as InstallationCandidateAdmissionV1);
        render(<InstallationCandidateAdmission itemId="example" selectionId="selection-1" />);
        expect(await screen.findByText(/no result was returned for the review record check/i)).toBeInTheDocument();
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
