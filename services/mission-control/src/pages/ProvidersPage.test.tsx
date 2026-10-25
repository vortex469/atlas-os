import { StrictMode } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "../api/atlas";
import { ProvidersPage } from "./ProvidersPage";

vi.mock("../api/atlas", () => ({ atlas: { get: vi.fn() } }));
const get = vi.mocked(atlas.get);
const provider = (id = "proxmox", name = "Proxmox", status = "healthy") => ({
    id, name, workspace: "homelab", priority: "normal", version: "1", description: "Provider",
    icon: "server", capabilities: [],
    health: { status, message: null, latency_ms: null, http_status: null, details: {} },
});
const show = () => render(<MemoryRouter><ProvidersPage /></MemoryRouter>);

describe("ProvidersPage", () => {
    beforeEach(() => get.mockReset());

    it("loads the provider registry directly and links to existing details", async () => {
        get.mockResolvedValue({ data: [provider()] });
        show();
        expect(await screen.findByRole("heading", { name: "Proxmox" })).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Open Proxmox provider" })).toHaveAttribute("href", "/providers/proxmox");
        expect(get).toHaveBeenCalledExactlyOnceWith("/providers");
        expect(screen.queryByRole("button", { name: /approve|execute|restart/i })).not.toBeInTheDocument();
    });

    it("offers recovery without exposing raw server errors", async () => {
        get.mockRejectedValueOnce(new Error("PRIVATE_SERVER_BODY"))
            .mockResolvedValueOnce({ data: [] });
        show();
        expect(await screen.findByRole("alert")).toHaveTextContent("Providers could not load");
        expect(document.body.textContent).not.toContain("PRIVATE_SERVER_BODY");
        fireEvent.click(screen.getByRole("button", { name: "Try again" }));
        expect(await screen.findByText("No providers are listed yet.")).toBeInTheDocument();
        expect(get).toHaveBeenCalledTimes(2);
    });

    it("does not treat a malformed response as an empty registry", async () => {
        get.mockResolvedValue({ data: { invalid: true } });
        show();
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByText("No providers are listed yet.")).not.toBeInTheDocument();
    });

    it("filters names locally and can clear a search", async () => {
        get.mockResolvedValue({ data: [provider(), provider("docker", "Docker")] });
        show();
        fireEvent.change(await screen.findByRole("searchbox", { name: "Search providers" }), { target: { value: "missing" } });
        expect(screen.getByText("No providers match your search.")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
        expect(screen.getByRole("heading", { name: "Proxmox" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Docker" })).toBeInTheDocument();
        expect(get).toHaveBeenCalledTimes(1);
    });

    it("does not keep old health visible after a failed refresh", async () => {
        get.mockResolvedValueOnce({ data: [provider()] }).mockRejectedValueOnce(new Error("offline"));
        show();
        const list = await screen.findByRole("region", { name: "Provider list" });
        expect(within(list).getByText("Healthy", { exact: true })).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
        await screen.findByRole("alert");
        expect(screen.queryByRole("region", { name: "Provider list" })).not.toBeInTheDocument();
    });

    it("keeps duplicate identities unavailable and withholds sensitive reasons", async () => {
        get.mockResolvedValue({ data: [provider(), provider(), {
            ...provider("docker", "Docker"), health: { status: "offline", message: "Bearer PRIVATE_TOKEN" },
        }] });
        show();
        expect(await screen.findAllByRole("heading", { name: "Provider information unavailable" })).toHaveLength(2);
        expect(screen.queryByRole("link", { name: "Open Proxmox provider" })).not.toBeInTheDocument();
        expect(document.body.textContent).not.toContain("PRIVATE_TOKEN");
        expect(screen.getByText("[Sensitive text withheld]")).toBeInTheDocument();
    });

    it("does not duplicate its initial read under Strict Mode", async () => {
        get.mockResolvedValue({ data: [] });
        render(<StrictMode><MemoryRouter><ProvidersPage /></MemoryRouter></StrictMode>);
        await screen.findByText("No providers are listed yet.");
        expect(get).toHaveBeenCalledTimes(1);
    });
});
