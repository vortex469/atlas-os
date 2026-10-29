import { StrictMode } from "react";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

    it("keeps registry navigation links visible in keyboard focus", async () => {
        const user = userEvent.setup();
        get.mockResolvedValue({ data: [provider()] });
        show();

        const backLink = await screen.findByRole("link", { name: "← Mission Control" });
        const providerLink = screen.getByRole("link", { name: "Open Proxmox provider" });
        expect(backLink).toHaveClass("mc-focusable");
        expect(providerLink).toHaveClass("mc-focusable");

        await user.tab();
        expect(backLink).toHaveFocus();
        await user.tab();
        expect(screen.getByRole("button", { name: "Refresh" })).toHaveFocus();
        await user.tab();
        expect(providerLink).toHaveFocus();
    });

    it("keeps registry health readable without empty check-time placeholders", async () => {
        get.mockResolvedValue({ data: [provider()] });
        show();
        const list = await screen.findByRole("region", { name: "Provider list" });
        expect(within(list).getByText("Healthy", { exact: true })).toBeInTheDocument();
        expect(within(list).queryByText("Check time unavailable.", { exact: true })).not.toBeInTheDocument();
    });

    it("offers recovery without exposing raw server errors", async () => {
        get.mockRejectedValueOnce(new Error("PRIVATE_SERVER_BODY"))
            .mockResolvedValueOnce({ data: [] });
        show();
        const alert = await screen.findByRole("alert");
        expect(within(alert).getByRole("heading", { name: "Providers could not load" })).toBeInTheDocument();
        expect(within(alert).queryByText("Try again to get the latest provider list.")).not.toBeInTheDocument();
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

    it("keeps last loaded providers visible as unknown during and after a failed refresh", async () => {
        get.mockResolvedValueOnce({ data: [provider()] });
        let rejectRefresh!: (error: Error) => void;
        get.mockImplementationOnce(() => new Promise((_, reject) => { rejectRefresh = reject; }));
        show();
        const list = await screen.findByRole("region", { name: "Provider list" });
        expect(within(list).getByText("Healthy", { exact: true })).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
        expect(screen.getByRole("status")).toHaveTextContent("Refreshing providers. Showing the last loaded information.");
        expect(within(list).getByText("Last known report (out of date): Healthy.")).toBeInTheDocument();
        expect(within(list).queryByText("Healthy", { exact: true })).not.toBeInTheDocument();

        await act(async () => rejectRefresh(new Error("offline")));

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Provider refresh failed");
        expect(alert).toHaveTextContent("Current provider information is unknown.");
        expect(screen.getByRole("region", { name: "Provider list" })).toBeInTheDocument();
        expect(within(list).getByText("Last known report (out of date): Healthy.")).toBeInTheDocument();
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
