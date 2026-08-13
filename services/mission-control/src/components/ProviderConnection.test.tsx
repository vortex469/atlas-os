import {
    render,
    screen,
    waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getProviderConnection,
    testProviderConnection,
    updateProviderConnection,
} from "../api/connections";
import type {
    ProviderConnectionField,
    ProviderConnectionSchema,
} from "../types/connections";
import type { Provider } from "../types/provider";
import { ProviderConnection } from "./ProviderConnection";

vi.mock("../api/atlas", () => ({
    getAtlasErrorMessage: (
        error: unknown,
        fallback: string,
    ) => (error instanceof Error ? error.message : fallback),
}));

vi.mock("../api/connections", () => ({
    getProviderConnection: vi.fn(),
    testProviderConnection: vi.fn(),
    updateProviderConnection: vi.fn(),
}));

const mockedGetProviderConnection = vi.mocked(getProviderConnection);
const mockedTestProviderConnection = vi.mocked(testProviderConnection);
const mockedUpdateProviderConnection = vi.mocked(updateProviderConnection);

const provider: Provider = {
    id: "proxmox",
    name: "Proxmox",
    workspace: "operations",
    priority: "critical",
    version: "1.0.0",
    description: "Virtualization provider.",
    icon: "server",
    capabilities: ["health", "connection", "resources"],
    health: {
        status: "online",
        latency_ms: null,
        http_status: null,
        message: null,
        details: {},
    },
};

const noConnectionProvider: Provider = {
    ...provider,
    id: "hermes",
    name: "Hermes",
    capabilities: ["health", "resources"],
};

function field(
    overrides: Partial<ProviderConnectionField>,
): ProviderConnectionField {
    return {
        key: "host",
        label: "Host",
        kind: "host",
        required: true,
        editable: true,
        secret: false,
        current_value: "10.10.50.10",
        secret_state: null,
        source: "atlas_yaml",
        help_text: "",
        options: [],
        validation: {},
        ...overrides,
    };
}

function proxmoxSchema(
    overrides: Partial<ProviderConnectionSchema> = {},
): ProviderConnectionSchema {
    return {
        provider_id: "proxmox",
        provider_name: "Proxmox",
        editable: true,
        testable: true,
        updated_at: "2026-08-01T20:00:00Z",
        metadata: {},
        fields: [
            field({ key: "host", label: "Host", kind: "host", current_value: "10.10.50.10" }),
            field({ key: "port", label: "Port", kind: "port", current_value: 8006, validation: { min: 1, max: 65535 } }),
            field({ key: "node", label: "Node", kind: "string", current_value: "vorex469" }),
            field({ key: "verify_tls", label: "Verify TLS", kind: "boolean", current_value: false }),
            field({ key: "mode", label: "Mode", kind: "select", current_value: "https", options: [{ value: "https", label: "HTTPS", description: "Encrypted" }] }),
            field({ key: "user", label: "User", kind: "secret", secret: true, current_value: null, secret_state: "configured" }),
            field({ key: "token_name", label: "Token Name", kind: "secret", secret: true, current_value: null, secret_state: "missing" }),
            field({ key: "token_value", label: "Token Value", kind: "secret", secret: true, current_value: null, secret_state: "configured" }),
        ],
        ...overrides,
    };
}

function dockerSchema(): ProviderConnectionSchema {
    return {
        provider_id: "docker",
        provider_name: "Docker",
        editable: false,
        testable: true,
        updated_at: null,
        metadata: {
            update_supported: false,
            privileged_local_runtime: true,
        },
        fields: [
            field({
                key: "path",
                label: "Docker socket path",
                kind: "path",
                editable: false,
                current_value: "/var/run/docker.sock",
                source: "atlas_yaml",
                help_text: "Socket editing is disabled.",
            }),
        ],
    };
}

async function renderConnection(
    currentProvider: Provider = provider,
): Promise<void> {
    render(<ProviderConnection provider={currentProvider} />);
    if (currentProvider.capabilities.includes("connection")) {
        await screen.findByText("Connection");
        await screen.findByLabelText("Host").catch(async () => {
            await screen.findByLabelText("Docker socket path");
        });
    }
}

describe("ProviderConnection", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedGetProviderConnection.mockResolvedValue(proxmoxSchema());
        mockedTestProviderConnection.mockResolvedValue({
            provider_id: "proxmox",
            status: "success",
            message: "Connection OK.",
            tested_at: "2026-08-01T20:01:00Z",
            latency_ms: 42,
            diagnostics: { status: "online" },
        });
        mockedUpdateProviderConnection.mockResolvedValue({
            provider_id: "proxmox",
            connection_schema: proxmoxSchema({
                fields: proxmoxSchema().fields.map((candidate) =>
                    candidate.key === "host"
                        ? { ...candidate, current_value: "runtime.invalid" }
                        : candidate,
                ),
            }),
            updated_at: "2026-08-01T20:02:00Z",
            message: "Saved.",
        });
        vi.spyOn(window, "confirm").mockReturnValue(true);
    });

    it("renders Proxmox schema fields without secret values", async () => {
        await renderConnection();

        expect(screen.getByLabelText("Host")).toHaveValue("10.10.50.10");
        expect(screen.getByLabelText("Port")).toHaveValue(8006);
        expect(screen.getByLabelText("Node")).toHaveValue("vorex469");
        expect(screen.getByLabelText("Verify TLS")).not.toBeChecked();
        expect(screen.getByLabelText("Mode")).toHaveValue("https");
        expect(screen.getByText("HTTPS")).toBeInTheDocument();
        expect(screen.getAllByText(/Secret is Configured/).length).toBeGreaterThan(0);
        expect(screen.getByText(/Secret is Missing/)).toBeInTheDocument();
        expect(screen.queryByText("existing-secret")).not.toBeInTheDocument();
    });

    it("respects required and editable state and hides when capability is absent", async () => {
        await renderConnection(noConnectionProvider);

        expect(screen.queryByText("Connection")).not.toBeInTheDocument();
        expect(mockedGetProviderConnection).not.toHaveBeenCalled();
    });

    it("renders Docker path read-only and warning with save unavailable", async () => {
        mockedGetProviderConnection.mockResolvedValue(dockerSchema());
        await renderConnection({ ...provider, id: "docker", name: "Docker" });

        expect(screen.getByLabelText("Docker socket path")).toBeDisabled();
        expect(screen.getByText(/Privileged local runtime connection/)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Save Connection" })).not.toBeInTheDocument();
        expect(screen.getByText(/Connection editing is not available/)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Test Connection" })).toBeInTheDocument();
    });

    it("tests current edited values and entered secrets without saving", async () => {
        const user = userEvent.setup();
        await renderConnection();

        await user.clear(screen.getByLabelText("Host"));
        await user.type(screen.getByLabelText("Host"), "candidate.invalid");
        await user.type(screen.getByLabelText("Token Value"), "candidate-secret");
        await user.click(screen.getByRole("button", { name: "Test Connection" }));

        expect(window.confirm).toHaveBeenCalledWith("Run a live connection test for Proxmox?");
        await waitFor(() => {
            expect(mockedTestProviderConnection).toHaveBeenCalledWith("proxmox", {
                confirmed: true,
                values: expect.objectContaining({
                    host: "candidate.invalid",
                    port: 8006,
                    node: "vorex469",
                    verify_tls: false,
                    mode: "https",
                    token_value: "candidate-secret",
                }),
            });
        });
        expect(mockedUpdateProviderConnection).not.toHaveBeenCalled();
        expect(screen.getByText(/Test success/)).toBeInTheDocument();
        expect(screen.getByText(/42 ms/)).toBeInTheDocument();
        expect(screen.getByLabelText("Host")).toHaveValue("candidate.invalid");
        expect(screen.queryByText("candidate-secret")).not.toBeInTheDocument();
    });

    it("renders failed test details sanitized and preserves form values", async () => {
        mockedTestProviderConnection.mockResolvedValue({
            provider_id: "proxmox",
            status: "failure",
            message: "Bad token candidate-secret",
            tested_at: "2026-08-01T20:01:00Z",
            latency_ms: null,
            diagnostics: { error: "candidate-secret rejected" },
        });
        const user = userEvent.setup();
        await renderConnection();

        await user.clear(screen.getByLabelText("Host"));
        await user.type(screen.getByLabelText("Host"), "candidate.invalid");
        await user.type(screen.getByLabelText("Token Value"), "candidate-secret");
        await user.click(screen.getByRole("button", { name: "Test Connection" }));

        expect(await screen.findByText(/Test failure/)).toBeInTheDocument();
        expect(screen.getByText(/Bad token \[redacted\]/)).toBeInTheDocument();
        expect(screen.getByText(/\[redacted\] rejected/)).toBeInTheDocument();
        expect(screen.queryByText("candidate-secret")).not.toBeInTheDocument();
        expect(screen.getByLabelText("Host")).toHaveValue("candidate.invalid");
    });

    it("saves only editable values and entered secret replacements", async () => {
        const user = userEvent.setup();
        await renderConnection();

        await user.clear(screen.getByLabelText("Host"));
        await user.type(screen.getByLabelText("Host"), "runtime.invalid");
        await user.type(screen.getByLabelText("Token Value"), "replacement-secret");
        await user.click(screen.getByRole("button", { name: "Save Connection" }));

        expect(window.confirm).toHaveBeenCalledWith("Save connection settings for Proxmox?");
        await waitFor(() => {
            expect(mockedUpdateProviderConnection).toHaveBeenCalledWith("proxmox", {
                confirmed: true,
                values: expect.objectContaining({
                    host: "runtime.invalid",
                    port: 8006,
                    node: "vorex469",
                    verify_tls: false,
                    mode: "https",
                    token_value: "replacement-secret",
                }),
            });
        });
        expect(mockedUpdateProviderConnection.mock.calls[0][1].values).not.toHaveProperty("user");
        expect(screen.getByLabelText("Host")).toHaveValue("runtime.invalid");
        expect(screen.getByLabelText("Token Value")).toHaveValue("");
        expect(screen.queryByText("replacement-secret")).not.toBeInTheDocument();
    });

    it("omits untouched secrets from save", async () => {
        const user = userEvent.setup();
        await renderConnection();

        await user.click(screen.getByRole("button", { name: "Save Connection" }));

        await waitFor(() => {
            expect(mockedUpdateProviderConnection).toHaveBeenCalled();
        });
        const values = mockedUpdateProviderConnection.mock.calls[0][1].values;
        expect(values).not.toHaveProperty("user");
        expect(values).not.toHaveProperty("token_name");
        expect(values).not.toHaveProperty("token_value");
    });

    it("preserves form values and redacts failed save errors", async () => {
        const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
        mockedUpdateProviderConnection.mockRejectedValue(new Error("Save failed replacement-secret"));
        const user = userEvent.setup();
        await renderConnection();

        await user.clear(screen.getByLabelText("Host"));
        await user.type(screen.getByLabelText("Host"), "runtime.invalid");
        await user.type(screen.getByLabelText("Token Value"), "replacement-secret");
        await user.click(screen.getByRole("button", { name: "Save Connection" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Save failed [redacted]");
        expect(screen.getByLabelText("Host")).toHaveValue("runtime.invalid");
        expect(screen.getByLabelText("Token Value")).toHaveValue("replacement-secret");
        expect(screen.queryByText("replacement-secret")).not.toBeInTheDocument();
        expect(JSON.stringify(consoleError.mock.calls)).not.toContain("replacement-secret");
    });

    it("disables only connection controls while save is active", async () => {
        const pending = new Promise<never>(() => {});
        mockedUpdateProviderConnection.mockReturnValue(pending);
        const user = userEvent.setup();
        await renderConnection();

        await user.click(screen.getByRole("button", { name: "Save Connection" }));

        expect(await screen.findByRole("button", { name: "Saving..." })).toBeDisabled();
        expect(screen.getByLabelText("Host")).toBeDisabled();
    });
});
