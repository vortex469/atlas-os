import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Provider } from "../types/provider";
import { ProviderOverview } from "./ProviderOverview";

function view(capabilities: unknown, latencyMs: number | null = 24) {
    const provider = {
        id: "proxmox",
        name: "Proxmox",
        workspace: "operations",
        priority: "critical",
        version: "1",
        description: "Virtualization",
        icon: "server",
        capabilities,
        health: { status: "online", latency_ms: latencyMs, http_status: 200, message: null, details: { url: "https://proxmox.example/health" } },
    } as unknown as Provider;
    render(<ProviderOverview provider={provider} />);
}

describe("ProviderOverview feature data", () => {
    it("shows provider health once as a readable status badge", () => {
        view([]);
        expect(screen.getByText("Online", { exact: true })).toBeInTheDocument();
        expect(screen.queryByText("online", { exact: true })).not.toBeInTheDocument();
        expect(screen.queryByText("Status", { exact: true })).not.toBeInTheDocument();
        expect(screen.getByText(/Response time/)).toBeInTheDocument();
        expect(screen.getByText("24 ms")).toBeInTheDocument();
    });

    it("keeps technical facts and the endpoint collapsed until requested", async () => {
        const user = userEvent.setup();
        view([]);
        const disclosure = screen.getByText("Technical details");
        expect(disclosure).toBeVisible();
        expect(screen.getByText("HTTP response code")).not.toBeVisible();
        expect(screen.getByText("Provider priority")).not.toBeVisible();
        expect(screen.getByText("Version")).not.toBeVisible();
        expect(screen.getByText("https://proxmox.example/health")).not.toBeVisible();

        await user.click(disclosure);

        expect(screen.getByText("HTTP response code")).toBeVisible();
        expect(screen.getByText("200")).toBeVisible();
        expect(screen.getByText("Provider priority")).toBeVisible();
        expect(screen.getByText("Version")).toBeVisible();
        expect(screen.getByText("https://proxmox.example/health")).toBeVisible();
    });

    it("omits an unavailable response-time placeholder", () => {
        view([], null);
        expect(screen.queryByText(/Response time/)).not.toBeInTheDocument();
        expect(screen.queryByText("—")).not.toBeInTheDocument();
    });

    it("distinguishes missing features from an empty advertised list", () => {
        view(undefined);
        expect(screen.getByText("Capabilities unavailable.")).toBeInTheDocument();
        expect(screen.queryByText("No capabilities advertised.")).not.toBeInTheDocument();
    });

    it("reports an empty but valid capability list plainly", () => {
        view([]);
        expect(screen.getByText("No capabilities advertised.")).toBeInTheDocument();
        expect(screen.queryByText("Capabilities unavailable.")).not.toBeInTheDocument();
    });
});
