import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Provider } from "../types/provider";
import { ProviderOverview } from "./ProviderOverview";

function view(capabilities: unknown) {
    const provider = {
        id: "proxmox",
        name: "Proxmox",
        workspace: "operations",
        priority: "critical",
        version: "1",
        description: "Virtualization",
        icon: "server",
        capabilities,
        health: { status: "online", latency_ms: null, http_status: null, message: null, details: {} },
    } as unknown as Provider;
    render(<ProviderOverview provider={provider} />);
}

describe("ProviderOverview feature data", () => {
    it("shows provider health once as a readable status badge", () => {
        view([]);
        expect(screen.getByText("Online", { exact: true })).toBeInTheDocument();
        expect(screen.queryByText("online", { exact: true })).not.toBeInTheDocument();
        expect(screen.queryByText("Status", { exact: true })).not.toBeInTheDocument();
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
