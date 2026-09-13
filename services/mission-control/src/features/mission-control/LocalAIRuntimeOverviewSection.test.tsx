import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { LocalAIRuntimeOverviewSection } from "./LocalAIRuntimeOverviewSection";

const renderWithRouter = (component: React.ReactNode) => {
    return render(
        <BrowserRouter>{component}</BrowserRouter>
    );
};

describe("LocalAIRuntimeOverviewSection", () => {
    it("renders local AI runtime section", () => {
        renderWithRouter(<LocalAIRuntimeOverviewSection />);
        expect(screen.getByText("Local AI Runtime")).toBeInTheDocument();
    });

    it("shows unknown when no evidence available", () => {
        renderWithRouter(<LocalAIRuntimeOverviewSection isAvailable={undefined} />);
        expect(screen.getByText("Unknown")).toBeInTheDocument();
        expect(
            screen.queryAllByText((_content, element) => {
                return element?.textContent?.includes("Local AI runtime status is not exposed by Atlas Core") || false;
            })[0],
        ).toBeInTheDocument();
    });

    it("shows unavailable when not configured", () => {
        renderWithRouter(<LocalAIRuntimeOverviewSection isAvailable={false} />);
        expect(screen.getByText("Unavailable")).toBeInTheDocument();
        expect(
            screen.queryAllByText((_content, element) => {
                return element?.textContent?.includes("The Local AI runtime is not running or not accessible") || false;
            })[0],
        ).toBeInTheDocument();
    });

    it("shows degraded when endpoint is unhealthy", () => {
        renderWithRouter(
            <LocalAIRuntimeOverviewSection
                isAvailable={true}
                endpointHealthy={false}
            />,
        );
        expect(screen.getByText("Degraded")).toBeInTheDocument();
        expect(
            screen.queryAllByText((_content, element) => {
                return element?.textContent?.includes("Check runtime logs and network connectivity") || false;
            })[0],
        ).toBeInTheDocument();
    });

    it("shows healthy when endpoint is operational", () => {
        renderWithRouter(
            <LocalAIRuntimeOverviewSection
                isAvailable={true}
                endpointHealthy={true}
                modelIdentity="llama-2-7b"
            />,
        );
        expect(screen.getByText("Healthy")).toBeInTheDocument();
        expect(screen.getByText("llama-2-7b")).toBeInTheDocument();
    });

    it("displays status message when available", () => {
        renderWithRouter(
            <LocalAIRuntimeOverviewSection
                isAvailable={true}
                endpointHealthy={true}
                statusMessage="All systems operational"
            />,
        );
        expect(
            screen.getByText("All systems operational"),
        ).toBeInTheDocument();
    });

    it("shows extension point note", () => {
        renderWithRouter(<LocalAIRuntimeOverviewSection />);
        expect(
            screen.getByText(
                /This section will expand as the Atlas Local AI Runtime/,
            ),
        ).toBeInTheDocument();
        expect(
            screen.getByText(/Model availability and version information/),
        ).toBeInTheDocument();
    });
});
