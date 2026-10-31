import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { AceFinding, AceRecommendation } from "../types/ace";
import { FindingCard } from "./FindingCard";
import { RecommendationCard } from "./RecommendationCard";

describe("provider advisory cards", () => {
    it("keeps a plain health effect visible and technical finding details collapsed", async () => {
        const user = userEvent.setup();
        const finding = {
            id: "finding-1",
            source: "proxmox",
            component: "proxmox",
            category: "state_mismatch",
            severity: "warning",
            title: "Observed state does not match monitoring expectation",
            message: "Observed stopped; monitoring expectation running.",
            affects_health: true,
            score_penalty: 10,
            details: {},
        } as AceFinding;
        render(<FindingCard finding={finding} />);
        expect(screen.getByText(/Advisory finding/)).toBeInTheDocument();
        expect(screen.getByText("Affects system health")).toBeInTheDocument();
        expect(screen.getByText("State Mismatch")).not.toBeVisible();
        await user.click(screen.getByText("Technical details"));
        expect(screen.getByText("State Mismatch")).toBeInTheDocument();
        expect(screen.getByText("Health score reduction")).toBeInTheDocument();
        expect(screen.getByText("10 points")).toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
        expect(screen.queryByText(/Start|Restart|Apply|Remediate/i)).not.toBeInTheDocument();
    });

    it("does not claim a health-score reduction for findings excluded from health", async () => {
        const user = userEvent.setup();
        const finding = {
            id: "finding-info",
            source: "proxmox",
            component: "proxmox",
            category: "state_mismatch",
            severity: "info",
            title: "Informational observation",
            message: "This observation is informational.",
            affects_health: false,
            score_penalty: 10,
            details: {},
        } as AceFinding;

        render(<FindingCard finding={finding} />);
        expect(screen.getByText("Does not affect system health")).toBeInTheDocument();
        await user.click(screen.getByText("Technical details"));
        expect(screen.getByText("None")).toBeInTheDocument();
    });

    it("labels recommendations as Atlas suggestions rather than executable actions", () => {
        const recommendation = {
            title: "Review provider capacity",
            reason: "Capacity is approaching its configured threshold.",
            component: "proxmox",
            priority: "medium",
            confidence: 0.9,
            estimated_effort: "low",
        } as AceRecommendation;
        render(<RecommendationCard recommendation={recommendation} />);
        expect(screen.getByText("Atlas suggestion")).toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
        expect(screen.queryByText("Recommended Action")).not.toBeInTheDocument();
    });

    it("withholds credential and URL text from reported findings and suggestions", () => {
        const finding = {
            id: "finding-sensitive",
            source: "proxmox",
            component: "proxmox",
            category: "provider_unavailable",
            severity: "warning",
            title: "Provider at https://operator:canary-password@example.invalid/",
            message: "Authorization: Bearer canary-token",
            affects_health: true,
            score_penalty: 1,
            details: {},
        } as AceFinding;
        const recommendation = {
            title: "Review provider capacity",
            reason: "Credential check failed for https://operator:canary-password@example.invalid/?token=canary-token",
            component: "proxmox",
            priority: "medium",
            confidence: 0.9,
            estimated_effort: "low",
        } as AceRecommendation;

        render(<><FindingCard finding={finding} /><RecommendationCard recommendation={recommendation} /></>);

        expect(screen.getAllByText("[Sensitive text withheld]")).toHaveLength(3);
        expect(screen.queryByText(/canary-token|canary-password|operator|example\.invalid/)).not.toBeInTheDocument();
    });
});
