import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Provider } from "../types/provider";
import { ProviderOverview } from "./ProviderOverview";

const provider: Provider = {
    id: "proxmox", name: "Proxmox", workspace: "operations", priority: "critical", version: "1",
    description: "Virtualization", icon: "server", capabilities: ["resources"],
    health: { status: "online", latency_ms: 12, http_status: 200, message: null, details: {} },
};

describe("ProviderOverview health", () => {
    it.each([
        ["https://public-user:PUBLIC-ENDPOINT-CANARY@example.invalid:8443/PUBLIC-ENDPOINT-CANARY?token=PUBLIC-ENDPOINT-CANARY#PUBLIC-ENDPOINT-CANARY", "https://example.invalid:8443"],
        ["http://[::1]:8080/provider-health", "http://[::1]:8080"],
        ["https://example.invalid/provider-health", "https://example.invalid"],
        ["/relative/PUBLIC-ENDPOINT-CANARY", null],
        ["javascript:PUBLIC-ENDPOINT-CANARY", null],
        ["data:text/plain,PUBLIC-ENDPOINT-CANARY", null],
    ])("shows only a provider address without URL credentials or payload: %s", (url, address) => {
        const { container } = render(<ProviderOverview provider={{ ...provider, health: { ...provider.health, details: { url } } }} />);
        expect(container.innerHTML).not.toContain("PUBLIC-ENDPOINT-CANARY");
        if (address) {
            expect(screen.getByText(address)).not.toBeVisible();
            fireEvent.click(screen.getByText("Technical details"));
            expect(screen.getByText("Provider address")).toBeVisible();
            expect(screen.getByText(address)).toBeVisible();
        } else expect(screen.queryByText("Provider address")).not.toBeInTheDocument();
    });

    it("does not treat a generic success code as recognized provider health", () => {
        const { container } = render(<ProviderOverview provider={{ ...provider, health: { ...provider.health, status: "success" } }} />);
        expect(screen.getByText("Unknown")).toBeInTheDocument();
        expect(container.querySelector('[data-mc-status="success"]')).toBeNull();
    });

    it("explains retained health without a message and restores current health after a fresh read", () => {
        const view = render(<ProviderOverview provider={provider} stale />);
        expect(screen.getByText("Current provider health could not be refreshed. Last reported status: Healthy.")).toBeInTheDocument();
        expect(view.container.querySelector('[data-mc-status="success"]')).toBeNull();
        view.rerender(<ProviderOverview provider={{ ...provider, health: { ...provider.health, status: "offline" } }} />);
        expect(screen.getByText("Unavailable")).toBeInTheDocument();
        expect(screen.queryByText(/Last reported status:/)).not.toBeInTheDocument();
    });
});
