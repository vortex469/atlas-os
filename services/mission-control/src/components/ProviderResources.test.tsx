import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError, AxiosHeaders } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getAuthenticatedProviderManagement,
    putProviderMonitoringIntent,
} from "../api/providerManagement";
import { getProviderResources, refreshProviderResources } from "../api/resources";
import { useOperatorSession } from "../hooks/operatorSessionContext";
import type { Provider } from "../types/provider";
import type { ProviderManagementV3 } from "../types/providerManagement";
import type { ProviderResourceCollection } from "../types/resources";
import { ProviderResources } from "./ProviderResources";

vi.mock("../api/providerManagement", () => ({
    getAuthenticatedProviderManagement: vi.fn(),
    putProviderMonitoringIntent: vi.fn(),
}));
vi.mock("../api/resources", () => ({
    getProviderResources: vi.fn(),
    refreshProviderResources: vi.fn(),
}));
vi.mock("../hooks/operatorSessionContext", () => ({ useOperatorSession: vi.fn() }));
vi.mock("../api/atlas", () => ({
    getAtlasErrorMessage: (_error: unknown, fallback: string) => fallback,
}));

const fingerprint = `provider-management-fingerprint-v1:${"a".repeat(64)}`;
const invalidate = vi.fn();
const provider: Provider = {
    id: "proxmox",
    name: "Proxmox",
    workspace: "operations",
    priority: "critical",
    version: "1",
    description: "Virtualization",
    icon: "server",
    capabilities: ["resources"],
    health: { status: "online", latency_ms: null, http_status: null, message: null, details: {} },
};
const inventory: ProviderResourceCollection = {
    provider_id: "proxmox",
    provider_name: "Proxmox",
    refreshed_at: "2026-08-16T00:00:00Z",
    resources: [{
        provider_id: "proxmox",
        resource_id: "110",
        display_name: "Frigate",
        resource_type: "qemu",
        current_state: "running",
        expectation: { value: null, label: "Needs Review", state: "needs_review", allowed_values: [] },
        configured: false,
        missing: false,
        needs_review: true,
        metadata: { vmid: 110, node: "vorex469" },
    }],
    summary: { total: 1, configured: 0, needs_review: 1, missing: 0, ignored: 0, by_type: { qemu: 1 }, by_state: { running: 1 } },
    metadata: {},
};

function management(overrides: Partial<ProviderManagementV3["resources"][number]> = {}): ProviderManagementV3 {
    return {
        schema_version: "provider-management-v3",
        provider_id: "proxmox",
        provider_name: "Proxmox",
        sections: [],
        resource_types: [],
        provider_intent_activation: "activated",
        provider_intent_authority_status: "available",
        caller_has_provider_intent_update: true,
        grants_permission: false,
        grants_execution: false,
        resources: [{
            provider_id: "proxmox",
            resource_id: "110",
            resource_type: "qemu",
            display_name: "Frigate",
            current_state: "running",
            missing: false,
            resource_live: true,
            identity_assurance: "authoritative",
            management_fingerprint: fingerprint,
            intent_authority: "provider_intent",
            intent_status: "needs_review",
            intent_reason: "no_active_intent",
            expectation: null,
            record_version: null,
            legacy_review_available: false,
            legacy_expectation: null,
            replacement_detected: false,
            provider_intent_mutation_supported: true,
            mutation_readiness: "ready",
            editable_in_principle: true,
            caller_can_mutate: true,
            operationally_requestable: false,
            grants_permission: false,
            grants_execution: false,
            ...overrides,
        }],
    };
}

function httpError(status: number, detail: string): AxiosError {
    return new AxiosError("failed", "ERR_BAD_RESPONSE", undefined, undefined, {
        data: { detail }, status, statusText: "failed", headers: {}, config: { headers: new AxiosHeaders() },
    });
}

async function renderResources() {
    render(<ProviderResources provider={provider} />);
    await screen.findByText("Frigate");
    await screen.findByLabelText(/monitoring expectation/i);
}

describe("ProviderResources Provider Intent flow", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(useOperatorSession).mockReturnValue({
            authenticated: true,
            principal: null,
            csrfToken: "csrf",
            loading: false,
            error: null,
            login: vi.fn(),
            logout: vi.fn(),
            invalidate,
        });
        vi.mocked(getProviderResources).mockResolvedValue(inventory);
        vi.mocked(refreshProviderResources).mockResolvedValue(inventory);
        vi.mocked(getAuthenticatedProviderManagement).mockResolvedValue(management());
        vi.mocked(putProviderMonitoringIntent).mockResolvedValue({
            outcome: "created",
            request_id: `provider-intent-mutation-${"b".repeat(32)}`,
            provider_id: "proxmox",
            resource_type: "qemu",
            resource_id: "110",
            management_fingerprint: fingerprint,
            expectation: "running",
            record_version: 1,
            superseded_previous_incarnation: false,
        });
        vi.stubGlobal("crypto", { randomUUID: () => "12345678-1234-1234-1234-123456789abc" });
    });

    it("saves through only the P3b API and reloads server projections", async () => {
        const user = userEvent.setup();
        await renderResources();
        await user.selectOptions(screen.getByLabelText(/monitoring expectation/i), "running");
        await user.click(screen.getByRole("button", { name: "Save" }));
        await waitFor(() => expect(putProviderMonitoringIntent).toHaveBeenCalledTimes(1));
        expect(putProviderMonitoringIntent).toHaveBeenCalledWith(
            "proxmox", "qemu", "110",
            {
                request_id: "provider-intent-mutation-12345678123412341234123456789abc",
                expected_management_fingerprint: fingerprint,
                expectation: "running",
                expected_record_version: 0,
                acknowledge_monitoring_suppression: false,
            },
            "csrf",
        );
        await waitFor(() => expect(getProviderResources).toHaveBeenCalledTimes(2));
        expect(getAuthenticatedProviderManagement).toHaveBeenCalledTimes(2);
    });

    it.each([
        [409, "cas_conflict", "intent changed"],
        [409, "fingerprint_mismatch", "identity changed"],
        [409, "request_conflict", "save request is stale"],
        [403, "permission_missing", "does not permit"],
        [422, "invalid_request", "request is invalid"],
        [429, "rate_limited", "rate limited"],
        [503, "store_migration_required", "awaiting migration"],
    ] as const)("handles %s %s without retry", async (status, detail, message) => {
        const user = userEvent.setup();
        vi.mocked(putProviderMonitoringIntent).mockRejectedValue(httpError(status, detail));
        await renderResources();
        await user.selectOptions(screen.getByLabelText(/monitoring expectation/i), "running");
        await user.click(screen.getByRole("button", { name: "Save" }));
        expect(await screen.findByText(message, { exact: false })).toBeInTheDocument();
        expect(putProviderMonitoringIntent).toHaveBeenCalledTimes(1);
        if (detail === "cas_conflict" || detail === "fingerprint_mismatch") {
            await waitFor(() => expect(getAuthenticatedProviderManagement).toHaveBeenCalledTimes(2));
            expect(screen.getByLabelText(/monitoring expectation/i)).toHaveValue("");
        }
    });

    it("invalidates a rejected operator session", async () => {
        const user = userEvent.setup();
        vi.mocked(putProviderMonitoringIntent).mockRejectedValue(httpError(401, "unauthorized"));
        await renderResources();
        await user.selectOptions(screen.getByLabelText(/monitoring expectation/i), "running");
        await user.click(screen.getByRole("button", { name: "Save" }));
        expect(await screen.findByText(/sign in again/i)).toBeInTheDocument();
        expect(invalidate).toHaveBeenCalledOnce();
    });

    it("renders schema migration required as read-only without calling mutation", async () => {
        vi.mocked(getAuthenticatedProviderManagement).mockResolvedValue(management({
            mutation_readiness: "store_migration_required",
            editable_in_principle: false,
            caller_can_mutate: false,
        }));
        render(<ProviderResources provider={provider} />);
        expect(await screen.findByText(/awaiting a store migration/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
        expect(putProviderMonitoringIntent).not.toHaveBeenCalled();
    });

    it("reports committed save separately when authoritative reload fails", async () => {
        const user = userEvent.setup();
        vi.mocked(getProviderResources)
            .mockResolvedValueOnce(inventory)
            .mockRejectedValueOnce(new Error("reload failed"));
        await renderResources();
        await user.selectOptions(screen.getByLabelText(/monitoring expectation/i), "running");
        await user.click(screen.getByRole("button", { name: "Save" }));
        expect(await screen.findByText(/was saved, but refreshed server state/i)).toBeInTheDocument();
        expect(putProviderMonitoringIntent).toHaveBeenCalledTimes(1);
    });

    it("refreshes inventory and authenticated management together", async () => {
        const user = userEvent.setup();
        await renderResources();
        await user.click(screen.getByRole("button", { name: "Refresh Inventory" }));
        await waitFor(() => expect(refreshProviderResources).toHaveBeenCalledWith("proxmox"));
        expect(getAuthenticatedProviderManagement).toHaveBeenCalledTimes(2);
    });
});
