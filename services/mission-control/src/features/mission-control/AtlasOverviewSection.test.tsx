import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AtlasOverviewSection } from "./AtlasOverviewSection";
import type { ServiceHealth } from "../../types/health";

const renderWithRouter = (component: React.ReactNode) => {
    return render(
        <BrowserRouter>{component}</BrowserRouter>
    );
};

describe("AtlasOverviewSection", () => {
    it("renders atlas status card", () => {
        const services: Record<string, ServiceHealth> = {};
        renderWithRouter(
            <AtlasOverviewSection
                atlasStatus="healthy"
                services={services}
                lastUpdated={new Date()}
            />,
        );
        expect(screen.getByText("Atlas health")).toBeInTheDocument();
        expect(screen.getByText("Atlas Core")).toBeInTheDocument();
    });

    it("displays healthy status", () => {
        const services: Record<string, ServiceHealth> = {};
        renderWithRouter(
            <AtlasOverviewSection
                atlasStatus="healthy"
                services={services}
                lastUpdated={new Date()}
            />,
        );
        expect(screen.getByText("Healthy")).toBeInTheDocument();
    });

    it("displays degraded status with service issues", () => {
        const services: Record<string, ServiceHealth> = {
            api: {
                provider_id: "api",
                status: "degraded",
                latency_ms: 5000,
                http_status: 200,
                message: "High latency",
                details: {},
            },
        };
        renderWithRouter(
            <AtlasOverviewSection
                atlasStatus="degraded"
                services={services}
                lastUpdated={new Date()}
            />,
        );
        const degradedElements = screen.queryAllByText("Degraded");
        expect(degradedElements.length).toBeGreaterThan(0);
    });

    it("handles unknown atlas status", () => {
        const services: Record<string, ServiceHealth> = {};
        renderWithRouter(
            <AtlasOverviewSection
                atlasStatus={undefined}
                services={services}
                lastUpdated={new Date()}
            />,
        );
        expect(screen.getByText("Status unknown")).toBeInTheDocument();
    });

    it("displays service latency details when available", () => {
        const services: Record<string, ServiceHealth> = {
            queue: {
                provider_id: "queue",
                status: "healthy",
                latency_ms: 42,
                http_status: 200,
                message: null,
                details: {},
            },
        };
        renderWithRouter(
            <AtlasOverviewSection
                atlasStatus="healthy"
                services={services}
                lastUpdated={new Date()}
            />,
        );
        expect(screen.getByText(/queue/)).toBeInTheDocument();
        expect(screen.getByText(/42ms/)).toBeInTheDocument();
    });

    it("shows offline and unknown services in plain language even when HTTP returned 200", () => {
        const services: Record<string, ServiceHealth> = {
            fileshare: {
                provider_id: "fileshare",
                status: "offline",
                latency_ms: null,
                http_status: 200,
                message: "Connection refused",
                details: {},
            },
            worker: {
                provider_id: "worker",
                status: "unrecognized",
                latency_ms: 42,
                http_status: 200,
                message: null,
                details: {},
            },
        };
        renderWithRouter(
            <AtlasOverviewSection
                atlasStatus="degraded"
                services={services}
                lastUpdated={new Date()}
            />,
        );

        expect(screen.getByText("Services needing attention:")).toBeVisible();
        expect(screen.getByText(/fileshare: Unavailable · response time not reported/)).toBeVisible();
        expect(screen.getByText(/worker: Status unknown · response time 42 ms/)).toBeVisible();
        expect(screen.getAllByText("Atlas Core's connection to this address was refused.").length).toBeGreaterThan(0);
        expect(screen.queryByText(/fileshare: offline|worker: unrecognized/i)).not.toBeInTheDocument();
    });
});
