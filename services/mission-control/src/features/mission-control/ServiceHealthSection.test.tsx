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
    it("shows refreshed service details and provider operations", async () => {
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
        expect(
            screen.getByText("Operations for Docker"),
        ).toBeInTheDocument();
        expect(screen.getByText("Address Atlas checked")).toBeInTheDocument();
        expect(screen.getByText("http://10.10.60.30:8080/")).toBeInTheDocument();
        expect(screen.getByText("Atlas Core checks this address from its own machine. A service can open in your browser and still be unreachable from Atlas Core.")).toBeInTheDocument();
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

    it.each([
        ["[Errno 111] Connection refused", "The service refused the connection.", "Check that the service is listening on this port and that Atlas Core can reach it."],
        ["[Errno 113] No route to host", "The service could not be reached over the network.", "Check the target address and the network or firewall route from Atlas Core to the service host."],
        ["[Errno 110] Connection timed out", "The service did not respond in time.", "Check that the service is responding and that network or firewall rules allow access from Atlas Core."],
    ])("explains a failed check and suggests a next check for %s", async (message, explanation, nextCheck) => {
        const user = userEvent.setup();
        render(
            <ServiceHealthSection
                services={{ iFileshare: {
                    ...service("ifileshare", 0),
                    status: "offline",
                    message,
                } }}
                providers={providers}
                isRefreshing={false}
                onRefresh={vi.fn()}
            />,
        );

        await user.click(screen.getByRole("button", { name: "View details for iFileshare" }));

        const drawer = within(screen.getByRole("dialog"));
        expect(drawer.getByRole("heading", { name: "What this means" })).toBeInTheDocument();
        expect(drawer.getByText(explanation)).toBeInTheDocument();
        expect(drawer.getByRole("heading", { name: "Next check" })).toBeInTheDocument();
        expect(drawer.getByText(nextCheck)).toBeInTheDocument();
        const technicalDetails = drawer.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(technicalDetails).toHaveTextContent(message);
        const diagnostic = technicalDetails?.querySelector("pre");
        expect(diagnostic).not.toBeVisible();
        await user.click(drawer.getByText("Technical details"));
        expect(diagnostic).toBeVisible();
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
