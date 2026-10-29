import {
    fireEvent,
    render,
    screen,
    within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ServiceHealth } from "../../types/health";
import type { Provider } from "../../types/provider";
import { ServiceHealthSection } from "./ServiceHealthSection";

vi.mock("../../components/ProviderActions", () => ({
    ProviderActions: ({
        provider,
        onActionCompleted,
    }: {
        provider: Pick<Provider, "id" | "name">;
        onActionCompleted: () => void;
    }) => (
        <div>
            <p>Operations for {provider.name}</p>
            <button type="button" onClick={onActionCompleted}>
                Complete operation
            </button>
        </div>
    ),
}));

function service(
    providerId: string,
    latency: number,
): ServiceHealth {
    return {
        provider_id: providerId,
        status: "healthy",
        latency_ms: latency,
        http_status: 200,
        message: "Service ready.",
        details: { url: "http://10.10.60.30:8080/", version: "1.0.0" },
    };
}

const providers: Provider[] = [
    {
        id: "docker",
        name: "Docker",
        workspace: "infrastructure",
        priority: "critical",
        version: "1.0.0",
        description: "Docker provider",
        icon: "docker",
        capabilities: [],
        health: {
            status: "healthy",
            latency_ms: 8,
            http_status: 200,
            message: null,
            details: {},
        },
    },
    {
        id: "podman",
        name: "Podman",
        workspace: "infrastructure",
        priority: "standard",
        version: "1.0.0",
        description: "Podman provider",
        icon: "container",
        capabilities: [],
        health: {
            status: "healthy",
            latency_ms: 10,
            http_status: 200,
            message: null,
            details: {},
        },
    },
];

describe("ServiceHealthSection", () => {
    it("shows Atlas Core reachability, the checked address, and provider operations", async () => {
        const user = userEvent.setup();
        const onRefresh = vi.fn();
        const { rerender } = render(
            <ServiceHealthSection
                services={{ Containers: service("docker", 8) }}
                providers={providers}
                isRefreshing={false}
                onRefresh={onRefresh}
            />,
        );

        await user.click(
            screen.getByRole("button", {
                name: "View details for Containers",
            }),
        );
        expect(
            screen.getByRole("dialog", { name: "Containers" }),
        ).toBeInTheDocument();
        expect(within(screen.getByRole("dialog", { name: "Containers" })).getByText("Reachability from Atlas Core")).toBeInTheDocument();
        expect(screen.queryByText("Check time unavailable.")).not.toBeInTheDocument();
        expect(
            screen.getByText("Operations for Docker"),
        ).toBeInTheDocument();
        expect(screen.getByText("Address Atlas checked")).toBeInTheDocument();
        expect(screen.getByText("http://10.10.60.30:8080/")).toBeInTheDocument();
        expect(screen.getByText("atlas-core").closest("p")).toHaveTextContent("Run a network test from the machine running Atlas Core. If Atlas Core runs in Docker Compose, run it inside the atlas-core container. Run Compose commands from the folder containing Atlas's Compose file, or pass its full path with --file. A test from the service's machine or your browser only checks that machine's connection.");
        expect(screen.getByText(/"version"/)).not.toBeVisible();
        await user.click(screen.getByText("Technical details"));
        expect(screen.getByText(/"version"/)).toBeVisible();
        expect(screen.getAllByText("8 ms")).toHaveLength(2);

        rerender(
            <ServiceHealthSection
                services={{ Containers: service("podman", 14) }}
                providers={providers}
                isRefreshing
                onRefresh={onRefresh}
            />,
        );

        expect(
            screen.getByText("Operations for Podman"),
        ).toBeInTheDocument();
        expect(screen.getAllByText("14 ms")).toHaveLength(2);
        expect(
            screen.getByRole("button", {
                name: "Refreshing health...",
            }),
        ).toBeDisabled();

        await user.click(
            screen.getByRole("button", {
                name: "Complete operation",
            }),
        );
        expect(onRefresh).toHaveBeenCalledOnce();
    });

    it("labels a failed probe as unreachable from Atlas Core rather than offline", () => {
        render(
            <ServiceHealthSection
                services={{ iFileshare: { ...service("ifileshare", 0), latency_ms: null, status: "offline", message: "Connection refused" } }}
                providers={providers}
                isRefreshing={false}
                onRefresh={vi.fn()}
            />,
        );

        expect(screen.getByText("Unreachable from Atlas Core")).toBeInTheDocument();
        expect(screen.queryByText("Offline")).not.toBeInTheDocument();
        expect(screen.queryByText("Check time unavailable.")).not.toBeInTheDocument();
        expect(screen.getByText("Response time")).toBeInTheDocument();
        expect(screen.getByText("Not recorded")).toBeInTheDocument();
    });

    it("shows a plain next step for a refused service connection", async () => {
        const user = userEvent.setup();
        render(
            <ServiceHealthSection
                services={{
                    iFileshare: {
                        ...service("ifileshare", 0),
                        status: "offline",
                        message: "[Errno 111] Connection refused",
                    },
                }}
                providers={providers}
                isRefreshing={false}
                onRefresh={vi.fn()}
            />,
        );

        await user.click(
            screen.getByRole("button", { name: "View details for iFileshare" }),
        );

        expect(
            screen.getByRole("heading", { name: "What to check next" }),
        ).toBeInTheDocument();
        expect(
            screen.getByText(
                "On the service's host, confirm the service is listening on this port. If it runs in Docker, confirm the port is published. Then test again from Atlas Core.",
            ),
        ).toBeInTheDocument();
    });

    it("does not retain successful health or provider operations for a removed service", async () => {
        const user = userEvent.setup();
        const props = { providers, isRefreshing: false, onRefresh: vi.fn() };
        const { rerender } = render(<ServiceHealthSection {...props} services={{ Containers: service("docker", 8) }} />);
        await user.click(screen.getByRole("button", { name: "View details for Containers" }));
        rerender(<ServiceHealthSection {...props} services={{ Other: service("podman", 10) }} />);
        expect(screen.getByText("Status unknown")).toBeInTheDocument();
        expect(screen.getByText("This service is absent from the latest health response.")).toBeInTheDocument();
        expect(screen.queryByText("Operations for Docker")).not.toBeInTheDocument();
    });

    it("shows the checked host and path without URL credentials or query values", async () => {
        const user = userEvent.setup();
        const fileShare = {
            ...service("ifileshare", 7),
            details: { url: "http://operator:password@10.10.60.30:8080/health?token=private" },
        };
        render(
            <ServiceHealthSection
                services={{ iFileshare: fileShare }}
                providers={providers}
                isRefreshing={false}
                onRefresh={vi.fn()}
            />,
        );

        await user.click(screen.getByRole("button", { name: "View details for iFileshare" }));

        expect(screen.getByText("http://10.10.60.30:8080/health?…")).toBeInTheDocument();
        expect(screen.queryByText(/password|private/)).not.toBeInTheDocument();
    });

    it("closes the details drawer with Escape and the backdrop", async () => {
        const user = userEvent.setup();
        render(
            <ServiceHealthSection
                services={{ Containers: service("docker", 8) }}
                providers={providers}
                isRefreshing={false}
                onRefresh={vi.fn()}
            />,
        );

        const openDrawer = () =>
            user.click(
                screen.getByRole("button", {
                    name: "View details for Containers",
                }),
            );

        await openDrawer();
        fireEvent.keyDown(window, { key: "Escape" });
        expect(
            screen.queryByRole("dialog"),
        ).not.toBeInTheDocument();

        await openDrawer();
        const dialog = screen.getByRole("dialog");
        fireEvent.mouseDown(dialog.parentElement!);
        expect(
            screen.queryByRole("dialog"),
        ).not.toBeInTheDocument();
    });
});
