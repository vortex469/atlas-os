import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { InstallationPlan } from "../../types/installationPlan";
import type { InstallationAdmissionReasonCode } from "../../types/installationDestination";
import {
    assessInstallationAdmission,
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
        expect(screen.getByRole("status")).toHaveTextContent("Loading prospective installation destinations");
        await user.click(await screen.findByRole("button", { name: "Select as prospective installation destination — QEMU resource 101" }));
        expect(screen.getByText("Proxmox")).toBeInTheDocument();
        expect(screen.getByText("QEMU", { selector: "dd" })).toBeInTheDocument();
        expect(screen.getByText("existing guest")).toBeInTheDocument();
        expect(selectProspectiveInstallationDestination).toHaveBeenCalledWith(
            { resource_id: "101", enumeration_token: "b".repeat(64) }, "csrf", "mission-control-test-key",
        );
        expect(await screen.findByRole("heading", { name: "Immutable selection summary" })).toBeInTheDocument();
        expect(screen.getByText(selection.selection_id)).toBeInTheDocument();
        expect(screen.queryByText(destination.destination_fingerprint)).not.toBeInTheDocument();
        expect(screen.queryByText(destination.enumeration_token)).not.toBeInTheDocument();
        expect(document.body).not.toHaveTextContent(/vmgenid|hostname|ip address|docker|compose|credential/i);
    });

    it("keeps the primary label visible while giving each destination a resource-specific accessible name", async () => {
        vi.mocked(listProspectiveInstallationDestinations).mockResolvedValueOnce([destination, secondDestination]);
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);

        expect(await screen.findByRole("button", { name: "Select as prospective installation destination — QEMU resource 101" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Select as prospective installation destination — QEMU resource 202" })).toBeInTheDocument();
        expect(screen.getAllByText("Select as prospective installation destination", { selector: "button" })).toHaveLength(2);
        expect(screen.queryByRole("button", { name: /^(install|plan|execute|approve|deploy)$/i })).not.toBeInTheDocument();
    });

    it("states that selection cannot install or plan and preserves all non-authority disclaimers", async () => {
        const user = userEvent.setup();
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Select as prospective installation destination — QEMU resource 101" }));

        expect(await screen.findByText(/cannot install or plan the application/i)).toHaveTextContent(/does not approve installation/i);
        expect(screen.getByText(/cannot install or plan the application/i)).toHaveTextContent(/does not prove the guest is installable/i);
        expect(screen.getByText(/cannot install or plan the application/i)).toHaveTextContent(/does not authorize execution/i);
    });

    it("renders bounded empty and API unavailable states", async () => {
        vi.mocked(listProspectiveInstallationDestinations).mockResolvedValueOnce([]);
        const { rerender } = render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);
        expect(await screen.findByText("No prospective installation destinations are currently available.")).toBeInTheDocument();
        vi.mocked(listProspectiveInstallationDestinations).mockRejectedValueOnce(new Error("raw secret"));
        rerender(<ProspectiveDestinationReview key="unavailable" plan={plan} csrfToken="csrf" />);
        expect(await screen.findByRole("alert")).toHaveTextContent("Prospective installation destinations are currently unavailable.");
        expect(document.body).not.toHaveTextContent("raw secret");
    });

    it.each(["cancelled", "expired", "stale"] as const)("shows %s as terminal and disables assessment", async (status) => {
        vi.mocked(selectProspectiveInstallationDestination).mockResolvedValueOnce({ ...selection, status, terminated_at: "2026-08-27T01:00:00Z" });
        const user = userEvent.setup();
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Select as prospective installation destination — QEMU resource 101" }));
        expect(await screen.findByText(new RegExp(`terminal selection — ${status}`, "i"))).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Assess installation admission" })).toBeDisabled();
        expect(screen.getByText(/requires a current active prospective destination selection/i)).toBeInTheDocument();
    });

    it("posts and renders the Home Assistant golden blocked assessment with all three non-authorizing blockers", async () => {
        vi.mocked(assessInstallationAdmission).mockResolvedValueOnce(assessment("blocked", [
            "installation_plan_missing_deployment_artifact",
            "destination_installation_capability_unknown",
            "agent_install_container_unsupported",
        ]));
        const user = userEvent.setup();
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Select as prospective installation destination — QEMU resource 101" }));
        await user.click(screen.getByRole("button", { name: "Assess installation admission" }));
        expect(assessInstallationAdmission).toHaveBeenCalledWith({
            item_id: "home-assistant", catalog_entry_id: "d5-home-assistant", plan_fingerprint: fingerprint,
            selection_id: selection.selection_id,
        }, "csrf", "mission-control-test-key");
        const blockers = await screen.findByRole("list", { name: "Installation admission blockers" });
        expect(within(blockers).getAllByRole("listitem")).toHaveLength(3);
        expect(blockers).toHaveTextContent("Installation plan missing deployment artifact");
        expect(blockers).toHaveTextContent("has not established in-guest installability, runtime, transport, or readiness");
        expect(blockers).toHaveTextContent("Atlas Agent cannot plan this install intent yet");
        expect(screen.getByText(/Candidate eligibility evaluated: false/)).toBeInTheDocument();
    });

    it("distinguishes preconditions satisfied but unsupported without readiness language", async () => {
        vi.mocked(assessInstallationAdmission).mockResolvedValueOnce(assessment("preconditions_satisfied_but_unsupported", [
            "destination_installation_capability_unknown", "agent_install_container_unsupported",
        ]));
        const user = userEvent.setup();
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Select as prospective installation destination — QEMU resource 101" }));
        await user.click(screen.getByRole("button", { name: "Assess installation admission" }));
        expect(await screen.findByText(/installation capability and Agent support remain unavailable/i)).toBeInTheDocument();
        expect(document.body).not.toHaveTextContent(/\bready\b|\beligible\b|\bapproved\b|\bexecutable\b/i);
    });

    it("provides a human-readable label and diagnostic code for every frozen reason", async () => {
        const codes = Object.keys(REASON_LABELS) as InstallationAdmissionReasonCode[];
        vi.mocked(assessInstallationAdmission).mockResolvedValueOnce(assessment("blocked", codes));
        const user = userEvent.setup();
        render(<ProspectiveDestinationReview plan={plan} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Select as prospective installation destination — QEMU resource 101" }));
        await user.click(screen.getByRole("button", { name: "Assess installation admission" }));
        const list = await screen.findByRole("list", { name: "Installation admission blockers" });
        expect(within(list).getAllByRole("listitem")).toHaveLength(16);
        for (const code of codes) expect(list).toHaveTextContent(code);
    });

    it("explains disabled mutation protection and exposes no prohibited control or authority navigation", async () => {
        render(<ProspectiveDestinationReview plan={plan} csrfToken={null} />);
        const button = await screen.findByRole("button", { name: "Select as prospective installation destination — QEMU resource 101" });
        expect(button).toBeDisabled();
        expect(screen.getByText(/authenticated operator session with mutation protection is required/i)).toBeInTheDocument();
        expect(screen.queryByRole("link")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /^(install|execute|deploy|approve|plan|convert|dispatch|run|apply)$/i })).not.toBeInTheDocument();
    });
});
