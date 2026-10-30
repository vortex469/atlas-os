import { render, screen, within } from "@testing-library/react";
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
        expect(screen.getByText("Providers & integrations")).toBeInTheDocument();
    });

    it("shows no providers message when empty", () => {
        renderWithRouter(<AgentProviderOverviewSection providers={[]} />);
        expect(
            screen.queryAllByText((_content, element) => {
                return element?.textContent?.includes("No providers are set up yet.") || false;
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
        expect(screen.getByText("Total providers")).toBeInTheDocument();
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
            {
                id: "unknown",
                name: "Unknown service",
                workspace: "infra",
                priority: "standard",
                version: "1.0",
                description: "",
                icon: "unknown",
                capabilities: [],
                health: {
                    status: "unrecognized",
                    latency_ms: null,
                    http_status: 200,
                    message: null,
                    details: {},
                },
            },
            {
                id: "blocked",
                name: "Blocked service",
                workspace: "infra",
                priority: "standard",
                version: "1.0",
                description: "",
                icon: "blocked",
                capabilities: [],
                health: {
                    status: "blocked",
                    latency_ms: null,
                    http_status: 200,
                    message: null,
                    details: {},
                },
            },
        ];
        renderWithRouter(<AgentProviderOverviewSection providers={providers} />);
        const availableCard = screen.getByText("Available").closest(".mc-surface");
        const attentionCard = screen.getByText("Needs attention").closest(".mc-surface");
        expect(availableCard).not.toBeNull();
        expect(attentionCard).not.toBeNull();
        expect(within(availableCard as HTMLElement).getByText("1")).toBeInTheDocument();
        expect(within(attentionCard as HTMLElement).getByText("3")).toBeInTheDocument();
        expect(screen.getByText(/Kubernetes — Unavailable/)).toBeInTheDocument();
        expect(screen.getByText(/Unknown service — Status unknown/)).toBeInTheDocument();
        expect(screen.getByText(/Blocked service — Blocked/)).toBeInTheDocument();
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
                    message: "Connection refused",
                    details: {},
                },
            },
        ];
        renderWithRouter(<AgentProviderOverviewSection providers={providers} />);
        expect(
            screen.getByText("Critical provider unavailable"),
        ).toBeInTheDocument();
        expect(
            screen.getByText("Docker is unavailable. Atlas Core's connection to this address was refused."),
        ).toBeInTheDocument();
        expect(screen.getByText("Docker — Unavailable (critical)")).toBeInTheDocument();
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
        expect(screen.getByText("Docker — Healthy")).toBeInTheDocument();
        // Verify the provider card is rendered
        const container = screen.getByText("Docker — Healthy").closest(".grid");
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
        expect(screen.getByText("Docker — Healthy (critical)")).toBeInTheDocument();
    });
});
