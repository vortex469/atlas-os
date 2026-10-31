import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Provider } from "../types/provider";
import { ProviderOverview } from "./ProviderOverview";

function view(capabilities: unknown, latencyMs: number | null = 24, status = "online", message: string | null = null, stale = false, endpoint: unknown = "https://proxmox.example/health") {
    const provider = {
        id: "proxmox",
        name: "Proxmox",
        workspace: "operations",
        priority: "critical",
        version: "1",
        description: "Virtualization",
        icon: "server",
        capabilities,
        health: { status, latency_ms: latencyMs, http_status: 200, message, details: { url: endpoint } },
    } as unknown as Provider;
    return render(<ProviderOverview provider={provider} stale={stale} />);
}

describe("ProviderOverview feature data", () => {
    it("shows provider health once as a readable status badge", () => {
        view([]);
        expect(screen.getByText("Healthy", { exact: true })).toBeInTheDocument();
        expect(screen.queryByText("online", { exact: true })).not.toBeInTheDocument();
        expect(screen.queryByText("Status", { exact: true })).not.toBeInTheDocument();
        expect(screen.getByText(/Response time/)).toBeInTheDocument();
        expect(screen.getByText("24 ms")).toBeInTheDocument();
    });

    it("keeps technical facts and the provider address collapsed until requested", async () => {
        const user = userEvent.setup();
        view([]);
        const disclosure = screen.getByText("Technical details");
        expect(disclosure).toBeVisible();
        expect(screen.getByText("HTTP response code")).not.toBeVisible();
        expect(screen.getByText("Provider priority")).not.toBeVisible();
        expect(screen.getByText("Version")).not.toBeVisible();
        expect(screen.getByText("https://proxmox.example")).not.toBeVisible();

        await user.click(disclosure);

        expect(screen.getByText("HTTP response code")).toBeVisible();
        expect(screen.getByText("200")).toBeVisible();
        expect(screen.getByText("Provider priority")).toBeVisible();
        expect(screen.getByText("Version")).toBeVisible();
        expect(screen.getByText("Provider address")).toBeVisible();
        expect(screen.getByText("https://proxmox.example")).toBeVisible();
    });

    it.each([
        ["https://public-user:PRIVATE-ENDPOINT-CANARY@example.invalid:8443/private-path?token=PRIVATE-ENDPOINT-CANARY#private-fragment", "https://example.invalid:8443"],
        ["http://[::1]:8080/provider-health", "http://[::1]:8080"],
        ["/relative/PRIVATE-ENDPOINT-CANARY", null],
        ["javascript:PRIVATE-ENDPOINT-CANARY", null],
        ["ftp://example.invalid/private-path", null],
    ])("shows only a valid public provider address for %s", async (endpoint, address) => {
        const user = userEvent.setup();
        const { container } = view([], 24, "online", null, false, endpoint);

        expect(container.innerHTML).not.toContain("PRIVATE-ENDPOINT-CANARY");
        if (address) {
            expect(screen.getByText(address)).not.toBeVisible();
            await user.click(screen.getByText("Technical details"));
            expect(screen.getByText("Provider address")).toBeVisible();
            expect(screen.getByText(address)).toBeVisible();
        } else {
            expect(screen.queryByText("Provider address")).not.toBeInTheDocument();
        }
    });

    it("omits an unavailable response-time placeholder", () => {
        view([], null);
        expect(screen.queryByText(/Response time/)).not.toBeInTheDocument();
        expect(screen.queryByText("—")).not.toBeInTheDocument();
    });

    it("explains that an unavailable result is Core's connection check", () => {
        view([], null, "offline", "Connection refused");
        expect(screen.getByText("Unavailable", { exact: true })).toBeVisible();
        expect(screen.getByText("Atlas Core could not reach this provider. It may still be running on its own computer.")).toBeVisible();
        expect(screen.getByText("Atlas Core's connection to this address was refused.")).toBeVisible();
        expect(screen.queryByText("Connection refused", { exact: true })).not.toBeInTheDocument();
    });

    it("marks cached provider health and response details as out of date after a catalog failure", () => {
        view([], 24, "online", null, true);

        expect(screen.getByRole("status")).toHaveTextContent("Could not update provider details. This information may be out of date.");
        expect(screen.getByText("Status unknown", { exact: true })).toBeVisible();
        expect(screen.getByText("Last known report (out of date): Healthy.")).toBeVisible();
        expect(screen.getByText(/Last known response time/)).toHaveTextContent("Last known response time 24 ms");
        expect(screen.queryByText("Online", { exact: true })).not.toBeInTheDocument();
        expect(screen.queryByText("Atlas Core could not reach this provider. It may still be running on its own computer.")).not.toBeInTheDocument();
    });

    it("marks an old connection failure as last known when provider refresh fails", () => {
        view([], null, "offline", "Connection refused", true);

        expect(screen.getByText("Status unknown", { exact: true })).toBeVisible();
        expect(screen.getByText("Last known report (out of date): Unavailable.")).toBeVisible();
        expect(screen.getByText("Last known connection result: Atlas Core's connection to this address was refused.")).toBeVisible();
        expect(screen.queryByText("Atlas Core could not reach this provider. It may still be running on its own computer.")).not.toBeInTheDocument();
    });

    it("distinguishes missing features from an empty advertised list", () => {
        view(undefined);
        expect(screen.getByText("Features unavailable.")).toBeInTheDocument();
        expect(screen.queryByText("No supported features are listed.")).not.toBeInTheDocument();
    });

    it("reports an empty but valid feature list plainly", () => {
        view([]);
        expect(screen.getByText("No supported features are listed.")).toBeInTheDocument();
        expect(screen.queryByText("Features unavailable.")).not.toBeInTheDocument();
    });
});
