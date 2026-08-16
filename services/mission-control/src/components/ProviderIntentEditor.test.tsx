import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ManagedProviderResourceV3 } from "../types/providerManagement";
import { ProviderIntentEditor } from "./ProviderIntentEditor";

const fingerprint = `provider-management-fingerprint-v1:${"a".repeat(64)}`;

function resource(
    overrides: Partial<ManagedProviderResourceV3> = {},
): ManagedProviderResourceV3 {
    return {
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
    };
}

function renderEditor(value = resource(), onSave = vi.fn()) {
    render(
        <ProviderIntentEditor
            resource={value}
            saving={false}
            onSave={onSave}
        />,
    );
    return onSave;
}

describe("ProviderIntentEditor", () => {
    it("requires an explicit Needs Review choice and Save", async () => {
        const user = userEvent.setup();
        const save = renderEditor();
        const select = screen.getByLabelText(/monitoring expectation/i);
        expect(select).toHaveValue("");
        expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
        await user.selectOptions(select, "running");
        await user.click(screen.getByRole("button", { name: "Save" }));
        expect(save).toHaveBeenCalledWith("running", false);
    });

    it("does not preselect legacy evidence", () => {
        renderEditor(resource({
            legacy_review_available: true,
            legacy_expectation: "stopped",
            intent_reason: "legacy_unbound_evidence",
        }));
        expect(screen.getByText("Previous legacy expectation: Stopped")).toBeInTheDocument();
        expect(screen.getByLabelText(/monitoring expectation/i)).toHaveValue("");
    });

    it("requires explicit ignored acknowledgement", async () => {
        const user = userEvent.setup();
        const save = renderEditor();
        await user.selectOptions(screen.getByLabelText(/monitoring expectation/i), "ignored");
        const button = screen.getByRole("button", { name: "Save" });
        expect(button).toBeDisabled();
        await user.click(screen.getByRole("checkbox"));
        await user.click(button);
        expect(save).toHaveBeenCalledWith("ignored", true);
    });

    it("shows configured value and permits explicit same-value reauthorization", async () => {
        const user = userEvent.setup();
        const save = renderEditor(resource({
            intent_status: "configured",
            intent_reason: "matching_active_intent",
            expectation: "running",
            record_version: 3,
        }));
        const select = screen.getByLabelText(/monitoring expectation/i);
        expect(select).toHaveValue("running");
        await user.click(screen.getByRole("button", { name: "Save" }));
        expect(save).toHaveBeenCalledWith("running", false);
    });

    it("shows replacement warning without copying the old expectation", () => {
        renderEditor(resource({
            intent_reason: "incarnation_mismatch",
            replacement_detected: true,
            expectation: "running",
        }));
        expect(screen.getByRole("alert")).toHaveTextContent("old intent does not apply");
        expect(screen.getByLabelText(/monitoring expectation/i)).toHaveValue("");
    });

    it.each([
        ["resource_type_unsupported", "unsupported for this resource type"],
        ["resource_missing", "Missing resources cannot be edited"],
        ["identity_unavailable", "Authoritative QEMU identity is unavailable"],
        ["authority_unavailable", "authority is temporarily unavailable"],
        ["store_migration_required", "awaiting a store migration"],
    ] as const)("keeps %s read-only", (readiness, message) => {
        renderEditor(resource({
            editable_in_principle: false,
            caller_can_mutate: false,
            mutation_readiness: readiness,
        }));
        expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
        expect(screen.getByText(message, { exact: false })).toBeInTheDocument();
    });

    it("keeps an unauthorized ready resource read-only", () => {
        renderEditor(resource({ caller_can_mutate: false }));
        expect(screen.getByText(/does not permit Provider Intent updates/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    });

    it("fails closed when caller capability contradicts resource safety fields", () => {
        renderEditor(resource({
            caller_can_mutate: true,
            editable_in_principle: false,
            mutation_readiness: "identity_unavailable",
            identity_assurance: "unavailable",
            management_fingerprint: null,
        }));
        expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    });

    it("clears ignored acknowledgement when selection changes", async () => {
        const user = userEvent.setup();
        renderEditor();
        const select = screen.getByLabelText(/monitoring expectation/i);
        await user.selectOptions(select, "ignored");
        await user.click(screen.getByRole("checkbox"));
        await user.selectOptions(select, "running");
        await user.selectOptions(select, "ignored");
        expect(screen.getByRole("checkbox")).not.toBeChecked();
        expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    });
});
