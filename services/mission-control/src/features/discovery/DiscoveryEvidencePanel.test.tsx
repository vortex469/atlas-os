import { cleanup, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
    DiscoveryItemEvidence,
    DiscoveryReleaseEvaluation,
    DiscoveryReleaseEvaluationStatus,
} from "../../types/discovery";
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

function evaluation(
    status: DiscoveryReleaseEvaluationStatus,
    overrides: Partial<DiscoveryReleaseEvaluation> = {},
): DiscoveryReleaseEvaluation {
    return {
        status,
        baseline: { version: "0.15.0", source: "item_version" },
        latest_candidate: null,
        reason: null,
        ...overrides,
    };
}

const RELEASE_EVALUATION_STATES: readonly DiscoveryReleaseEvaluationStatus[] = [
    "up_to_date",
    "update_available",
    "baseline_ahead",
    "conflicted",
    "stale_evidence",
    "no_baseline",
    "no_dynamic_evidence",
    "insufficient_information",
];

function releaseEvaluationSection(): HTMLElement {
    const title = screen.getByText("Release evaluation");
    const section = title.closest("div[role='status'], div[role='alert']");
    if (!(section instanceof HTMLElement)) {
        throw new Error("release evaluation section not found");
    }
    return section;
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

    describe("release evaluation", () => {
        const stateTitles: Record<DiscoveryReleaseEvaluationStatus, string> = {
            up_to_date: "Up to date",
            update_available: "Update available",
            baseline_ahead: "Baseline ahead",
            conflicted: "Conflicted release claims",
            stale_evidence: "Stale release evidence",
            no_baseline: "No baseline version",
            no_dynamic_evidence: "No dynamic release evidence",
            insufficient_information: "Insufficient information",
        };

        it.each(RELEASE_EVALUATION_STATES)(
            "presents the %s bounded state",
            (status) => {
                render(
                    <DiscoveryEvidencePanel
                        evidence={evidence({ release_evaluation: evaluation(status) })}
                        isLoading={false}
                        error={null}
                    />,
                );
                const section = releaseEvaluationSection();
                expect(within(section).getByText(stateTitles[status])).toBeInTheDocument();
                expect(within(section).getByText("Release evaluation")).toBeInTheDocument();
            },
        );

        it.each(["up_to_date", "update_available", "baseline_ahead"] as const)(
            "shows the curated baseline and latest candidate for %s when present",
            (status) => {
                render(
                    <DiscoveryEvidencePanel
                        evidence={evidence({
                            release_evaluation: evaluation(status, {
                                baseline: { version: "0.15.0", source: "curated" },
                                latest_candidate: "0.16.1",
                            }),
                        })}
                        isLoading={false}
                        error={null}
                    />,
                );
                const section = releaseEvaluationSection();
                expect(within(section).getByText("Baseline version")).toBeInTheDocument();
                expect(within(section).getByText("0.15.0")).toBeInTheDocument();
                expect(within(section).getByText("Baseline source")).toBeInTheDocument();
                expect(within(section).getByText("Curated")).toBeInTheDocument();
                expect(within(section).getByText("Latest candidate")).toBeInTheDocument();
                expect(within(section).getByText("0.16.1")).toBeInTheDocument();
            },
        );

        it.each([
            "conflicted",
            "stale_evidence",
            "no_baseline",
            "no_dynamic_evidence",
            "insufficient_information",
        ] as const)(
            "never shows a selected latest candidate for %s",
            (status) => {
                render(
                    <DiscoveryEvidencePanel
                        evidence={evidence({
                            release_evaluation: evaluation(status, {
                                baseline: status === "no_baseline" ? null : evaluation(status).baseline,
                            }),
                        })}
                        isLoading={false}
                        error={null}
                    />,
                );
                const section = releaseEvaluationSection();
                expect(within(section).queryByText("Latest candidate")).not.toBeInTheDocument();
                expect(within(section).queryByText("0.16.1")).not.toBeInTheDocument();
            },
        );

        it("omits baseline facts when no baseline is present", () => {
            render(
                <DiscoveryEvidencePanel
                    evidence={evidence({
                        release_evaluation: evaluation("no_baseline", { baseline: null }),
                    })}
                    isLoading={false}
                    error={null}
                />,
            );
            const section = releaseEvaluationSection();
            expect(within(section).queryByText("Baseline version")).not.toBeInTheDocument();
            expect(within(section).queryByText("Baseline source")).not.toBeInTheDocument();
            expect(within(section).queryByText("Latest candidate")).not.toBeInTheDocument();
        });

        it.each(["up_to_date", "update_available", "baseline_ahead"] as const)(
            "uses a positive tone for %s",
            (status) => {
                render(
                    <DiscoveryEvidencePanel
                        evidence={evidence({ release_evaluation: evaluation(status) })}
                        isLoading={false}
                        error={null}
                    />,
                );
                expect(releaseEvaluationSection().className).toContain("emerald");
            },
        );

        it.each(["stale_evidence", "insufficient_information"] as const)(
            "renders %s as a non-positive caution state",
            (status) => {
                render(
                    <DiscoveryEvidencePanel
                        evidence={evidence({ release_evaluation: evaluation(status) })}
                        isLoading={false}
                        error={null}
                    />,
                );
                const section = releaseEvaluationSection();
                expect(section).toHaveAttribute("role", "status");
                expect(section.className).toContain("amber");
                expect(section.className).not.toContain("emerald");
                expect(within(section).getByText(/No positive comparison is made\./)).toBeInTheDocument();
            },
        );

        it("renders no_baseline and no_dynamic_evidence as non-positive neutral states", () => {
            for (const status of ["no_baseline", "no_dynamic_evidence"] as const) {
                render(
                    <DiscoveryEvidencePanel
                        evidence={evidence({ release_evaluation: evaluation(status) })}
                        isLoading={false}
                        error={null}
                    />,
                );
                const section = releaseEvaluationSection();
                expect(section).toHaveAttribute("role", "status");
                expect(section.className).not.toContain("emerald");
                expect(section.className).not.toContain("red");
                cleanup();
            }
        });

        it("renders conflicted as an alert that preserves curated authority", () => {
            render(
                <DiscoveryEvidencePanel
                    evidence={evidence({
                        conflict_state: "curated_conflict",
                        release_evaluation: evaluation("conflicted"),
                    })}
                    isLoading={false}
                    error={null}
                />,
            );
            const section = releaseEvaluationSection();
            expect(section).toHaveAttribute("role", "alert");
            expect(section.className).toContain("red");
            expect(within(section).getByText(
                "Release evidence conflicts, so no latest version is selected. Curated catalog data remains authoritative. No change is recommended or implied.",
            )).toBeInTheDocument();
            expect(within(section).queryByText("Latest candidate")).not.toBeInTheDocument();
        });

        it("presents update_available as informational only", () => {
            render(
                <DiscoveryEvidencePanel
                    evidence={evidence({
                        release_evaluation: evaluation("update_available", {
                            latest_candidate: "0.16.1",
                        }),
                    })}
                    isLoading={false}
                    error={null}
                />,
            );
            expect(
                within(releaseEvaluationSection()).getByText(
                    /Informational only; nothing is scheduled, proposed, or applied\./,
                ),
            ).toBeInTheDocument();
        });

        it("omits the release evaluation subsection when the field is absent", () => {
            render(<DiscoveryEvidencePanel evidence={evidence()} isLoading={false} error={null} />);
            expect(screen.queryByText("Release evaluation")).not.toBeInTheDocument();
        });

        it("omits the release evaluation subsection when the field is null", () => {
            render(
                <DiscoveryEvidencePanel
                    evidence={evidence({ release_evaluation: null })}
                    isLoading={false}
                    error={null}
                />,
            );
            expect(screen.queryByText("Release evaluation")).not.toBeInTheDocument();
        });

        it.each(RELEASE_EVALUATION_STATES)(
            "contains no action or mutation controls for %s",
            (status) => {
                render(
                    <DiscoveryEvidencePanel
                        evidence={evidence({ release_evaluation: evaluation(status) })}
                        isLoading={false}
                        error={null}
                    />,
                );
                const section = releaseEvaluationSection();
                expect(within(section).queryByRole("button")).not.toBeInTheDocument();
                expect(within(section).queryByRole("link")).not.toBeInTheDocument();
                expect(within(section).queryByRole("checkbox")).not.toBeInTheDocument();
                expect(within(section).queryByRole("radio")).not.toBeInTheDocument();
                expect(within(section).queryByRole("switch")).not.toBeInTheDocument();
                expect(within(section).queryByRole("textbox")).not.toBeInTheDocument();
            },
        );
    });
});
