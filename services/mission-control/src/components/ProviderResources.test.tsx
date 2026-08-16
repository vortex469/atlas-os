import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError, AxiosHeaders } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getAuthenticatedProviderManagement,
    getProviderManagement,
    putProviderMonitoringIntent,
} from "../api/providerManagement";
import { getProviderMonitoringIntentSuggestions } from "../api/providerIntentSuggestions";
import { getProviderResources, refreshProviderResources } from "../api/resources";
import { useOperatorSession } from "../hooks/operatorSessionContext";
import type { Provider } from "../types/provider";
import type { ProviderManagementV2, ProviderManagementV3, ProviderMonitoringIntentSuggestionV1 } from "../types/providerManagement";
import type { ProviderResourceCollection } from "../types/resources";
import { ProviderResources } from "./ProviderResources";
import {
    composeProviderResources,
    monitoringPresentation,
} from "./providerResourceComposition";

vi.mock("../api/providerManagement", () => ({
    getAuthenticatedProviderManagement: vi.fn(),
    getProviderManagement: vi.fn(),
    putProviderMonitoringIntent: vi.fn(),
}));
vi.mock("../api/resources", () => ({
    getProviderResources: vi.fn(),
    refreshProviderResources: vi.fn(),
}));
vi.mock("../api/providerIntentSuggestions", () => ({
    getProviderMonitoringIntentSuggestions: vi.fn(),
}));
vi.mock("../hooks/operatorSessionContext", () => ({ useOperatorSession: vi.fn() }));
vi.mock("../api/atlas", () => ({
    getAtlasErrorMessage: (_error: unknown, fallback: string) => fallback,
}));

const fingerprint: ProviderMonitoringIntentSuggestionV1["management_fingerprint"] = `provider-management-fingerprint-v1:${"a".repeat(64)}`;
const replacementFingerprint: ProviderMonitoringIntentSuggestionV1["management_fingerprint"] = `provider-management-fingerprint-v1:${"b".repeat(64)}`;
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

function suggestion(overrides: Partial<ProviderMonitoringIntentSuggestionV1> = {}): ProviderMonitoringIntentSuggestionV1 {
    return {
        schema_version: "provider-monitoring-intent-suggestion-v1",
        suggestion_id: `provider-monitoring-intent-suggestion-id-v1:${"c".repeat(64)}`,
        provider_id: "proxmox",
        resource_type: "qemu",
        resource_id: "110",
        management_fingerprint: fingerprint,
        suggested_expectation: "running",
        base_record_version: 0,
        source: "provider_intelligence_rule",
        source_rule: "qemu-observed-running-no-active-intent-v1",
        reason: "observed_running_without_active_intent",
        advisory_only: true,
        grants_permission: false,
        grants_execution: false,
        ...overrides,
    };
}

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

function publicManagement(overrides: Partial<ProviderManagementV2["resources"][number]> = {}): ProviderManagementV2 {
    const source = management().resources[0];
    return {
        schema_version: "provider-management-v2",
        provider_id: "proxmox",
        provider_name: "Proxmox",
        sections: [],
        resource_types: [],
        provider_intent_activation: "activated",
        provider_intent_authority_status: "available",
        grants_permission: false,
        grants_execution: false,
        resources: [{
            provider_id: source.provider_id,
            resource_id: source.resource_id,
            resource_type: source.resource_type,
            display_name: source.display_name,
            current_state: source.current_state,
            missing: source.missing,
            identity_assurance: source.identity_assurance,
            management_fingerprint: source.management_fingerprint,
            intent_authority: source.intent_authority,
            intent_status: source.intent_status,
            intent_reason: source.intent_reason,
            expectation: source.expectation,
            record_version: source.record_version,
            legacy_review_available: source.legacy_review_available,
            legacy_expectation: source.legacy_expectation,
            replacement_detected: source.replacement_detected,
            mutation_available: false,
            operationally_requestable: false,
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
        vi.mocked(getProviderManagement).mockResolvedValue(publicManagement());
        vi.mocked(getAuthenticatedProviderManagement).mockResolvedValue(management());
        vi.mocked(getProviderMonitoringIntentSuggestions).mockResolvedValue([]);
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
        expect(getProviderResources).toHaveBeenCalledTimes(1);
        expect(getProviderManagement).toHaveBeenCalledTimes(2);
        expect(getAuthenticatedProviderManagement).toHaveBeenCalledTimes(2);
    });

    it("reviews advisory state locally and mutates only on explicit Save", async () => {
        const user = userEvent.setup();
        vi.mocked(getProviderMonitoringIntentSuggestions)
            .mockResolvedValueOnce([suggestion()])
            .mockResolvedValueOnce([]);
        vi.mocked(getProviderManagement)
            .mockResolvedValueOnce(publicManagement())
            .mockResolvedValueOnce(publicManagement({
                intent_status: "configured",
                intent_reason: "matching_active_intent",
                expectation: "running",
                record_version: 1,
            }));
        await renderResources();
        expect(screen.getByText("Not configured")).toBeInTheDocument();
        expect(screen.getByText("Running", { selector: "dd" })).toBeInTheDocument();
        expect(screen.getByLabelText(/monitoring expectation/i)).toHaveValue("");
        expect(putProviderMonitoringIntent).not.toHaveBeenCalled();

        await user.click(screen.getByRole("button", { name: "Review suggestion" }));
        expect(screen.getByLabelText(/monitoring expectation/i)).toHaveValue("running");
        expect(screen.getByText("Not configured")).toBeInTheDocument();
        expect(putProviderMonitoringIntent).not.toHaveBeenCalled();

        await user.click(screen.getByRole("button", { name: "Save" }));
        await waitFor(() => expect(putProviderMonitoringIntent).toHaveBeenCalledTimes(1));
        expect(await screen.findByText("Expected running")).toBeInTheDocument();
        expect(screen.queryByText("Advisory suggestion")).not.toBeInTheDocument();
    });

    it("allows manual override after review", async () => {
        const user = userEvent.setup();
        vi.mocked(getProviderMonitoringIntentSuggestions).mockResolvedValue([suggestion()]);
        await renderResources();
        await user.click(screen.getByRole("button", { name: "Review suggestion" }));
        await user.selectOptions(screen.getByLabelText(/monitoring expectation/i), "stopped");
        await user.click(screen.getByRole("button", { name: "Save" }));
        await waitFor(() => expect(putProviderMonitoringIntent).toHaveBeenCalledTimes(1));
        expect(putProviderMonitoringIntent).toHaveBeenCalledWith(
            "proxmox", "qemu", "110",
            expect.objectContaining({ expectation: "stopped" }),
            "csrf",
        );
    });

    it("shows a stale fingerprint without review or prefill", async () => {
        vi.mocked(getProviderMonitoringIntentSuggestions).mockResolvedValue([
            suggestion({ management_fingerprint: replacementFingerprint }),
        ]);
        await renderResources();
        expect(screen.getByText(/different resource incarnation/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review suggestion" })).not.toBeInTheDocument();
        expect(screen.getByLabelText(/monitoring expectation/i)).toHaveValue("");
        expect(putProviderMonitoringIntent).not.toHaveBeenCalled();
    });

    it("clears reviewed state when identity changes before Save", async () => {
        const user = userEvent.setup();
        vi.mocked(getProviderMonitoringIntentSuggestions)
            .mockResolvedValueOnce([suggestion()])
            .mockResolvedValueOnce([]);
        vi.mocked(getProviderManagement)
            .mockResolvedValueOnce(publicManagement())
            .mockResolvedValueOnce(publicManagement({ management_fingerprint: replacementFingerprint }));
        vi.mocked(getAuthenticatedProviderManagement)
            .mockResolvedValueOnce(management())
            .mockResolvedValueOnce(management({ management_fingerprint: replacementFingerprint }));
        await renderResources();
        await user.click(screen.getByRole("button", { name: "Review suggestion" }));
        expect(screen.getByLabelText(/monitoring expectation/i)).toHaveValue("running");
        await user.click(screen.getByRole("button", { name: "Refresh resources" }));
        expect(await screen.findByText(/different resource incarnation/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/monitoring expectation/i)).toHaveValue("");
        expect(putProviderMonitoringIntent).not.toHaveBeenCalled();
    });

    it("requires a renewed explicit choice when intent configures after review", async () => {
        const user = userEvent.setup();
        vi.mocked(getProviderMonitoringIntentSuggestions)
            .mockResolvedValueOnce([suggestion()])
            .mockResolvedValueOnce([]);
        vi.mocked(getProviderManagement)
            .mockResolvedValueOnce(publicManagement())
            .mockResolvedValueOnce(publicManagement({
                intent_status: "configured",
                intent_reason: "matching_active_intent",
                expectation: "running",
                record_version: 1,
            }));
        vi.mocked(getAuthenticatedProviderManagement)
            .mockResolvedValueOnce(management())
            .mockResolvedValueOnce(management({
                intent_status: "configured",
                intent_reason: "matching_active_intent",
                expectation: "running",
                record_version: 1,
            }));
        await renderResources();
        await user.click(screen.getByRole("button", { name: "Review suggestion" }));
        await user.click(screen.getByRole("button", { name: "Refresh resources" }));
        expect(await screen.findByText("Expected running")).toBeInTheDocument();
        expect(screen.getByLabelText(/monitoring expectation/i)).toHaveValue("");
        expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
        expect(putProviderMonitoringIntent).not.toHaveBeenCalled();
    });

    it("does not treat suggestion review as ignored acknowledgement", async () => {
        const user = userEvent.setup();
        vi.mocked(getProviderMonitoringIntentSuggestions).mockResolvedValue([suggestion()]);
        await renderResources();
        await user.click(screen.getByRole("button", { name: "Review suggestion" }));
        await user.selectOptions(screen.getByLabelText(/monitoring expectation/i), "ignored");
        const acknowledgement = screen.getByRole("checkbox", { name: /I understand monitoring findings/i });
        expect(acknowledgement).not.toBeChecked();
        expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
        await user.click(acknowledgement);
        expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
        expect(putProviderMonitoringIntent).not.toHaveBeenCalled();
    });

    it("keeps suggestions reviewable but mutation unavailable without permission", async () => {
        const user = userEvent.setup();
        vi.mocked(getProviderMonitoringIntentSuggestions).mockResolvedValue([suggestion()]);
        vi.mocked(getAuthenticatedProviderManagement).mockResolvedValue(management({ caller_can_mutate: false }));
        render(<ProviderResources provider={provider} />);
        await user.click(await screen.findByRole("button", { name: "Review suggestion" }));
        expect(screen.getByText(/selected for local review/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
        expect(putProviderMonitoringIntent).not.toHaveBeenCalled();
    });

    it("keeps advisory review visible but editing unavailable when v3 fails", async () => {
        vi.mocked(getProviderMonitoringIntentSuggestions).mockResolvedValue([suggestion()]);
        vi.mocked(getAuthenticatedProviderManagement).mockRejectedValue(new Error("offline"));
        render(<ProviderResources provider={provider} />);
        expect(await screen.findByText("Advisory suggestion")).toBeInTheDocument();
        expect(screen.getByText("Not configured")).toBeInTheDocument();
        expect(screen.getByText(/operator capability could not be loaded/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
        expect(putProviderMonitoringIntent).not.toHaveBeenCalled();
    });

    it("preserves authoritative monitoring when suggestion loading fails", async () => {
        vi.mocked(getProviderMonitoringIntentSuggestions).mockRejectedValue(new Error("offline"));
        render(<ProviderResources provider={provider} />);
        expect(await screen.findByText("Not configured")).toBeInTheDocument();
        expect(screen.getByText(/suggestions could not be loaded/i)).toBeInTheDocument();
        expect(screen.queryByText("Advisory suggestion")).not.toBeInTheDocument();
        expect(screen.getByLabelText(/monitoring expectation/i)).toHaveValue("");
    });

    it("reports suggestion refresh failure without reporting mutation failure", async () => {
        const user = userEvent.setup();
        vi.mocked(getProviderMonitoringIntentSuggestions)
            .mockResolvedValueOnce([suggestion()])
            .mockRejectedValueOnce(new Error("offline"));
        vi.mocked(getProviderManagement)
            .mockResolvedValueOnce(publicManagement())
            .mockResolvedValueOnce(publicManagement({
                intent_status: "configured",
                intent_reason: "matching_active_intent",
                expectation: "running",
                record_version: 1,
            }));
        await renderResources();
        await user.click(screen.getByRole("button", { name: "Review suggestion" }));
        await user.click(screen.getByRole("button", { name: "Save" }));
        expect(await screen.findByText(/saved and confirmed.*suggestions could not be refreshed/i)).toBeInTheDocument();
        expect(screen.queryByText(/could not save the monitoring expectation/i)).not.toBeInTheDocument();
        expect(await screen.findByText("Expected running")).toBeInTheDocument();
        expect(screen.getByText(/different resource incarnation or monitoring state/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review suggestion" })).not.toBeInTheDocument();
    });

    it("associates a QEMU suggestion by exact type when LXC has the same ID", async () => {
        const lxcInventory = { ...inventory.resources[0], resource_type: "lxc", display_name: "Container" };
        const lxcManagement = {
            ...publicManagement().resources[0],
            resource_type: "lxc",
            display_name: "Container",
            identity_assurance: "unsupported" as const,
            management_fingerprint: null,
            intent_status: "unsupported" as const,
            intent_reason: "resource_type_unsupported" as const,
        };
        vi.mocked(getProviderResources).mockResolvedValue({
            ...inventory,
            resources: [lxcInventory, inventory.resources[0]],
        });
        vi.mocked(getProviderManagement).mockResolvedValue({
            ...publicManagement(),
            resources: [lxcManagement, publicManagement().resources[0]],
        });
        vi.mocked(getProviderMonitoringIntentSuggestions).mockResolvedValue([suggestion()]);
        render(<ProviderResources provider={provider} />);
        const qemu = await screen.findByTestId("resource-row-qemu-110");
        const lxc = screen.getByTestId("resource-row-lxc-110");
        expect(within(qemu).getByText("Advisory suggestion")).toBeInTheDocument();
        expect(within(lxc).queryByText("Advisory suggestion")).not.toBeInTheDocument();
    });

    it("keeps reviewed selection local to its exact QEMU coordinate", async () => {
        const user = userEvent.setup();
        const qemu200Inventory = { ...inventory.resources[0], resource_id: "200", display_name: "PBS", metadata: { vmid: 200, node: "vorex469" } };
        const qemu200Public = { ...publicManagement().resources[0], resource_id: "200", display_name: "PBS" };
        const qemu200Operator = { ...management().resources[0], resource_id: "200", display_name: "PBS" };
        vi.mocked(getProviderResources).mockResolvedValue({ ...inventory, resources: [inventory.resources[0], qemu200Inventory] });
        vi.mocked(getProviderManagement).mockResolvedValue({ ...publicManagement(), resources: [publicManagement().resources[0], qemu200Public] });
        vi.mocked(getAuthenticatedProviderManagement).mockResolvedValue({ ...management(), resources: [management().resources[0], qemu200Operator] });
        vi.mocked(getProviderMonitoringIntentSuggestions).mockResolvedValue([suggestion()]);
        render(<ProviderResources provider={provider} />);
        const qemu110 = await screen.findByTestId("resource-row-qemu-110");
        const qemu200 = screen.getByTestId("resource-row-qemu-200");
        await user.click(within(qemu110).getByRole("button", { name: "Review suggestion" }));
        expect(within(qemu110).getByLabelText(/monitoring expectation/i)).toHaveValue("running");
        expect(within(qemu200).getByLabelText(/monitoring expectation/i)).toHaveValue("");
        expect(within(qemu200).queryByText("Advisory suggestion")).not.toBeInTheDocument();
        expect(putProviderMonitoringIntent).not.toHaveBeenCalled();
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
            await waitFor(() => expect(getProviderManagement).toHaveBeenCalledTimes(2));
            expect(getAuthenticatedProviderManagement).toHaveBeenCalledTimes(2);
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
        vi.mocked(getProviderManagement)
            .mockResolvedValueOnce(publicManagement())
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
        await user.click(screen.getByRole("button", { name: "Refresh resources" }));
        await waitFor(() => expect(refreshProviderResources).toHaveBeenCalledWith("proxmox"));
        expect(getProviderManagement).toHaveBeenCalledTimes(2);
        expect(getAuthenticatedProviderManagement).toHaveBeenCalledTimes(2);
    });

    it("uses public v2 instead of the legacy inventory expectation", async () => {
        vi.mocked(getProviderResources).mockResolvedValue({
            ...inventory,
            resources: [{
                ...inventory.resources[0],
                current_state: "stopped",
                expectation: {
                    value: "stopped",
                    label: "Expected Stopped",
                    state: "configured",
                    allowed_values: [],
                },
            }],
        });
        vi.mocked(getProviderManagement).mockResolvedValue(publicManagement({
            intent_status: "configured",
            intent_reason: "matching_active_intent",
            expectation: "running",
            record_version: 1,
        }));
        render(<ProviderResources provider={provider} />);
        expect(await screen.findByText("Expected running")).toBeInTheDocument();
        expect(screen.getByText("Configured — does not match observed state")).toBeInTheDocument();
        expect(screen.queryByText("Expected stopped")).not.toBeInTheDocument();
    });

    it("shows public monitoring anonymously without requesting v3", async () => {
        vi.mocked(useOperatorSession).mockReturnValue({
            authenticated: false,
            principal: null,
            csrfToken: null,
            loading: false,
            error: null,
            login: vi.fn(),
            logout: vi.fn(),
            invalidate,
        });
        vi.mocked(getProviderManagement).mockResolvedValue(publicManagement({
            intent_status: "configured",
            intent_reason: "matching_active_intent",
            expectation: "running",
            record_version: 1,
        }));
        render(<ProviderResources provider={provider} />);
        expect(await screen.findByText("Expected running")).toBeInTheDocument();
        expect(screen.getByText(/Sign in with Provider Intent permission/)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
        expect(getAuthenticatedProviderManagement).not.toHaveBeenCalled();
        expect(getProviderMonitoringIntentSuggestions).not.toHaveBeenCalled();
    });

    it("preserves public monitoring when authenticated v3 fails", async () => {
        vi.mocked(getProviderManagement).mockResolvedValue(publicManagement({
            intent_status: "configured",
            intent_reason: "matching_active_intent",
            expectation: "running",
            record_version: 1,
        }));
        vi.mocked(getAuthenticatedProviderManagement).mockRejectedValue(new Error("offline"));
        render(<ProviderResources provider={provider} />);
        expect(await screen.findByText("Expected running")).toBeInTheDocument();
        expect(screen.getByText(/operator capability could not be loaded/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    });

    it("invalidates a 401 v3 read while preserving public monitoring", async () => {
        vi.mocked(getProviderManagement).mockResolvedValue(publicManagement({
            intent_status: "configured",
            intent_reason: "matching_active_intent",
            expectation: "running",
            record_version: 1,
        }));
        vi.mocked(getAuthenticatedProviderManagement).mockRejectedValue(httpError(401, "unauthorized"));
        render(<ProviderResources provider={provider} />);
        expect(await screen.findByText("Expected running")).toBeInTheDocument();
        await waitFor(() => expect(invalidate).toHaveBeenCalledOnce());
        expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    });

    it("preserves inventory and does not fall back to its expectation when v2 fails", async () => {
        vi.mocked(getProviderManagement).mockRejectedValue(new Error("offline"));
        render(<ProviderResources provider={provider} />);
        expect(await screen.findByText("Frigate")).toBeInTheDocument();
        expect(screen.getByText("Monitoring unavailable", { selector: "p.font-semibold" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    });

    it("does not present management current_state as observed when inventory fails", async () => {
        vi.mocked(getProviderResources).mockRejectedValue(new Error("offline"));
        vi.mocked(getProviderManagement).mockResolvedValue(publicManagement({
            intent_status: "configured",
            intent_reason: "matching_active_intent",
            expectation: "running",
            record_version: 1,
        }));
        render(<ProviderResources provider={provider} />);
        expect(await screen.findByText("Expected running")).toBeInTheDocument();
        const row = screen.getByTestId("resource-row-qemu-110");
        expect(row).toHaveTextContent("Observed stateUnavailable");
        expect(row).toHaveTextContent("Configured — does not match observed state");
    });

    it("keeps an unauthorized v3 overlay read-only without changing public state", async () => {
        vi.mocked(getProviderManagement).mockResolvedValue(publicManagement({
            intent_status: "configured",
            intent_reason: "matching_active_intent",
            expectation: "running",
            record_version: 1,
        }));
        vi.mocked(getAuthenticatedProviderManagement).mockResolvedValue(management({ caller_can_mutate: false }));
        render(<ProviderResources provider={provider} />);
        expect(await screen.findByText("Expected running")).toBeInTheDocument();
        expect(screen.getByText(/does not permit Provider Intent updates/)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    });
});

describe("ProviderResources exact-coordinate composition", () => {
    it("isolates QEMU and LXC with the same numeric ID", () => {
        const lxcInventory = { ...inventory.resources[0], resource_type: "lxc", display_name: "Container" };
        const lxcManagement = {
            ...publicManagement().resources[0],
            resource_type: "lxc",
            display_name: "Container",
            identity_assurance: "unsupported" as const,
            intent_status: "unsupported" as const,
            intent_reason: "resource_type_unsupported" as const,
            management_fingerprint: null,
        };
        const result = composeProviderResources(
            { ...inventory, resources: [inventory.resources[0], lxcInventory] },
            { ...publicManagement(), resources: [publicManagement().resources[0], lxcManagement] },
            null,
        );
        expect(result).toHaveLength(2);
        expect(result.map((entry) => entry.inventory?.resource_type)).toEqual(["lxc", "qemu"]);
        expect(result[0].management?.identity_assurance).toBe("unsupported");
        expect(result[1].management?.identity_assurance).toBe("authoritative");
    });

    it("fails closed on duplicate exact management coordinates", () => {
        const descriptor = publicManagement();
        expect(() => composeProviderResources(inventory, {
            ...descriptor,
            resources: [descriptor.resources[0], descriptor.resources[0]],
        }, null)).toThrow(/duplicated/);
    });

    it("marks an inventory/management type disagreement inconsistent", () => {
        const descriptor = publicManagement();
        const result = composeProviderResources(inventory, {
            ...descriptor,
            resources: [{ ...descriptor.resources[0], resource_type: "lxc" }],
        }, null);
        expect(result.find((entry) => entry.inventory)?.inconsistent).toBe(true);
        expect(result.find((entry) => entry.inventory)?.operator).toBeNull();
    });
});

describe("ProviderResources bounded monitoring presentation", () => {
    it.each([
        ["running", "running", "Configured — matches observed state"],
        ["stopped", "stopped", "Configured — matches observed state"],
        ["running", "stopped", "Configured — does not match observed state"],
        ["stopped", "running", "Configured — does not match observed state"],
        ["ignored", "running", "Configured — monitoring ignored"],
    ] as const)("derives configured %s against observed %s", (expectation, observed, status) => {
        const resource = publicManagement({
            intent_status: "configured",
            intent_reason: "matching_active_intent",
            expectation,
            record_version: 1,
        }).resources[0];
        expect(monitoringPresentation(resource, observed, false).status).toBe(status);
    });

    it.each([
        ["no_active_intent", "Needs Review — monitoring expectation not configured"],
        ["legacy_unbound_evidence", "Needs Review — historical expectation available for review"],
        ["incarnation_mismatch", "Needs Review — resource incarnation changed"],
        ["identity_unavailable", "Needs Review — authoritative identity unavailable"],
        ["authority_store_unavailable", "Monitoring unavailable — Provider Intent authority could not be read"],
        ["resource_missing", "Resource missing — retained expectation does not describe a current live identity"],
        ["resource_type_unsupported", "Unsupported for identity-bound monitoring"],
    ] as const)("maps %s to bounded operator text", (reason, status) => {
        const resource = publicManagement({
            intent_status: reason === "resource_missing" ? "missing" : reason === "resource_type_unsupported" ? "unsupported" : reason === "authority_store_unavailable" ? "unavailable" : "needs_review",
            intent_reason: reason,
        }).resources[0];
        expect(monitoringPresentation(resource, "running", false).status).toBe(status);
    });
});
