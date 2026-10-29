import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { InstallationPlan } from "../../types/installationPlan";
import type { InstallationAdmissionReasonCode } from "../../types/installationDestination";
import {
    assessInstallationAdmission,
    installationIdempotencyKey,
    listProspectiveInstallationDestinations,
    selectProspectiveInstallationDestination,
} from "../../api/installationDestination";
import { ProspectiveDestinationReview, REASON_LABELS } from "./ProspectiveDestinationReview";

vi.mock("../../api/installationDestination", () => ({
    listProspectiveInstallationDestinations: vi.fn(),
    selectProspectiveInstallationDestination: vi.fn(),
    assessInstallationAdmission: vi.fn(),
    installationIdempotencyKey: vi.fn(() => "mission-control-test-key"),
}));

const fingerprint = "34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a";
const plan = {
    application: { item_id: "home-assistant", catalog_entry_id: "d5-home-assistant" },
    fingerprint: { value: fingerprint },
} as InstallationPlan;
const destination = {
    schema_version: "prospective-installation-destination-v1" as const,
    provider: "proxmox" as const, resource_type: "qemu" as const, placement_kind: "existing-guest" as const,
    resource_id: "101", destination_fingerprint: "a".repeat(64), enumeration_token: "b".repeat(64),
};
const secondDestination = {
    ...destination,
    resource_id: "202", destination_fingerprint: "2".repeat(64), enumeration_token: "3".repeat(64),
};
const selection = {
    schema_version: "installation-destination-selection-v1" as const,
    selection_id: "00000000-0000-4000-8000-000000000001",
    provider: "proxmox" as const, resource_type: "qemu" as const, placement_kind: "existing-guest" as const,
    resource_id: "101", selected_destination_fingerprint: "a".repeat(64), selected_at: "2026-08-27T00:00:00Z",
    expires_at: "2026-08-28T00:00:00Z", selected_by: "operator", request_digest: "c".repeat(64),
    selection_fingerprint: "d".repeat(64), status: "active" as const, terminated_at: null,
};

const assessment = (status: "blocked" | "preconditions_satisfied_but_unsupported", reasonCodes: InstallationAdmissionReasonCode[]) => ({
    schema_version: "installation-admission-assessment-v1" as const,
    item_id: "home-assistant", catalog_entry_id: "d5-home-assistant", plan_fingerprint: fingerprint,
    selection_id: selection.selection_id, selected_destination_fingerprint: "a".repeat(64), current_destination_fingerprint: "a".repeat(64),
    interest_fingerprint: "e".repeat(64), assessment_status: status, reason_codes: reasonCodes,
    candidate_eligibility_evaluated: false as const, assessment_fingerprint: "f".repeat(64),
});

describe("ProspectiveDestinationReview", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(listProspectiveInstallationDestinations).mockResolvedValue([destination]);
        vi.mocked(selectProspectiveInstallationDestination).mockResolvedValue(selection);
    });

    it("announces loading, renders only sanitized destination fields, and selects with the exact server tuple", async () => {
        const user = userEvent.setup();
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);
        expect(screen.getByRole("status")).toHaveTextContent("Loading available VMs");
        await user.click(await screen.findByRole("button", { name: "Select VM 101 for assessment" }));
        expect(screen.getByText("Proxmox")).toBeInTheDocument();
        const destinationRow = within(screen.getByRole("list", { name: "VMs available for assessment" })).getByRole("listitem");
        expect(within(destinationRow).getByText("VM ID").parentElement).toHaveTextContent("101");
        expect(document.body).not.toHaveTextContent(/QEMU|prospective installation destination/i);
        expect(selectProspectiveInstallationDestination).toHaveBeenCalledWith(
            { resource_id: "101", enumeration_token: "b".repeat(64) }, "csrf", "mission-control-test-key",
        );
        expect(await screen.findByRole("heading", { name: "VM selected for assessment" })).toBeInTheDocument();
        expect(screen.getByText("This is a temporary choice for a check. Atlas has not confirmed that this VM can run the app. It does not install or approve anything. It does not authorize execution.")).toBeInTheDocument();
        expect(screen.getByText(selection.selection_id)).toBeInTheDocument();
        const selectionDetails = screen.getByText("Selection details").closest("details");
        expect(selectionDetails).not.toHaveAttribute("open");
        expect(within(selectionDetails as HTMLElement).getByText(selection.selection_id)).not.toBeVisible();
        expect(screen.queryByText(destination.destination_fingerprint)).not.toBeInTheDocument();
        expect(screen.queryByText(destination.enumeration_token)).not.toBeInTheDocument();
        expect(document.body).not.toHaveTextContent(/vmgenid|hostname|ip address|docker|compose|credential/i);
    });

    it("keeps the primary label visible while giving each destination a resource-specific accessible name", async () => {
        vi.mocked(listProspectiveInstallationDestinations).mockResolvedValueOnce([destination, secondDestination]);
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);

        expect(await screen.findByRole("button", { name: "Select VM 101 for assessment" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Select VM 202 for assessment" })).toBeInTheDocument();
        expect(screen.getAllByText("Select this VM for assessment", { selector: "button" })).toHaveLength(2);
        expect(screen.queryByRole("button", { name: /^(install|plan|execute|approve|deploy)$/i })).not.toBeInTheDocument();
    });

    it("states that selection is temporary and does not authorize installation", async () => {
        const user = userEvent.setup();
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Select VM 101 for assessment" }));

        expect(await screen.findByText(/temporary choice for a check/i)).toHaveTextContent(/Atlas has not confirmed that this VM can run the app/i);
        expect(screen.getByText(/temporary choice for a check/i)).toHaveTextContent(/does not install or approve anything/i);
        expect(screen.getByText(/temporary choice for a check/i)).toHaveTextContent(/It does not authorize execution/i);
    });

    it("renders bounded empty and API unavailable states", async () => {
        vi.mocked(listProspectiveInstallationDestinations).mockResolvedValueOnce([]);
        const { rerender } = render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);
        expect(await screen.findByText("No existing Proxmox VMs are available to assess.")).toBeInTheDocument();
        vi.mocked(listProspectiveInstallationDestinations).mockRejectedValueOnce(new Error("raw secret"));
        rerender(<ProspectiveDestinationReview key="unavailable" plan={plan} csrfToken="csrf" />);
        expect(await screen.findByRole("alert")).toHaveTextContent("Atlas cannot list available VMs right now.");
        expect(document.body).not.toHaveTextContent("raw secret");
    });

    it("shows a plain selection recovery message and retries the exact request key", async () => {
        const apiError = {
            isAxiosError: true,
            response: { data: { error: { message: "Installation selection request conflicts with current state." } } },
        };
        vi.mocked(installationIdempotencyKey)
            .mockReturnValueOnce("selection-request-key-1")
            .mockReturnValueOnce("selection-request-key-2");
        vi.mocked(listProspectiveInstallationDestinations).mockResolvedValueOnce([destination, secondDestination]);
        vi.mocked(selectProspectiveInstallationDestination).mockRejectedValueOnce(apiError);
        const user = userEvent.setup();
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);

        await user.click(await screen.findByRole("button", { name: "Select VM 101 for assessment" }));

        const message = await screen.findByText("Atlas could not confirm whether it saved this VM selection. Retry the same selection to check its status.");
        const alert = message.closest("[role=alert]") as HTMLElement;
        expect(alert.querySelector(":scope > p")).toHaveTextContent("Atlas could not confirm whether it saved this VM selection.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("Installation selection request conflicts with current state.")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Retry selection — VM 101" })).toBeEnabled();
        expect(screen.getByRole("button", { name: "Select VM 202 for assessment" })).toBeDisabled();
        expect(screen.queryByRole("button", { name: "Check this plan and VM" })).not.toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Retry selection — VM 101" }));
        expect(await screen.findByRole("heading", { name: "VM selected for assessment" })).toBeInTheDocument();
        expect(selectProspectiveInstallationDestination).toHaveBeenNthCalledWith(
            1,
            { resource_id: "101", enumeration_token: "b".repeat(64) },
            "csrf",
            "selection-request-key-1",
        );
        expect(selectProspectiveInstallationDestination).toHaveBeenNthCalledWith(
            2,
            { resource_id: "101", enumeration_token: "b".repeat(64) },
            "csrf",
            "selection-request-key-1",
        );
        expect(installationIdempotencyKey).toHaveBeenCalledTimes(1);
        expect(screen.queryByText("Atlas could not confirm whether it saved this VM selection.")).not.toBeInTheDocument();
    });

    it("shows plain assessment recovery, clears stale results, and reuses its request key", async () => {
        const apiError = {
            isAxiosError: true,
            response: { data: { error: { message: "Installation admission could not be assessed." } } },
        };
        vi.mocked(installationIdempotencyKey)
            .mockReturnValueOnce("selection-request-key")
            .mockReturnValueOnce("assessment-request-key-1")
            .mockReturnValueOnce("assessment-request-key-2")
            .mockReturnValueOnce("assessment-request-key-3");
        vi.mocked(assessInstallationAdmission)
            .mockResolvedValueOnce(assessment("blocked", ["installation_plan_insufficient_information"]))
            .mockRejectedValueOnce(apiError)
            .mockResolvedValueOnce(assessment("blocked", ["installation_plan_insufficient_information"]));
        const user = userEvent.setup();
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);

        await user.click(await screen.findByRole("button", { name: "Select VM 101 for assessment" }));
        await user.click(screen.getByRole("button", { name: "Check this plan and VM" }));
        expect(await screen.findByRole("heading", { name: "Check result" })).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Check this plan and VM" }));

        const message = await screen.findByText("Atlas could not confirm the check result. Retry the same check to retrieve it.");
        const alert = message.closest("[role=alert]") as HTMLElement;
        expect(alert.querySelector(":scope > p")).toHaveTextContent("Atlas could not confirm the check result.");
        expect(screen.queryByRole("heading", { name: "Check result" })).not.toBeInTheDocument();
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("Installation admission could not be assessed.")).toBeInTheDocument();

        const assessmentControls = screen.getByText("This checks the plan and selected VM only. It does not install or authorize anything.").parentElement as HTMLElement;
        await user.click(within(assessmentControls).getByRole("button", { name: "Retry check" }));
        expect(await screen.findByRole("list", { name: "Issues to review" })).toBeInTheDocument();
        expect(assessInstallationAdmission).toHaveBeenNthCalledWith(
            1,
            { item_id: "home-assistant", catalog_entry_id: "d5-home-assistant", plan_fingerprint: fingerprint, selection_id: selection.selection_id },
            "csrf",
            "assessment-request-key-1",
        );
        expect(assessInstallationAdmission).toHaveBeenNthCalledWith(
            2,
            { item_id: "home-assistant", catalog_entry_id: "d5-home-assistant", plan_fingerprint: fingerprint, selection_id: selection.selection_id },
            "csrf",
            "assessment-request-key-2",
        );
        expect(assessInstallationAdmission).toHaveBeenNthCalledWith(
            3,
            { item_id: "home-assistant", catalog_entry_id: "d5-home-assistant", plan_fingerprint: fingerprint, selection_id: selection.selection_id },
            "csrf",
            "assessment-request-key-2",
        );
        expect(installationIdempotencyKey).toHaveBeenCalledTimes(3);
        expect(screen.queryByText("Atlas could not confirm the check result. Retry the same check to retrieve it.")).not.toBeInTheDocument();
    });

    it.each(["cancelled", "expired", "stale"] as const)("shows %s as terminal and disables assessment", async (status) => {
        vi.mocked(selectProspectiveInstallationDestination).mockResolvedValueOnce({ ...selection, status, terminated_at: "2026-08-27T01:00:00Z" });
        const user = userEvent.setup();
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Select VM 101 for assessment" }));
        const expected = {
            cancelled: "Selection was cancelled. Select this VM again to start a new check.",
            expired: "Selection expired. Select this VM again to start a new check.",
            stale: "The destination changed. Select the current VM to start a new check.",
        }[status];
        expect(await screen.findByRole("status")).toHaveTextContent(expected);
        expect(screen.getByRole("button", { name: "Check this plan and VM" })).toBeDisabled();
        expect(screen.getByText("Select a current VM before requesting a check.")).toBeInTheDocument();
    });

    it("posts and renders the Home Assistant golden blocked assessment with all three non-authorizing blockers", async () => {
        vi.mocked(assessInstallationAdmission).mockResolvedValueOnce(assessment("blocked", [
            "installation_plan_missing_deployment_artifact",
            "destination_installation_capability_unknown",
            "agent_install_container_unsupported",
        ]));
        const user = userEvent.setup();
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Select VM 101 for assessment" }));
        await user.click(screen.getByRole("button", { name: "Check this plan and VM" }));
        expect(assessInstallationAdmission).toHaveBeenCalledWith({
            item_id: "home-assistant", catalog_entry_id: "d5-home-assistant", plan_fingerprint: fingerprint,
            selection_id: selection.selection_id,
        }, "csrf", "mission-control-test-key");
        const blockers = await screen.findByRole("list", { name: "Issues to review" });
        expect(within(blockers).getAllByRole("listitem")).toHaveLength(3);
        expect(blockers).toHaveTextContent("Installation file is missing");
        expect(blockers).toHaveTextContent("VM readiness is unknown");
        expect(blockers).toHaveTextContent("Installation planning is not available yet");
        expect(screen.getByRole("status")).toHaveTextContent("Blocked by the issues below");
        expect(screen.getByText("This check did not determine whether the app qualifies for installation or approve an install.")).toBeInTheDocument();
        expect(blockers).not.toHaveTextContent("agent_install_container_unsupported");
    });

    it("distinguishes preconditions satisfied but unsupported without readiness language", async () => {
        vi.mocked(assessInstallationAdmission).mockResolvedValueOnce(assessment("preconditions_satisfied_but_unsupported", [
            "destination_installation_capability_unknown", "agent_install_container_unsupported",
        ]));
        const user = userEvent.setup();
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Select VM 101 for assessment" }));
        await user.click(screen.getByRole("button", { name: "Check this plan and VM" }));
        expect(await screen.findByText("Atlas has not confirmed that this VM can run the app. This check does not authorize an installation.")).toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent("Atlas cannot plan this installation yet");
        expect(screen.getByRole("status")).not.toHaveTextContent("preconditions_satisfied_but_unsupported");
        expect(document.body).not.toHaveTextContent(/\bready\b|\beligible\b|\bapproved\b|\bexecutable\b/i);
    });

    it("provides a human-readable label and diagnostic code for every frozen reason", async () => {
        const codes = Object.keys(REASON_LABELS) as InstallationAdmissionReasonCode[];
        vi.mocked(assessInstallationAdmission).mockResolvedValueOnce(assessment("blocked", codes));
        const user = userEvent.setup();
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Select VM 101 for assessment" }));
        await user.click(screen.getByRole("button", { name: "Check this plan and VM" }));
        const list = await screen.findByRole("list", { name: "Issues to review" });
        expect(within(list).getAllByRole("listitem")).toHaveLength(16);
        const assessmentSummary = screen.getByRole("region", { name: "Check result" });
        const technicalDetails = within(assessmentSummary).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(technicalDetails).not.toBeNull();
        for (const code of codes) {
            expect(within(technicalDetails as HTMLElement).getByText(code)).toBeInTheDocument();
            expect(within(list).queryByText(code)).not.toBeInTheDocument();
            expect(within(list).getByText(REASON_LABELS[code].title, { exact: false })).toBeInTheDocument();
        }
    });

    it("explains the sign-in requirement and exposes no prohibited control or authority navigation", async () => {
        render(<ProspectiveDestinationReview plan={plan} csrfToken={null} />);
        const button = await screen.findByRole("button", { name: "Select VM 101 for assessment" });
        expect(button).toBeDisabled();
        expect(screen.getByText("An authenticated session is required to save a VM selection.")).toBeInTheDocument();
        expect(screen.queryByRole("link")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /^(install|execute|deploy|approve|plan|convert|dispatch|run|apply)$/i })).not.toBeInTheDocument();
    });
});
