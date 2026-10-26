import {
    act,
    render,
    screen,
    waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StrictMode } from "react";

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
    it("clears form and secret values immediately when the provider changes", async () => {
        const first = { ...provider, capabilities: ["connection"] };
        const next = { ...first, id: "other", name: "Other" };
        const user = userEvent.setup();
        const view = render(<ProviderConnection provider={first} />);
        await user.clear(await screen.findByLabelText("Host"));
        await user.type(screen.getByLabelText("Host"), "previous.example.invalid");
        await user.type(screen.getByLabelText("Token Value"), "fixture-only-secret");
        let resolveNext!: (value: ProviderConnectionSchema) => void;
        mockedGetProviderConnection.mockImplementationOnce(() => new Promise((resolve) => { resolveNext = resolve; }));
        view.rerender(<ProviderConnection provider={next} />);
        expect(screen.queryByLabelText("Host")).not.toBeInTheDocument();
        expect(screen.queryByDisplayValue("fixture-only-secret")).not.toBeInTheDocument();
        await waitFor(() => expect(mockedGetProviderConnection).toHaveBeenCalledWith("other"));
        await act(async () => resolveNext(proxmoxSchema({ provider_id: "other", provider_name: "Other" })));
        expect(await screen.findByLabelText("Host")).toHaveValue("10.10.50.10");
        expect(screen.getByLabelText("Token Value")).toHaveValue("");
        expect(mockedTestProviderConnection).not.toHaveBeenCalled();
        expect(mockedUpdateProviderConnection).not.toHaveBeenCalled();
    });

    it("reads the connection schema once under Strict Mode", async () => {
        render(<StrictMode><ProviderConnection provider={{ ...provider, capabilities: ["connection"] }} /></StrictMode>);
        await screen.findByLabelText("Host");
        expect(mockedGetProviderConnection).toHaveBeenCalledTimes(1);
        expect(mockedTestProviderConnection).not.toHaveBeenCalled();
        expect(mockedUpdateProviderConnection).not.toHaveBeenCalled();
    });

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

    it.each(["Save Connection", "Test Connection", "Reload settings"])("admits one %s request during batched clicks", async (name) => {
        await renderConnection();
        if (name === "Save Connection") mockedUpdateProviderConnection.mockReturnValue(new Promise(() => {}));
        if (name === "Test Connection") mockedTestProviderConnection.mockReturnValue(new Promise(() => {}));
        if (name === "Reload settings") mockedGetProviderConnection.mockReturnValue(new Promise(() => {}));
        const button = screen.getByRole("button", { name });
        act(() => { button.click(); button.click(); });
        expect(mockedUpdateProviderConnection).toHaveBeenCalledTimes(name === "Save Connection" ? 1 : 0);
        expect(mockedTestProviderConnection).toHaveBeenCalledTimes(name === "Test Connection" ? 1 : 0);
        expect(mockedGetProviderConnection).toHaveBeenCalledTimes(name === "Reload settings" ? 2 : 1);
        expect(window.confirm).toHaveBeenCalledTimes(name === "Reload settings" ? 0 : 1);
    });

    it.each(["Save Connection", "Test Connection"])("blocks the other connection controls while %s starts", async (name) => {
        await renderConnection();
        mockedUpdateProviderConnection.mockReturnValue(new Promise(() => {}));
        mockedTestProviderConnection.mockReturnValue(new Promise(() => {}));
        const save = screen.getByRole("button", { name: "Save Connection" });
        const test = screen.getByRole("button", { name: "Test Connection" });
        const reload = screen.getByRole("button", { name: "Reload settings" });
        act(() => { (name === "Save Connection" ? save : test).click(); (name === "Save Connection" ? test : save).click(); reload.click(); });
        expect(mockedUpdateProviderConnection).toHaveBeenCalledTimes(name === "Save Connection" ? 1 : 0);
        expect(mockedTestProviderConnection).toHaveBeenCalledTimes(name === "Test Connection" ? 1 : 0);
        expect(mockedGetProviderConnection).toHaveBeenCalledTimes(1);
        expect(window.confirm).toHaveBeenCalledTimes(1);
    });

    it.each(["Save Connection", "Test Connection"])("does not lock controls after declining %s", async name => {
        const user = userEvent.setup();
        await renderConnection();
        vi.mocked(window.confirm).mockReturnValueOnce(false);
        await user.click(screen.getByRole("button", { name }));
        expect(mockedUpdateProviderConnection).not.toHaveBeenCalled();
        expect(mockedTestProviderConnection).not.toHaveBeenCalled();
        await user.click(screen.getByRole("button", { name }));
        expect(mockedUpdateProviderConnection).toHaveBeenCalledTimes(name === "Save Connection" ? 1 : 0);
        expect(mockedTestProviderConnection).toHaveBeenCalledTimes(name === "Test Connection" ? 1 : 0);
    });

    it("does not start an automatic settings read when the provider label changes during a live test", async () => {
        const user = userEvent.setup();
        let finish!: (value: Awaited<ReturnType<typeof testProviderConnection>>) => void;
        mockedTestProviderConnection.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
        const view = render(<ProviderConnection provider={provider} />);
        await screen.findByLabelText("Host");
        await user.click(screen.getByRole("button", { name: "Test Connection" }));
        view.rerender(<ProviderConnection provider={{ ...provider, name: "Updated provider name" }} />);
        await act(async () => { await Promise.resolve(); });
        expect(mockedGetProviderConnection).toHaveBeenCalledTimes(1);
        expect(screen.getByRole("button", { name: "Save Connection" })).toBeDisabled();
        await act(async () => finish({ provider_id: "proxmox", status: "success", message: "Connection OK.", tested_at: "2026-08-01T20:01:00Z", latency_ms: 42, diagnostics: {} }));
        expect(screen.getByRole("button", { name: "Test Connection" })).toBeEnabled();
        expect(mockedTestProviderConnection).toHaveBeenCalledTimes(1);
    });

    it("releases the request guard after a rejection without replaying it", async () => {
        const user = userEvent.setup();
        mockedTestProviderConnection.mockRejectedValueOnce(new Error("Test unavailable"));
        await renderConnection();
        await user.click(screen.getByRole("button", { name: "Test Connection" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("Test unavailable");
        expect(mockedTestProviderConnection).toHaveBeenCalledTimes(1);
        await user.click(screen.getByRole("button", { name: "Reload settings" }));
        expect(mockedGetProviderConnection).toHaveBeenCalledTimes(2);
        expect(mockedTestProviderConnection).toHaveBeenCalledTimes(1);
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
            diagnostics: { error: "candidate-secret rejected", "candidate-secret": "candidate-secret" },
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
        expect(screen.getAllByText("[redacted]", { exact: true })).toHaveLength(2);
        expect(document.body.textContent).not.toContain("candidate-secret");
        expect(screen.queryByText("candidate-secret")).not.toBeInTheDocument();
        expect(screen.getByLabelText("Host")).toHaveValue("candidate.invalid");
    });

    it.each(["Host", "Token Value"])("invalidates test results when %s changes without revealing the tested secret", async (label) => {
        mockedTestProviderConnection.mockResolvedValue({
            provider_id: "proxmox", status: "failure", message: "Bad token previous-test-secret",
            tested_at: "2026-10-26T00:00:00Z", latency_ms: null,
            diagnostics: { error: "previous-test-secret rejected" },
        });
        const user = userEvent.setup();
        await renderConnection();
        await user.type(screen.getByLabelText("Token Value"), "previous-test-secret");
        await user.click(screen.getByRole("button", { name: "Test Connection" }));
        await screen.findByText(/Test failure/);
        expect(document.body.textContent).not.toContain("previous-test-secret");
        await user.clear(screen.getByLabelText(label));
        expect(screen.queryByText(/Test failure/)).not.toBeInTheDocument();
        expect(document.body.textContent).not.toContain("previous-test-secret");
        expect(mockedTestProviderConnection).toHaveBeenCalledTimes(1);
        expect(mockedUpdateProviderConnection).not.toHaveBeenCalled();
    });

    it("clears the test result as soon as settings are reloaded", async () => {
        const user = userEvent.setup();
        await renderConnection();
        await user.click(screen.getByRole("button", { name: "Test Connection" }));
        await screen.findByText(/Test success/);
        let rejectRead!: (reason: Error) => void;
        mockedGetProviderConnection.mockReturnValueOnce(new Promise((_, reject) => { rejectRead = reject; }));
        await user.click(screen.getByRole("button", { name: "Reload settings" }));
        expect(screen.queryByText(/Test success/)).not.toBeInTheDocument();
        await act(async () => { rejectRead(new Error("Settings unavailable")); });
        expect(await screen.findByRole("alert")).toHaveTextContent("Settings unavailable");
        expect(screen.queryByText(/Test success/)).not.toBeInTheDocument();
        expect(mockedTestProviderConnection).toHaveBeenCalledTimes(1);
        expect(mockedUpdateProviderConnection).not.toHaveBeenCalled();
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
        expect(screen.getByRole("status")).toHaveTextContent("Connection settings saved.");
        await user.type(screen.getByLabelText("Host"), ".edited");
        expect(screen.queryByText("Connection settings saved.")).not.toBeInTheDocument();
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
        expect(screen.getByText("Connection settings saved.")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Reload settings" }));
        await waitFor(() => expect(mockedGetProviderConnection).toHaveBeenCalledTimes(2));
        expect(screen.queryByText("Connection settings saved.")).not.toBeInTheDocument();
    });

    it("preserves draft values and pauses writes when a save outcome is unconfirmed", async () => {
        const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
        mockedUpdateProviderConnection.mockRejectedValue(new Error("Save failed replacement-secret"));
        const user = userEvent.setup();
        await renderConnection();

        await user.clear(screen.getByLabelText("Host"));
        await user.type(screen.getByLabelText("Host"), "runtime.invalid");
        await user.type(screen.getByLabelText("Token Value"), "replacement-secret");
        await user.click(screen.getByRole("button", { name: "Save Connection" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Save outcome not confirmed");
        expect(screen.getByRole("button", { name: "Save Connection" })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Test Connection" })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Reload settings" })).toBeEnabled();
        expect(document.body.textContent).not.toContain("Save failed");
        expect(screen.getByLabelText("Host")).toHaveValue("runtime.invalid");
        expect(screen.getByLabelText("Token Value")).toHaveValue("replacement-secret");
        expect(screen.queryByText("replacement-secret")).not.toBeInTheDocument();
        expect(JSON.stringify(consoleError.mock.calls)).not.toContain("replacement-secret");
    });

    it("keeps an uncertain save paused through a failed reload and recovers only through a successful read", async () => {
        const user = userEvent.setup();
        mockedUpdateProviderConnection.mockRejectedValueOnce(new Error("lost response"));
        await renderConnection();
        await user.type(screen.getByLabelText("Token Value"), "draft-secret");
        await user.click(screen.getByRole("button", { name: "Save Connection" }));
        await screen.findByText("Save outcome not confirmed");
        mockedGetProviderConnection.mockRejectedValueOnce(new Error("Reload unavailable"));
        await user.click(screen.getByRole("button", { name: "Reload settings" }));
        await screen.findByText("Reload unavailable");
        expect(screen.getByText("Save outcome not confirmed")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Save Connection" })).toBeDisabled();
        mockedGetProviderConnection.mockResolvedValueOnce(proxmoxSchema());
        await user.click(screen.getByRole("button", { name: "Reload settings" }));
        await waitFor(() => expect(screen.getByRole("button", { name: "Save Connection" })).toBeEnabled());
        expect(screen.queryByText("Save outcome not confirmed")).not.toBeInTheDocument();
        expect(screen.getByLabelText("Token Value")).toHaveValue("");
        expect(mockedUpdateProviderConnection).toHaveBeenCalledTimes(1);
        expect(mockedTestProviderConnection).not.toHaveBeenCalled();
    });

    it("defers automatic settings reads while an uncertain save holds draft values", async () => {
        const user = userEvent.setup();
        mockedUpdateProviderConnection.mockRejectedValueOnce(new Error("lost response"));
        const view = render(<ProviderConnection provider={provider} />);
        await screen.findByLabelText("Host");
        await user.clear(screen.getByLabelText("Host"));
        await user.type(screen.getByLabelText("Host"), "draft.invalid");
        await user.type(screen.getByLabelText("Token Value"), "draft-secret");
        await user.click(screen.getByRole("button", { name: "Save Connection" }));
        await screen.findByText("Save outcome not confirmed");
        view.rerender(<ProviderConnection provider={{ ...provider, name: "Renamed provider" }} />);
        await act(async () => { await Promise.resolve(); });
        expect(mockedGetProviderConnection).toHaveBeenCalledTimes(1);
        expect(screen.getByLabelText("Host")).toHaveValue("draft.invalid");
        expect(screen.getByLabelText("Token Value")).toHaveValue("draft-secret");
        expect(screen.getByText("Save outcome not confirmed")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Test Connection" })).toBeDisabled();
        expect(mockedUpdateProviderConnection).toHaveBeenCalledTimes(1);
    });

    it("does not partially apply an unreadable saved schema or keep an old test result", async () => {
        const user = userEvent.setup();
        await renderConnection();
        await user.click(screen.getByRole("button", { name: "Test Connection" }));
        await screen.findByText("Connection OK.");
        mockedUpdateProviderConnection.mockResolvedValueOnce({ provider_id: "proxmox",
            connection_schema: { ...proxmoxSchema(), fields: null } as unknown as ProviderConnectionSchema,
            updated_at: "2026-08-01T20:02:00Z", message: "Saved." });
        await user.click(screen.getByRole("button", { name: "Save Connection" }));
        expect(await screen.findByText("Save outcome not confirmed")).toBeInTheDocument();
        expect(screen.queryByText("Connection settings saved.")).not.toBeInTheDocument();
        expect(screen.queryByText("Connection OK.")).not.toBeInTheDocument();
        expect(screen.getByLabelText("Host")).toBeInTheDocument();
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
