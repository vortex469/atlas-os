import {
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getProviderResources,
    refreshProviderResources,
    updateProviderResourceExpectation,
} from "../api/resources";
import type { Provider } from "../types/provider";
import type {
    ProviderResource,
    ProviderResourceCollection,
    ProviderResourceExpectation,
} from "../types/resources";
import { ProviderResources } from "./ProviderResources";

vi.mock("../api/atlas", () => ({
    getAtlasErrorMessage: (
        error: unknown,
        fallback: string,
    ) => (error instanceof Error ? error.message : fallback),
}));

vi.mock("../api/resources", () => ({
    getProviderResources: vi.fn(),
    refreshProviderResources: vi.fn(),
    updateProviderResourceExpectation: vi.fn(),
}));

const mockedGetProviderResources = vi.mocked(getProviderResources);
const mockedRefreshProviderResources = vi.mocked(
    refreshProviderResources,
);
const mockedUpdateProviderResourceExpectation = vi.mocked(
    updateProviderResourceExpectation,
);

const options = [
    {
        value: "running",
        label: "Expected Running",
        description: "Warn when not running.",
        terminal: false,
    },
    {
        value: "stopped",
        label: "Expected Stopped",
        description: "Accept stopped state.",
        terminal: false,
    },
    {
        value: "ignored",
        label: "Ignore",
        description: "Do not monitor state.",
        terminal: true,
    },
];

const proxmoxProvider: Provider = {
    id: "proxmox",
    name: "Proxmox",
    workspace: "operations",
    priority: "critical",
    version: "1.0.0",
    description: "Virtualization provider.",
    icon: "server",
    capabilities: ["health", "resources", "monitoring"],
    health: {
        status: "online",
        latency_ms: null,
        http_status: null,
        message: null,
        details: {},
    },
};

const hermesProvider: Provider = {
    ...proxmoxProvider,
    id: "hermes",
    name: "Hermes",
    capabilities: ["health", "actions"],
};

function expectation(
    value: string | null,
    label = value ?? "Needs Review",
    state: ProviderResourceExpectation["state"] =
        value === "ignored"
            ? "ignored"
            : value === null
              ? "needs_review"
              : "configured",
): ProviderResourceExpectation {
    return {
        value,
        label,
        state,
        allowed_values: options,
    };
}

function resource(
    overrides: Partial<ProviderResource>,
): ProviderResource {
    return {
        provider_id: "proxmox",
        resource_id: "100",
        display_name: "router",
        resource_type: "vm",
        current_state: "running",
        expectation: expectation(null),
        configured: false,
        missing: false,
        needs_review: true,
        metadata: {
            vmid: 100,
            node: "vorex469",
        },
        ...overrides,
    };
}

function collection(
    resources: ProviderResource[] = [
        resource({}),
        resource({
            resource_id: "109",
            display_name: "kenny",
            resource_type: "lxc",
            current_state: "stopped",
            expectation: expectation("stopped", "Expected Stopped"),
            configured: true,
            needs_review: false,
            metadata: {
                vmid: 109,
                node: "vorex469",
            },
        }),
        resource({
            resource_id: "200",
            display_name: "old-vm",
            resource_type: "unknown",
            current_state: "missing",
            expectation: expectation("running", "Expected Running"),
            configured: true,
            missing: true,
            needs_review: false,
            metadata: {
                vmid: 200,
                node: "vorex469",
            },
        }),
        resource({
            resource_id: "300",
            display_name: "lab-vm",
            expectation: expectation("ignored", "Ignore"),
            configured: true,
            needs_review: false,
            metadata: {
                vmid: 300,
                node: "pve2",
            },
        }),
    ],
): ProviderResourceCollection {
    return {
        provider_id: "proxmox",
        provider_name: "Proxmox",
        refreshed_at: "2026-08-01T16:00:00Z",
        resources,
        summary: {
            total: resources.length,
            configured: resources.filter((item) => item.configured).length,
            needs_review: resources.filter((item) => item.needs_review).length,
            missing: resources.filter((item) => item.missing).length,
            ignored: resources.filter(
                (item) => item.expectation.state === "ignored",
            ).length,
            by_type: {},
            by_state: {},
        },
        metadata: {},
    };
}

function deferred<T>() {
    let resolve!: (value: T) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise<T>((promiseResolve, promiseReject) => {
        resolve = promiseResolve;
        reject = promiseReject;
    });

    return { promise, resolve, reject };
}

async function renderResources(
    provider: Provider = proxmoxProvider,
) {
    render(<ProviderResources provider={provider} />);

    if (provider.capabilities.includes("resources")) {
        await screen.findByText("router");
    }
}

describe("ProviderResources", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedGetProviderResources.mockResolvedValue(collection());
        mockedRefreshProviderResources.mockResolvedValue(collection());
        mockedUpdateProviderResourceExpectation.mockResolvedValue({
            provider_id: "proxmox",
            resource_id: "100",
            expectation: expectation("running", "Expected Running"),
            updated_at: "2026-08-01T16:05:00Z",
        });
        vi.spyOn(window, "confirm").mockReturnValue(true);
    });

    it("renders a generic resource collection", async () => {
        await renderResources();

        expect(screen.getByText("Resources")).toBeInTheDocument();
        expect(screen.getByText("Last refreshed:", { exact: false })).toBeInTheDocument();
        expect(screen.getByText("Total")).toBeInTheDocument();
        expect(screen.getByText("Configured")).toBeInTheDocument();
        expect(screen.getAllByText("Needs Review").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Missing").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Ignored").length).toBeGreaterThan(0);
        expect(screen.getByText("router")).toBeInTheDocument();
        expect(screen.getByText("Current State")).toBeInTheDocument();
        expect(screen.getByText("Atlas Expectation")).toBeInTheDocument();
    });

    it("renders Proxmox VMID and node metadata", async () => {
        await renderResources();

        expect(screen.getByText("VMID")).toBeInTheDocument();
        expect(screen.getByText("Node")).toBeInTheDocument();
        expect(screen.getByText("100")).toBeInTheDocument();
        expect(screen.getAllByText("vorex469").length).toBeGreaterThan(0);
    });

    it("highlights Needs Review rows", async () => {
        await renderResources();

        const row = screen.getByTestId("resource-row-100");
        expect(row).toHaveClass("bg-amber-500/10");
        expect(within(row).getAllByText("Needs Review").length).toBeGreaterThan(0);
    });

    it("marks missing resources", async () => {
        await renderResources();

        const row = screen.getByTestId("resource-row-200");
        expect(row).toHaveClass("bg-red-500/10");
        expect(within(row).getByText("Missing")).toBeInTheDocument();
    });

    it("renders ignored expectations", async () => {
        await renderResources();

        const row = screen.getByTestId("resource-row-300");
        expect(within(row).getByText("Ignored")).toBeInTheDocument();
        expect(
            within(row).getByRole("combobox", {
                name: /atlas expectation/i,
            }),
        ).toHaveValue("ignored");
    });

    it("refreshes inventory with POST and replaces displayed data", async () => {
        const user = userEvent.setup();
        mockedRefreshProviderResources.mockResolvedValue(
            collection([
                resource({
                    resource_id: "400",
                    display_name: "new-vm",
                    metadata: {
                        vmid: 400,
                        node: "pve2",
                    },
                }),
            ]),
        );
        await renderResources();

        await user.click(screen.getByRole("button", { name: "Refresh Inventory" }));

        await waitFor(() =>
            expect(mockedRefreshProviderResources).toHaveBeenCalledWith("proxmox"),
        );
        expect(screen.getByText("new-vm")).toBeInTheDocument();
        expect(screen.queryByText("router")).not.toBeInTheDocument();
    });

    it("preserves prior data when refresh fails", async () => {
        const user = userEvent.setup();
        mockedRefreshProviderResources.mockRejectedValue(
            new Error("Refresh failed."),
        );
        await renderResources();

        await user.click(screen.getByRole("button", { name: "Refresh Inventory" }));

        expect(await screen.findByText("Refresh failed.")).toBeInTheDocument();
        expect(screen.getByText("router")).toBeInTheDocument();
    });

    it("populates expectation controls from provider-advertised options", async () => {
        await renderResources();

        const select = screen.getByLabelText(/router/i);
        expect(within(select).getByRole("option", { name: "Expected Running" })).toBeInTheDocument();
        expect(within(select).getByRole("option", { name: "Expected Stopped" })).toBeInTheDocument();
        expect(within(select).getByRole("option", { name: "Ignore" })).toBeInTheDocument();
    });

    it("confirms and sends expectation updates with PUT", async () => {
        const user = userEvent.setup();
        await renderResources();

        await user.selectOptions(screen.getByLabelText(/router/i), "running");

        expect(window.confirm).toHaveBeenCalledWith(
            "Update Atlas expectation for router to Expected Running?",
        );
        await waitFor(() =>
            expect(mockedUpdateProviderResourceExpectation).toHaveBeenCalledWith(
                "proxmox",
                "100",
                "running",
                true,
            ),
        );
    });

    it("updates the row after a successful expectation save", async () => {
        const user = userEvent.setup();
        await renderResources();

        await user.selectOptions(screen.getByLabelText(/router/i), "running");

        await waitFor(() =>
            expect(screen.getByLabelText(/router/i)).toHaveValue("running"),
        );
    });

    it("shows a recoverable error when expectation update fails", async () => {
        const user = userEvent.setup();
        mockedUpdateProviderResourceExpectation.mockRejectedValue(
            new Error("Update failed."),
        );
        await renderResources();

        await user.selectOptions(screen.getByLabelText(/router/i), "running");

        expect(await screen.findByText("Update failed.")).toBeInTheDocument();
        expect(screen.getByText("router")).toBeInTheDocument();
    });

    it("disables only the edited row while updating", async () => {
        const user = userEvent.setup();
        const update = deferred<Awaited<ReturnType<typeof updateProviderResourceExpectation>>>();
        mockedUpdateProviderResourceExpectation.mockReturnValue(update.promise);
        await renderResources();

        await user.selectOptions(screen.getByLabelText(/router/i), "running");

        expect(screen.getByLabelText(/router/i)).toBeDisabled();
        expect(screen.getByLabelText(/kenny/i)).toBeEnabled();

        update.resolve({
            provider_id: "proxmox",
            resource_id: "100",
            expectation: expectation("running", "Expected Running"),
            updated_at: "2026-08-01T16:05:00Z",
        });

        await waitFor(() =>
            expect(screen.getByLabelText(/router/i)).toBeEnabled(),
        );
    });

    it("is hidden when a provider lacks resources capability", async () => {
        await renderResources(hermesProvider);

        expect(screen.queryByText("Resources")).not.toBeInTheDocument();
        expect(mockedGetProviderResources).not.toHaveBeenCalled();
    });
});
