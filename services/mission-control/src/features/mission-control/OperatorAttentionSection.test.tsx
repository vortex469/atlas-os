import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { OperatorAttentionSection } from "./OperatorAttentionSection";
import type { AceFinding, AceRecommendation } from "../../types/ace";

describe("OperatorAttentionSection", () => {
    const renderWithRouter = (component: React.ReactElement) => {
        return render(<BrowserRouter>{component}</BrowserRouter>);
    };

    it("renders operator attention section", () => {
        renderWithRouter(<OperatorAttentionSection />);
        expect(screen.getByText("Operator Attention")).toBeInTheDocument();
    });

    it("shows no action required when healthy", () => {
        renderWithRouter(
            <OperatorAttentionSection
                blockedWorkflowCount={0}
                degradedServiceCount={0}
                unavailableProviderCount={0}
                findings={[]}
                recommendations={[]}
            />,
        );
        expect(screen.getByText("No action required")).toBeInTheDocument();
        expect(
            screen.getByText(/All systems operating normally/),
        ).toBeInTheDocument();
    });

    it("shows blocked workflow alert", () => {
        renderWithRouter(
            <OperatorAttentionSection blockedWorkflowCount={2} />,
        );
        expect(screen.getByText(/2 Blocked Workflows/)).toBeInTheDocument();
    });

    it("shows degraded service alert", () => {
        renderWithRouter(
            <OperatorAttentionSection degradedServiceCount={1} />,
        );
        expect(screen.getByText(/1 Degraded Service/)).toBeInTheDocument();
    });

    it("shows unavailable provider alert", () => {
        renderWithRouter(
            <OperatorAttentionSection
                unavailableProviderCount={3}
            />,
        );
        expect(screen.getByText(/3 Unavailable Providers/)).toBeInTheDocument();
    });

    it("displays critical findings", () => {
        const findings: AceFinding[] = [
            {
                id: "f1",
                severity: "critical",
                category: "security",
                source: "scanner",
                title: "SQL Injection Risk",
                message: "Potential SQL injection detected",
                recommendation: null,
                component: "api",
                metric: {},
                details: {},
                affects_health: true,
                score_penalty: 10,
            },
        ];
        renderWithRouter(<OperatorAttentionSection findings={findings} />);
        expect(screen.getByText(/1 Critical Finding/)).toBeInTheDocument();
        expect(screen.getByText("SQL Injection Risk")).toBeInTheDocument();
    });

    it("displays critical recommendations", () => {
        const recommendations: AceRecommendation[] = [
            {
                title: "Upgrade database driver",
                reason: "Current version has CVE",
                priority: "critical",
                confidence: 0.95,
                estimated_effort: "high",
                component: "database",
            },
        ];
        renderWithRouter(<OperatorAttentionSection recommendations={recommendations} />);
        expect(screen.getByText(/1 Recommended Action/)).toBeInTheDocument();
        expect(screen.getByText("Upgrade database driver")).toBeInTheDocument();
    });

    it("shows component labels in findings", () => {
        const findings: AceFinding[] = [
            {
                id: "f1",
                severity: "critical",
                category: "test",
                source: "test",
                title: "Test Issue",
                message: "msg",
                recommendation: null,
                component: "worker",
                metric: {},
                details: {},
                affects_health: true,
                score_penalty: 5,
            },
        ];
        renderWithRouter(<OperatorAttentionSection findings={findings} />);
        expect(screen.getByText(/worker/)).toBeInTheDocument();
    });

    it("limits findings display to first 3", () => {
        const findings: AceFinding[] = Array.from({ length: 5 }, (_, i) => ({
            id: `f${i}`,
            severity: "critical",
            category: "test",
            source: "test",
            title: `Issue ${i}`,
            message: "msg",
            recommendation: null,
            component: null,
            metric: {},
            details: {},
            affects_health: true,
            score_penalty: 5,
        }));
        renderWithRouter(<OperatorAttentionSection findings={findings} />);
        expect(screen.getByText(/5 Critical Findings/)).toBeInTheDocument();
        expect(screen.getByText(/\+2 more findings/)).toBeInTheDocument();
    });
});
