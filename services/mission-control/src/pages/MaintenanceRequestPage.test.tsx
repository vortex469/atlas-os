import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getCapabilityResources,
    getOperationalCapabilities,
    requestRestartServiceIntent,
} from "../api/operatorIntent";
import { getDiscoveryProposal } from "../api/discovery";
import { useOperatorSession } from "../hooks/operatorSessionContext";
import type { OperatorIntentResource } from "../types/operatorIntent";
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
    render(<MemoryRouter initialEntries={[{ pathname: "/operations/request", state }]}><Routes><Route path="/operations/request" element={<MaintenanceRequestPage />} /><Route path="/operator/login" element={<p>Login destination</p>} /><Route path="/execution-candidates/:candidateId" element={<p>Candidate destination</p>} /></Routes></MemoryRouter>);
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
        vi.mocked(requestRestartServiceIntent).mockResolvedValue({
            outcome: "created",
            candidate_id: "candidate-operator-intent-110",
            candidate: {
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
        });
    });

    it("renders fixed semantics and disables non-requestable resources", async () => {
        renderPage();
        expect(await screen.findByText("Frigate")).toBeInTheDocument();
        expect(screen.getByText("Restart service")).toBeInTheDocument();
        expect(screen.getByText("Proxmox")).toBeInTheDocument();
        expect(screen.getByText("QEMU")).toBeInTheDocument();
        expect(screen.getByText("Unavailable: stopped")).toBeInTheDocument();
        expect(screen.getByRole("radio", { name: /Stopped VM/i })).toBeDisabled();
        expect(screen.queryByText(/vmgenid|identity token|provider action/i)).not.toBeInTheDocument();
    });

    it("submits the exact selected resource and CAS then hands off", async () => {
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("radio", { name: /Frigate/i }));
        await user.click(screen.getByRole("button", { name: "Request restart candidate" }));
        await waitFor(() => expect(requestRestartServiceIntent).toHaveBeenCalledWith(
            "110",
            "operational-target-fingerprint-v1:abc",
            "csrf-in-memory",
        ));
        expect(requestRestartServiceIntent).toHaveBeenCalledTimes(1);
        expect(await screen.findByText(/Candidate ID: candidate-operator-intent-110/)).toBeInTheDocument();
        expect(screen.getByText("Expected disruption: brief service interruption")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Continue to candidate planning" })).toHaveAttribute(
            "href",
            "/execution-candidates/candidate-operator-intent-110",
        );
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

        expect(await screen.findByRole("heading", { name: "Advisory proposal context" })).toBeInTheDocument();
        expect(await screen.findByText("999 / attacker / lxc")).toBeInTheDocument();
        expect(screen.getByRole("radio", { name: /Frigate/i })).not.toBeChecked();
        expect(requestRestartServiceIntent).not.toHaveBeenCalled();
        expect(getOperationalCapabilities).toHaveBeenCalledTimes(1);
        expect(getCapabilityResources).toHaveBeenCalledWith("restart-service--proxmox--qemu");
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
        expect(await screen.findByRole("alert")).toHaveTextContent("advisory proposal was not found");
        expect(await screen.findByText("Frigate")).toBeInTheDocument();
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
        renderPage({ proposalId: `discovery-operator-proposal-${"e".repeat(64)}` });
        expect(await screen.findByText("Login destination")).toBeInTheDocument();
        expect(getDiscoveryProposal).not.toHaveBeenCalled();
        expect(getOperationalCapabilities).not.toHaveBeenCalled();
        expect(requestRestartServiceIntent).not.toHaveBeenCalled();
    });

    it.each([
        [403, "lacks maintenance permission"],
        [429, "rate limited"],
        [503, "temporarily unavailable"],
    ])("renders controlled status %i without automatic retry", async (status, message) => {
        vi.mocked(requestRestartServiceIntent).mockRejectedValue({ isAxiosError: true, response: { status } });
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("radio", { name: /Frigate/i }));
        await user.click(screen.getByRole("button", { name: "Request restart candidate" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(message);
        expect(requestRestartServiceIntent).toHaveBeenCalledTimes(1);
    });

    it("refreshes and requires reselection after a stale CAS conflict", async () => {
        vi.mocked(requestRestartServiceIntent).mockRejectedValue({ isAxiosError: true, response: { status: 409 } });
        const user = userEvent.setup();
        renderPage();
        const radio = await screen.findByRole("radio", { name: /Frigate/i });
        await user.click(radio);
        await user.click(screen.getByRole("button", { name: "Request restart candidate" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("resource changed");
        expect(getCapabilityResources).toHaveBeenCalledTimes(2);
        expect(radio).not.toBeChecked();
    });

    it("does not hand an expired candidate to planning", async () => {
        vi.mocked(requestRestartServiceIntent).mockResolvedValue({
            outcome: "created",
            candidate_id: "candidate-expired",
            candidate: {
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
        await user.click(screen.getByRole("button", { name: "Request restart candidate" }));
        expect(await screen.findByText(/candidate has expired/i)).toBeInTheDocument();
        expect(screen.queryByRole("link", { name: "Continue to candidate planning" })).not.toBeInTheDocument();
    });

    it("returns to login on 401", async () => {
        const invalidate = vi.fn();
        authenticated(invalidate);
        vi.mocked(getOperationalCapabilities).mockRejectedValue({ isAxiosError: true, response: { status: 401 } });
        renderPage();
        await waitFor(() => expect(invalidate).toHaveBeenCalled());
    });
});
