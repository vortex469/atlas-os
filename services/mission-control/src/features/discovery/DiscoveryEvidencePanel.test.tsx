import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { DiscoveryItemEvidence } from "../../types/discovery";
import { DiscoveryEvidencePanel } from "./DiscoveryEvidencePanel";

function evidence(overrides: Partial<DiscoveryItemEvidence> = {}): DiscoveryItemEvidence {
    return {
        schema_version: "discovery-merged-item-v1",
        catalog_item_id: "frigate",
        curated: {} as DiscoveryItemEvidence["curated"],
        dynamic_claims: [{
            fact_kind: "latest_stable_release",
            version: "0.16.1",
            published_at: "2026-08-17T09:00:00Z",
            freshness: "fresh",
            provenance: {
                source_id: "frigate-github-latest-release-v1",
                source_type: "github_latest_release",
                trust_tier: "supplemental",
                repository: "blakeblackshear/frigate",
                upstream_release_id: 123,
                retrieved_at: "2026-08-18T09:00:00Z",
                expires_at: "2026-08-19T09:00:00Z",
            },
        }],
        source_states: [{
            source_id: "frigate-github-latest-release-v1",
            health: "healthy",
            cache_state: "available",
        }],
        conflict_state: "agreement",
        ...overrides,
    };
}

describe("DiscoveryEvidencePanel", () => {
    it("announces loading accessibly", () => {
        render(<DiscoveryEvidencePanel evidence={null} isLoading error={null} />);
        expect(screen.getByRole("status")).toHaveTextContent("Loading source evidence");
    });

    it("renders provenance, trust, age, freshness, health, and agreement", () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date("2026-08-18T11:00:00Z"));
        render(<DiscoveryEvidencePanel evidence={evidence()} isLoading={false} error={null} />);

        expect(screen.getByText("Sources agree")).toBeInTheDocument();
        expect(screen.getByText("Fresh")).toBeInTheDocument();
        expect(screen.getByText("Health: Healthy")).toBeInTheDocument();
        expect(screen.getByText("blakeblackshear/frigate")).toBeInTheDocument();
        expect(screen.getByText("Supplemental")).toBeInTheDocument();
        expect(screen.getByText(/2 hours ago/)).toBeInTheDocument();
        vi.useRealTimers();
    });

    it("renders stale, degraded, unavailable, and unknown health explicitly", () => {
        render(<DiscoveryEvidencePanel evidence={evidence({
            dynamic_claims: [{ ...evidence().dynamic_claims[0], freshness: "stale" }],
            source_states: [
                { source_id: "healthy-source", health: "healthy", cache_state: "available" },
                { source_id: "degraded-source", health: "degraded", cache_state: "available" },
                { source_id: "offline-source", health: "unavailable", cache_state: "absent" },
                { source_id: "unknown-source", health: null, cache_state: "corrupt" },
            ],
        })} isLoading={false} error={null} />);

        expect(screen.getByText("Stale")).toBeInTheDocument();
        expect(screen.getByText(
            "Stale evidence may not describe the current upstream release.",
        )).toBeInTheDocument();
        for (const health of ["Healthy", "Degraded", "Unavailable", "Unknown"]) {
            expect(screen.getByText(`Health: ${health}`)).toBeInTheDocument();
        }
        expect(screen.getByText("Corrupt cached evidence was excluded.")).toBeInTheDocument();
        expect(screen.getByText("No cached evidence is available.")).toBeInTheDocument();
    });

    it("renders dynamic_conflict as an alert", () => {
        render(<DiscoveryEvidencePanel evidence={evidence({ conflict_state: "dynamic_conflict" })} isLoading={false} error={null} />);
        expect(within(screen.getByRole("alert")).getByText("Dynamic source conflict")).toBeInTheDocument();
    });

    it("renders curated_conflict and preserves curated authority", () => {
        render(<DiscoveryEvidencePanel evidence={evidence({ conflict_state: "curated_conflict" })} isLoading={false} error={null} />);
        const alert = screen.getByRole("alert");
        expect(within(alert).getByText("Curated evidence conflict")).toBeInTheDocument();
        expect(within(alert).getByText(
            "Supplemental evidence differs from the curated release claim. Curated data remains authoritative.",
        )).toBeInTheDocument();
    });

    it("explains when no dynamic sources are mapped", () => {
        render(<DiscoveryEvidencePanel evidence={evidence({ source_states: [] })} isLoading={false} error={null} />);
        expect(screen.getByText(
            "No dynamic sources are mapped to this catalog item.",
        )).toBeInTheDocument();
    });

    it("falls back to curated-only presentation for empty or corrupt evidence", () => {
        render(<DiscoveryEvidencePanel evidence={evidence({
            dynamic_claims: [],
            source_states: [{ source_id: "source", health: null, cache_state: "corrupt" }],
            conflict_state: "none",
        })} isLoading={false} error={null} />);
        expect(screen.getByText("Curated catalog only")).toBeInTheDocument();
        expect(screen.getByText("Corrupt cached evidence was excluded.")).toBeInTheDocument();
    });

    it("uses a non-blocking alert when the evidence request fails", () => {
        render(<DiscoveryEvidencePanel evidence={null} isLoading={false} error="Source offline" />);
        const alert = screen.getByRole("alert");
        expect(alert).toHaveTextContent("Dynamic evidence unavailable");
        expect(alert).toHaveTextContent("Showing the curated catalog only");
    });

    it("contains no mutation or execution controls", () => {
        render(<DiscoveryEvidencePanel evidence={evidence()} isLoading={false} error={null} />);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
        expect(screen.queryByRole("link")).not.toBeInTheDocument();
    });
});
