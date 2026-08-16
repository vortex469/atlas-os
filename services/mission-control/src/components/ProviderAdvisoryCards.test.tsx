import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AceFinding, AceRecommendation } from "../types/ace";
import { FindingCard } from "./FindingCard";
import { RecommendationCard } from "./RecommendationCard";

describe("provider advisory cards", () => {
    it("labels findings as advisory without presenting execution controls", () => {
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
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
        expect(screen.queryByText(/Start|Restart|Apply|Remediate/i)).not.toBeInTheDocument();
    });

    it("labels recommendations as advisory rather than executable actions", () => {
        const recommendation = {
            title: "Review provider capacity",
            reason: "Capacity is approaching its configured threshold.",
            component: "proxmox",
            priority: "medium",
            confidence: 0.9,
            estimated_effort: "low",
        } as AceRecommendation;
        render(<RecommendationCard recommendation={recommendation} />);
        expect(screen.getByText("Advisory recommendation")).toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
        expect(screen.queryByText("Recommended Action")).not.toBeInTheDocument();
    });
});
