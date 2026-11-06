import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getCapabilityResources,
    getOperationalCapabilities,
    requestRestartServiceIntent,
} from "../api/operatorIntent";
import { getDiscoveryProposal } from "../api/discovery";
import { useOperatorSession } from "../hooks/operatorSessionContext";
import type { OperatorIntentCreationResponse, OperatorIntentResource } from "../types/operatorIntent";
import { MaintenanceRequestPage } from "./MaintenanceRequestPage";

vi.mock("../api/operatorIntent", () => ({
    getCapabilityResources: vi.fn(),
    getOperationalCapabilities: vi.fn(),
    requestRestartServiceIntent: vi.fn(),
}));
vi.mock("../api/discovery", () => ({ getDiscoveryProposal: vi.fn() }));
vi.mock("../hooks/operatorSessionContext", () => ({ useOperatorSession: vi.fn() }));

const requestable: OperatorIntentResource = {
    provider_id: "proxmox",
    resource_id: "110",
    resource_type: "qemu",
    display_name: "Frigate",
    node: "vorex469",
    current_state: "running",
    authoritative_identity_present: true,
    template: false,
    locked: false,
    migrating: false,
    operational_target_fingerprint: "operational-target-fingerprint-v1:abc",
    requestable: true,
    reason: null,
};

const unavailable: OperatorIntentResource = {
    ...requestable,
    resource_id: "111",
    display_name: "Stopped VM",
    current_state: "stopped",
    requestable: false,
    reason: "stopped",
};

function authenticated(invalidate = vi.fn()) {
    vi.mocked(useOperatorSession).mockReturnValue({
        authenticated: true,
        principal: {
            operator_id: "kenny",
            authenticated_at: "2026-08-14T00:00:00Z",
            permissions: ["operational_intent:create"],
            auth_method: "core_session",
        },
        csrfToken: "csrf-in-memory",
        loading: false,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        invalidate,
    });
}

function renderPage(state?: unknown) {
    render(<MemoryRouter initialEntries={[{ pathname: "/operations/request", state }]}><Routes><Route path="/operations/request" element={<MaintenanceRequestPage />} /><Route path="/operator/login" element={<LoginDestination />} /><Route path="/execution-candidates" element={<p>Change proposal list</p>} /><Route path="/execution-candidates/:candidateId" element={<p>Candidate destination</p>} /></Routes></MemoryRouter>);
}

function LoginDestination() {
    return <><p>Login destination</p><output data-testid="login-context">{JSON.stringify(useLocation().state)}</output></>;
}

function createdCandidate(): OperatorIntentCreationResponse {
    return {
            outcome: "created",
            candidate_id: "candidate-operator-intent-110",
            candidate: {
                effect_kind: "operational_action",
                id: "candidate-operator-intent-110",
                source_recommendation_id: "operator-intent-record-1",
                source_subsystem: "operator-intent",
                recommendation_class: "restart-service",
                target_id: "110",
                target_type: "qemu",
                execution_category: "restart",
                execution_intent: "restart-service",
                status: "eligible",
                required_approval_level: "standard",
                rationale: "Bounded maintenance.",
                constraints: ["service-disruption"],
                evidence_ids: [],
                relationship_ids: [],
                created_at: "2026-08-14T00:00:00Z",
                expires_at: "2999-08-14T00:15:00Z",
            },
        };
}

describe("MaintenanceRequestPage", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        authenticated();
        vi.mocked(getOperationalCapabilities).mockResolvedValue({ capabilities: [{
            capability_id: "restart-service--proxmox--qemu",
            execution_intent: "restart-service",
            provider_id: "proxmox",
            resource_type: "qemu",
            effect_kind: "operational_action",
            required_approval_level: "standard",
            selector_available: true,
            selector_kind: "authoritative_resource",
            selector_id: "restart-service--proxmox--qemu",
            disruption_kind: "brief_service_interruption",
            verification_kind: "authoritative_state_and_health",
            core_gate_enabled: true,
            handler_registered: true,
            production_enabled: true,
            consistency: "consistent",
            label: "Restart service",
            description: "Graceful restart.",
        }] });
        vi.mocked(getCapabilityResources).mockResolvedValue({
            execution_intent: "restart-service",
            provider_id: "proxmox",
            resource_type: "qemu",
            generated_at: "2026-08-14T00:00:00Z",
            resources: [requestable, unavailable],
        });
        vi.mocked(requestRestartServiceIntent).mockResolvedValue(createdCandidate());
    });

    it("renders fixed semantics and disables non-requestable resources", async () => {
        renderPage();
        expect(await screen.findByRole("heading", { name: "Request a VM restart" })).toBeVisible();
        expect(await screen.findByText("Frigate")).toBeInTheDocument();
        expect(screen.getByText(/sends your request for separate review and approval/i)).toBeInTheDocument();
        expect(screen.getByText("Restart service")).toBeInTheDocument();
        expect(screen.getByText("Proxmox")).toBeInTheDocument();
        expect(screen.getByText("VM type")).toBeInTheDocument();
        expect(screen.getByText("Virtual machine")).toBeInTheDocument();
        expect(screen.queryByText("QEMU")).not.toBeInTheDocument();
        expect(screen.getByText(/^VM ID\s*110$/)).toBeInTheDocument();
        expect(screen.getAllByText(/^Host\s*vorex469$/)).toHaveLength(2);
        expect(screen.getByText("Stopped")).toBeInTheDocument();
        expect(screen.getByText("This VM is stopped. Select a running VM to request a restart.")).toBeInTheDocument();
        expect(screen.getByRole("radio", { name: /Stopped VM/i })).toBeDisabled();
        expect(screen.queryByText(/vmgenid|identity token|provider action/i)).not.toBeInTheDocument();
    });

    it("explains when no VMs are available and keeps Refresh as the recovery", async () => {
        vi.mocked(getCapabilityResources).mockResolvedValueOnce({
            execution_intent: "restart-service",
            provider_id: "proxmox",
            resource_type: "qemu",
            generated_at: "2026-08-14T00:00:00Z",
            resources: [],
        });
        renderPage();

        const resources = screen.getByRole("region", { name: "Available virtual machines" });
        expect(within(resources).getByRole("status")).toHaveTextContent("Loading available VMs…");
        expect(within(resources).getByRole("button", { name: "Refresh" })).toBeDisabled();
        expect(within(resources).queryByText("No VMs are available to select right now. Use Refresh to check again.")).not.toBeInTheDocument();
        expect(await within(resources).findByText("No VMs are available to select right now. Use Refresh to check again.")).toBeVisible();
        expect(screen.getByRole("button", { name: "Refresh" })).toBeEnabled();
        expect(screen.getByRole("button", { name: "Submit restart request" })).toBeDisabled();
        expect(within(resources).queryByRole("radio")).not.toBeInTheDocument();
    });

    it("does not leave a loading placeholder when no restart capability is available", async () => {
        vi.mocked(getOperationalCapabilities).mockResolvedValue({ capabilities: [] });
        renderPage();

        expect(await screen.findByRole("alert")).toHaveTextContent("Restart requests are not available right now.");
        expect(screen.queryByText("Loading capability")).not.toBeInTheDocument();
        expect(screen.queryByRole("radio")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Submit restart request" })).toBeDisabled();
    });

    it.each([
        ["identity_unavailable", "Atlas could not confirm this VM’s identity."],
        ["unsupported_resource_type", "This resource type cannot be restarted here."],
        ["stopped", "This VM is stopped. Select a running VM to request a restart."],
        ["template", "Templates cannot be restarted."],
        ["locked", "This VM is locked in Proxmox."],
        ["migrating", "This VM is moving between hosts."],
        ["unavailable_state", "Atlas could not confirm this VM’s current state."],
        [null, "This VM cannot be selected for a restart."],
    ] as const)("explains why a resource with reason %s cannot be selected", async (reason, message) => {
        vi.mocked(getCapabilityResources).mockResolvedValueOnce({
            execution_intent: "restart-service",
            provider_id: "proxmox",
            resource_type: "qemu",
            generated_at: "2026-08-14T00:00:00Z",
            resources: [{ ...unavailable, reason }],
        });
        renderPage();
        expect(await screen.findByText(message)).toBeInTheDocument();
    });

    it("submits the exact selected resource and CAS then hands off", async () => {
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("radio", { name: /Frigate/i }));
        await user.click(screen.getByRole("button", { name: "Submit restart request" }));
        await waitFor(() => expect(requestRestartServiceIntent).toHaveBeenCalledWith(
            "110",
            "operational-target-fingerprint-v1:abc",
            "csrf-in-memory",
        ));
        expect(requestRestartServiceIntent).toHaveBeenCalledTimes(1);
        expect(await screen.findByRole("heading", { name: "Restart request ready for review" })).toBeInTheDocument();
        expect(screen.getByText("Request for Frigate is ready. The VM has not restarted.")).toBeInTheDocument();
        expect(screen.getByText("Expected impact: brief service interruption.")).toBeInTheDocument();
        expect(screen.getByText(/Expires .* UTC/)).toBeInTheDocument();
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect(technicalDetails?.open).toBe(false);
        expect(screen.getByRole("link", { name: "Review request" })).toHaveAttribute(
            "href",
            "/execution-candidates/candidate-operator-intent-110",
        );
        fireEvent.click(screen.getByText("Technical details"));
        expect(technicalDetails?.open).toBe(true);
        expect(within(technicalDetails!).getByText("candidate-operator-intent-110")).toBeInTheDocument();
        expect(within(technicalDetails!).getByText("eligible")).toBeInTheDocument();
    });

    it("shows advisory context without selecting or submitting from proposal hints", async () => {
        const proposalId = `discovery-operator-proposal-${"a".repeat(64)}`;
        vi.mocked(getDiscoveryProposal).mockResolvedValue({
            proposal_id: proposalId,
            destination_kind: "operator_maintenance_selection",
            catalog_item_id: "frigate",
            catalog_source_type: "curated",
            compatibility_status: "compatible",
            finding_reference_count: 1,
            evidence_reference_count: 2,
            status: "current",
            reason: "compatible",
            intent_hint: "restart-service",
            target_hints: [{ catalog_target_id: "999", provider_hint: "attacker", resource_type_hint: "lxc" }],
            generated_at: "2026-08-15T00:00:00Z",
            expires_at: "2026-08-15T00:30:00Z",
            actionable_navigation: true,
        });

        renderPage({ proposalId, provider: "attacker", fingerprint: "tampered" });

        expect(await screen.findByRole("heading", { name: "Suggestion details" })).toBeInTheDocument();
        expect(screen.getByText("Atlas will not choose a VM from this suggestion. Select a running VM below.")).toBeInTheDocument();
        expect(await screen.findByText("999 / attacker / lxc")).toBeInTheDocument();
        expect(screen.getByRole("radio", { name: /Frigate/i })).not.toBeChecked();
        expect(requestRestartServiceIntent).not.toHaveBeenCalled();
        expect(getOperationalCapabilities).toHaveBeenCalledTimes(1);
        expect(getCapabilityResources).toHaveBeenCalledWith("restart-service--proxmox--qemu");
    });

    it("locks target selection and refresh while the exact request is pending", async () => {
        let resolve!: (value: OperatorIntentCreationResponse) => void;
        vi.mocked(requestRestartServiceIntent).mockImplementation(() => new Promise((done) => { resolve = done; }));
        renderPage();
        const target = await screen.findByRole("radio", { name: /Frigate/i });
        fireEvent.click(target);
        fireEvent.click(screen.getByRole("button", { name: "Submit restart request" }));
        expect(target).toBeDisabled();
        expect(screen.getByRole("button", { name: "Refresh" })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Sending restart request…" })).toBeDisabled();
        await act(async () => resolve(createdCandidate()));
        expect(screen.getByRole("link", { name: "Review request" })).toBeInTheDocument();
        expect(requestRestartServiceIntent).toHaveBeenCalledTimes(1);
    });

    it("clears the old proposal and requires reselection when refreshing resources", async () => {
        renderPage();
        const target = await screen.findByRole("radio", { name: /Frigate/i });
        fireEvent.click(target);
        fireEvent.click(screen.getByRole("button", { name: "Submit restart request" }));
        await screen.findByRole("link", { name: "Review request" });
        fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
        expect(screen.queryByRole("link", { name: "Review request" })).not.toBeInTheDocument();
        await waitFor(() => expect(getCapabilityResources).toHaveBeenCalledTimes(2));
        expect(await screen.findByRole("radio", { name: /Frigate/i })).not.toBeChecked();
        expect(screen.getByRole("button", { name: "Submit restart request" })).toBeDisabled();
    });

    it.each(["candidate_id", "target_id", "execution_intent"])("refuses a proposal with a mismatched %s", async (field) => {
        const response = createdCandidate();
        if (field === "candidate_id") response.candidate_id = "foreign-candidate";
        else if (field === "target_id") response.candidate.target_id = "999";
        else response.candidate.execution_intent = "update-compose-stack";
        vi.mocked(requestRestartServiceIntent).mockResolvedValue(response);
        renderPage();
        fireEvent.click(await screen.findByRole("radio", { name: /Frigate/i }));
        fireEvent.click(screen.getByRole("button", { name: "Submit restart request" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("Atlas returned details for a different request. The VM has not restarted. Check Change proposals before trying again.");
        expect(screen.getByRole("link", { name: "Open Change proposals" })).toHaveAttribute("href", "/execution-candidates");
        expect(screen.getByRole("radio", { name: /Frigate/i })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Refresh" })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Submit restart request" })).toBeDisabled();
        expect(screen.queryByRole("link", { name: "Review request" })).not.toBeInTheDocument();
        expect(requestRestartServiceIntent).toHaveBeenCalledTimes(1);
    });

    it("clears the previous proposal when another resource is selected", async () => {
        vi.mocked(getCapabilityResources).mockResolvedValue({ execution_intent: "restart-service", provider_id: "proxmox", resource_type: "qemu",
            generated_at: "2026-08-14T00:00:00Z", resources: [requestable, { ...requestable, resource_id: "111", display_name: "Other VM" }] });
        renderPage();
        fireEvent.click(await screen.findByRole("radio", { name: /Frigate/i }));
        fireEvent.click(screen.getByRole("button", { name: "Submit restart request" }));
        await screen.findByRole("link", { name: "Review request" });
        fireEvent.click(screen.getByRole("radio", { name: /Other VM/ }));
        expect(screen.queryByRole("link", { name: "Review request" })).not.toBeInTheDocument();
        expect(screen.queryByRole("region", { name: "Restart request ready" })).not.toBeInTheDocument();
        expect(requestRestartServiceIntent).toHaveBeenCalledTimes(1);
    });

    it("does not offer the previous resource list when refreshing fails", async () => {
        renderPage();
        await screen.findByRole("radio", { name: /Frigate/i });
        vi.mocked(getOperationalCapabilities).mockRejectedValueOnce(new Error("Unavailable"));
        fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("Available VMs could not be loaded. Use Refresh to try again.");
        expect(screen.queryByRole("radio")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Submit restart request" })).toBeDisabled();
        expect(requestRestartServiceIntent).not.toHaveBeenCalled();
    });

    it("describes a resource-list read failure without implying a request was submitted", async () => {
        vi.mocked(getCapabilityResources).mockRejectedValueOnce(new Error("Resource service unavailable"));
        renderPage();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Available VMs could not be loaded. Use Refresh to try again.");
        expect(alert).not.toHaveTextContent("maintenance request could not be completed");
        expect(screen.queryByRole("radio")).not.toBeInTheDocument();
        expect(requestRestartServiceIntent).not.toHaveBeenCalled();
    });

    it("ignores malformed proposal route state and never posts automatically", async () => {
        renderPage({ proposalId: "../../tampered", targetHint: "111" });
        await screen.findByText("Frigate");
        expect(getDiscoveryProposal).not.toHaveBeenCalled();
        expect(requestRestartServiceIntent).not.toHaveBeenCalled();
    });

    it("shows proposal-not-found separately without weakening the selector", async () => {
        const proposalId = `discovery-operator-proposal-${"d".repeat(64)}`;
        vi.mocked(getDiscoveryProposal).mockRejectedValue({ isAxiosError: true, response: { status: 404 } });
        renderPage({ proposalId });
        expect(await screen.findByRole("alert")).toHaveTextContent("This suggestion is no longer available.");
        expect(screen.queryByRole("button", { name: "Retry loading suggestion" })).not.toBeInTheDocument();
        expect(await screen.findByText("Frigate")).toBeInTheDocument();
        expect(requestRestartServiceIntent).not.toHaveBeenCalled();
    });

    it("retries a temporary suggestion read without reloading or selecting a VM", async () => {
        const user = userEvent.setup();
        const proposalId = `discovery-operator-proposal-${"f".repeat(64)}`;
        let resolveRetry!: (value: Awaited<ReturnType<typeof getDiscoveryProposal>>) => void;
        vi.mocked(getDiscoveryProposal).mockRejectedValueOnce(new Error("temporary read failure")).mockImplementationOnce(() => new Promise((resolve) => { resolveRetry = resolve; }));
        const currentSuggestion = {
            proposal_id: proposalId,
            destination_kind: "operator_maintenance_selection",
            catalog_item_id: "frigate",
            catalog_source_type: "curated",
            compatibility_status: "compatible",
            finding_reference_count: 1,
            evidence_reference_count: 2,
            status: "current",
            reason: "compatible",
            intent_hint: "restart-service",
            target_hints: [],
            generated_at: "2026-08-15T00:00:00Z",
            expires_at: "2026-08-15T00:30:00Z",
            actionable_navigation: true,
        } as Awaited<ReturnType<typeof getDiscoveryProposal>>;

        renderPage({ proposalId });
        expect(await screen.findByRole("alert")).toHaveTextContent("Suggestion details could not be loaded.");
        await user.click(screen.getByRole("button", { name: "Retry loading suggestion" }));
        expect(await screen.findByText("Loading suggestion details…")).toBeInTheDocument();
        await act(async () => resolveRetry(currentSuggestion));
        expect(await screen.findByText("Suggestion status: Current")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Retry loading suggestion" })).not.toBeInTheDocument();
        expect(getDiscoveryProposal).toHaveBeenCalledTimes(2);
        expect(getCapabilityResources).toHaveBeenCalledTimes(1);
        expect(screen.getByRole("radio", { name: /Frigate/i })).not.toBeChecked();
        expect(requestRestartServiceIntent).not.toHaveBeenCalled();
    });

    it("requires login before loading proposal or maintenance authority", async () => {
        vi.mocked(useOperatorSession).mockReturnValue({
            authenticated: false,
            principal: null,
            csrfToken: null,
            loading: false,
            error: null,
            login: vi.fn(),
            logout: vi.fn(),
            invalidate: vi.fn(),
        });
        const proposalId = `discovery-operator-proposal-${"e".repeat(64)}`;
        renderPage({ proposalId, resourceId: "999", approved: true });
        expect(await screen.findByText("Login destination")).toBeInTheDocument();
        expect(JSON.parse(screen.getByTestId("login-context").textContent!)).toEqual({ proposalId });
        expect(getDiscoveryProposal).not.toHaveBeenCalled();
        expect(getOperationalCapabilities).not.toHaveBeenCalled();
        expect(requestRestartServiceIntent).not.toHaveBeenCalled();
    });

    it.each([
        [403, "does not have permission"],
        [429, "Too many maintenance requests"],
        [503, "Atlas could not confirm whether your restart request was received"],
    ])("renders controlled status %i without automatic retry", async (status, message) => {
        vi.mocked(requestRestartServiceIntent).mockRejectedValue({ isAxiosError: true, response: { status } });
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("radio", { name: /Frigate/i }));
        await user.click(screen.getByRole("button", { name: "Submit restart request" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(message);
        expect(requestRestartServiceIntent).toHaveBeenCalledTimes(1);
        if (status === 503) {
            expect(screen.getByRole("link", { name: "Open Change proposals" })).toHaveAttribute("href", "/execution-candidates");
        }
    });

    it("directs an uncertain proposal response to read existing proposals without resubmitting", async () => {
        vi.mocked(requestRestartServiceIntent).mockRejectedValueOnce(new Error("Network unavailable"));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("radio", { name: /Frigate/i }));
        await user.click(screen.getByRole("button", { name: "Submit restart request" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Atlas could not confirm whether your restart request was received. The VM has not restarted. Check Change proposals before trying again.");
        expect(screen.getByRole("radio", { name: /Frigate/i })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Refresh" })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Submit restart request" })).toBeDisabled();
        await user.click(screen.getByRole("link", { name: "Open Change proposals" }));
        expect(await screen.findByText("Change proposal list")).toBeInTheDocument();
        expect(requestRestartServiceIntent).toHaveBeenCalledTimes(1);
    });

    it("refreshes and requires reselection after a stale CAS conflict", async () => {
        vi.mocked(requestRestartServiceIntent).mockRejectedValue({ isAxiosError: true, response: { status: 409 } });
        const user = userEvent.setup();
        renderPage();
        const radio = await screen.findByRole("radio", { name: /Frigate/i });
        await user.click(radio);
        await user.click(screen.getByRole("button", { name: "Submit restart request" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("This VM changed.");
        expect(getCapabilityResources).toHaveBeenCalledTimes(2);
        expect(await screen.findByRole("radio", { name: /Frigate/i })).not.toBeChecked();
    });

    it("does not hand an expired proposal to planning", async () => {
        vi.mocked(requestRestartServiceIntent).mockResolvedValue({
            outcome: "created",
            candidate_id: "candidate-expired",
            candidate: {
                effect_kind: "operational_action",
                id: "candidate-expired",
                source_recommendation_id: "operator-intent-record-1",
                source_subsystem: "operator-intent",
                recommendation_class: "restart-service",
                target_id: "110",
                target_type: "qemu",
                execution_category: "restart",
                execution_intent: "restart-service",
                status: "eligible",
                required_approval_level: "standard",
                rationale: "Expired.",
                constraints: ["service-disruption"],
                evidence_ids: [],
                relationship_ids: [],
                created_at: "2000-01-01T00:00:00Z",
                expires_at: "2000-01-01T00:15:00Z",
            },
        });
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("radio", { name: /Frigate/i }));
        await user.click(screen.getByRole("button", { name: "Submit restart request" }));
        expect(await screen.findByText(/restart request has expired/i)).toBeInTheDocument();
        expect(screen.queryByRole("link", { name: "Review request" })).not.toBeInTheDocument();
    });

    it("returns to login on 401", async () => {
        const invalidate = vi.fn();
        authenticated(invalidate);
        vi.mocked(getOperationalCapabilities).mockRejectedValue({ isAxiosError: true, response: { status: 401 } });
        renderPage();
        await waitFor(() => expect(invalidate).toHaveBeenCalled());
    });
});
