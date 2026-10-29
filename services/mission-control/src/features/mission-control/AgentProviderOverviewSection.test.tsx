import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AgentProviderOverviewSection } from "./AgentProviderOverviewSection";
import type { Provider } from "../../types/provider";

describe("AgentProviderOverviewSection", () => {
    const renderWithRouter = (component: React.ReactElement) => {
        return render(<BrowserRouter>{component}</BrowserRouter>);
    };

    it("renders agent and provider section", () => {
        renderWithRouter(<AgentProviderOverviewSection providers={[]} />);
        expect(screen.getByText("Agents & Providers")).toBeInTheDocument();
    });

    it("shows no providers message when empty", () => {
        renderWithRouter(<AgentProviderOverviewSection providers={[]} />);
        expect(
            screen.queryAllByText((_content, element) => {
                return element?.textContent?.includes("No providers configured") || false;
            })[0],
        ).toBeInTheDocument();
    });

    it("displays provider counts", () => {
        const providers: Provider[] = [
            {
                id: "docker",
                name: "Docker",
                workspace: "infra",
                priority: "critical",
                version: "1.0",
                description: "Container runtime",
                icon: "docker",
                capabilities: ["build", "run"],
                health: {
                    status: "healthy",
                    latency_ms: 10,
                    http_status: 200,
                    message: null,
                    details: {},
                },
            },
        ];
        renderWithRouter(<AgentProviderOverviewSection providers={providers} />);
        const allOnes = screen.queryAllByText("1");
        expect(allOnes.length).toBeGreaterThan(0);
        expect(screen.getByText("Total Providers")).toBeInTheDocument();
    });

    it("counts available providers", () => {
        const providers: Provider[] = [
            {
                id: "docker",
                name: "Docker",
                workspace: "infra",
                priority: "critical",
                version: "1.0",
                description: "",
                icon: "docker",
                capabilities: [],
                health: {
                    status: "healthy",
                    latency_ms: 10,
                    http_status: 200,
                    message: null,
                    details: {},
                },
            },
            {
                id: "k8s",
                name: "Kubernetes",
                workspace: "infra",
                priority: "standard",
                version: "1.0",
                description: "",
                icon: "k8s",
                capabilities: [],
                health: {
                    status: "offline",
                    latency_ms: null,
                    http_status: null,
                    message: "Connection refused",
                    details: {},
                },
            },
        ];
        renderWithRouter(<AgentProviderOverviewSection providers={providers} />);
        expect(screen.getByText("Available")).toBeInTheDocument();
        expect(screen.getByText("Unavailable")).toBeInTheDocument();
    });

    it("warns about unavailable critical providers", () => {
        const providers: Provider[] = [
            {
                id: "docker",
                name: "Docker",
                workspace: "infra",
                priority: "critical",
                version: "1.0",
                description: "",
                icon: "docker",
                capabilities: [],
                health: {
                    status: "offline",
                    latency_ms: null,
                    http_status: null,
                    message: "Not responding",
                    details: {},
                },
            },
        ];
        renderWithRouter(<AgentProviderOverviewSection providers={providers} />);
        expect(
            screen.getByText(/Critical Provider Unavailable/),
        ).toBeInTheDocument();
        expect(
            screen.getByText(/Docker is not responding/),
        ).toBeInTheDocument();
    });

    it("displays provider health status", () => {
        const providers: Provider[] = [
            {
                id: "docker",
                name: "Docker",
                workspace: "infra",
                priority: "standard",
                version: "1.0",
                description: "",
                icon: "docker",
                capabilities: [],
                health: {
                    status: "healthy",
                    latency_ms: 5,
                    http_status: 200,
                    message: null,
                    details: {},
                },
            },
        ];
        renderWithRouter(<AgentProviderOverviewSection providers={providers} />);
        expect(screen.getByText("Docker")).toBeInTheDocument();
        // Verify the provider card is rendered
        const container = screen.getByText("Docker").closest(".grid");
        expect(container).toBeInTheDocument();
    });

    it("marks critical providers with star", () => {
        const providers: Provider[] = [
            {
                id: "docker",
                name: "Docker",
                workspace: "infra",
                priority: "critical",
                version: "1.0",
                description: "",
                icon: "docker",
                capabilities: [],
                health: {
                    status: "healthy",
                    latency_ms: 5,
                    http_status: 200,
                    message: null,
                    details: {},
                },
            },
        ];
        renderWithRouter(<AgentProviderOverviewSection providers={providers} />);
        expect(screen.getByText(/Docker ⭐/)).toBeInTheDocument();
    });
});
