import {
    fireEvent,
    render,
    screen,
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
        details: { version: "1.0.0" },
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
