import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
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
    const title = screen.getByText("Version comparison");
    const section = title.closest("div[role='status'], div[role='alert']");
    if (!(section instanceof HTMLElement)) {
        throw new Error("release evaluation section not found");
    }
    return section;
}

describe("DiscoveryEvidencePanel", () => {
    it("announces loading accessibly", () => {
        render(<DiscoveryEvidencePanel evidence={null} isLoading error={null} />);
        expect(screen.getByRole("status")).toHaveTextContent("Checking release information");
    });

    it("leads with release freshness and keeps source records optional", () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date("2026-08-18T11:00:00Z"));
        render(<DiscoveryEvidencePanel evidence={evidence()} isLoading={false} error={null} />);

        expect(screen.getByText("Release information agrees")).toBeInTheDocument();
        expect(screen.getByText("Current report")).toBeInTheDocument();
        expect(screen.getByText("Source: Available")).toBeInTheDocument();
        expect(screen.getByText("Released (local time)").parentElement?.querySelector("time")).toHaveAttribute("dateTime", "2026-08-17T09:00:00Z");
        expect(screen.getByText("Checked by Atlas (local time)").parentElement).toHaveTextContent("2 hours ago");
        const sourceDetails = screen.getByText("Source details").closest("details");
        expect(sourceDetails).not.toHaveAttribute("open");
        expect(within(sourceDetails as HTMLDetailsElement).getByText("blakeblackshear/frigate")).not.toBeVisible();
        expect(screen.getByText("Release reports are for reference only. They don’t change this catalog item.")).toBeInTheDocument();
        expect(within(sourceDetails as HTMLDetailsElement).getByText("Additional report; catalog entry stays as listed")).not.toBeVisible();
        fireEvent.click(within(sourceDetails as HTMLDetailsElement).getByText("Source details"));
        expect(within(sourceDetails as HTMLDetailsElement).getByText("blakeblackshear/frigate")).toBeVisible();
        expect(within(sourceDetails as HTMLDetailsElement).getByText("Additional report; catalog entry stays as listed")).toBeVisible();
        const sourceSummary = screen.getByRole("list", { name: "Discovery source health" });
        const technicalDetails = within(sourceSummary).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Source ID: frigate-github-latest-release-v1")).not.toBeVisible();
        fireEvent.click(within(technicalDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Source ID: frigate-github-latest-release-v1")).toBeVisible();
        expect(screen.getByText(/2 hours ago/)).toBeInTheDocument();
        expect(screen.getByText("Checked by Atlas (local time)").parentElement?.querySelector("time")).toHaveAttribute("dateTime", "2026-08-18T09:00:00Z");
        expect(screen.getByText("Source data valid until (local time)").parentElement?.querySelector("time")).toHaveAttribute("dateTime", "2026-08-19T09:00:00Z");
        vi.useRealTimers();
    });

    it("shows unavailable for malformed release evidence timestamps", () => {
        const claim = evidence().dynamic_claims[0];
        render(<DiscoveryEvidencePanel evidence={evidence({ dynamic_claims: [{
            ...claim,
            published_at: "not-a-time",
            provenance: { ...claim.provenance, retrieved_at: "2026-02-30T09:00:00Z", expires_at: "not-a-time" },
        }] })} isLoading={false} error={null} />);
        expect(screen.getByText("Released (local time)").parentElement).toHaveTextContent("Time unavailable");
        expect(screen.getByText("Checked by Atlas (local time)").parentElement).toHaveTextContent("Time unavailable");
        fireEvent.click(screen.getByText("Source details"));
        expect(screen.getByText("Source data valid until (local time)").parentElement).toHaveTextContent("Time unavailable");
        expect(screen.queryByText("Invalid Date")).not.toBeInTheDocument();
    });

    it("does not describe future retrieval timestamps as recent", () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date("2026-08-18T11:00:00Z"));
        const claim = evidence().dynamic_claims[0];
        render(<DiscoveryEvidencePanel evidence={evidence({ dynamic_claims: [{
            ...claim,
            provenance: { ...claim.provenance, retrieved_at: "2026-08-19T09:00:00Z" },
        }] })} isLoading={false} error={null} />);
        expect(screen.getByText("Checked by Atlas (local time)").parentElement).toHaveTextContent("reported time is in the future");
        expect(screen.queryByText("less than 1 hour ago")).not.toBeInTheDocument();
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

        expect(screen.getByText("May be out of date")).toBeInTheDocument();
        expect(screen.getByText(
            "This information may not reflect the latest release.",
        )).toBeInTheDocument();
        for (const health of ["Available", "Partly available", "Unavailable", "Status not reported"]) {
            expect(screen.getByText(`Source: ${health}`)).toBeInTheDocument();
        }
        expect(screen.getByText("Atlas ignored unreadable saved evidence.")).toBeInTheDocument();
        expect(screen.getByText("Saved evidence: None found")).toBeInTheDocument();
    });

    it("renders dynamic_conflict as an alert", () => {
        render(<DiscoveryEvidencePanel evidence={evidence({ conflict_state: "dynamic_conflict" })} isLoading={false} error={null} />);
        expect(within(screen.getByRole("alert")).getByText("Release sources disagree")).toBeInTheDocument();
    });

    it("renders curated_conflict and preserves curated authority", () => {
        render(<DiscoveryEvidencePanel evidence={evidence({ conflict_state: "curated_conflict" })} isLoading={false} error={null} />);
        const alert = screen.getByRole("alert");
        expect(within(alert).getByText("Release report differs from the catalog")).toBeInTheDocument();
        expect(within(alert).getByText("A release report differs from the catalog. The catalog entry remains unchanged.")).toBeInTheDocument();
    });

    it("explains when no dynamic sources are mapped", () => {
        render(<DiscoveryEvidencePanel evidence={evidence({ source_states: [] })} isLoading={false} error={null} />);
        expect(screen.getByText(
            "No release sources are available for this item.",
        )).toBeInTheDocument();
    });

    it("falls back to curated-only presentation for empty or corrupt evidence", () => {
        render(<DiscoveryEvidencePanel evidence={evidence({
            dynamic_claims: [],
            source_states: [{ source_id: "source", health: null, cache_state: "corrupt" }],
            conflict_state: "none",
        })} isLoading={false} error={null} />);
        expect(screen.getByText("Only catalog information is available")).toBeInTheDocument();
        expect(screen.getByText("Atlas ignored unreadable saved evidence.")).toBeInTheDocument();
    });

    it("uses a non-blocking alert when the evidence request fails", () => {
        const onRetry = vi.fn();
        render(<DiscoveryEvidencePanel evidence={null} isLoading={false} error="Source offline" onRetry={onRetry} />);
        const alert = screen.getByRole("alert");
        expect(alert).toHaveTextContent("Release information unavailable");
        expect(alert).toHaveTextContent("Atlas could not check release information.");
        expect(alert).toHaveTextContent("The catalog information is still available and unchanged.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Source offline")).not.toBeVisible();
        fireEvent.click(within(technicalDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Source offline")).toBeVisible();
        screen.getByRole("button", { name: "Retry release check" }).click();
        expect(onRetry).toHaveBeenCalledOnce();
    });

    it("contains no mutation or execution controls", () => {
        render(<DiscoveryEvidencePanel evidence={evidence()} isLoading={false} error={null} />);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
        expect(screen.queryByRole("link")).not.toBeInTheDocument();
    });

    describe("release evaluation", () => {
        const stateTitles: Record<DiscoveryReleaseEvaluationStatus, string> = {
            up_to_date: "Versions match",
            update_available: "Newer release reported",
            baseline_ahead: "Catalog lists a newer version",
            conflicted: "Release information conflicts",
            stale_evidence: "Release information may be out of date",
            no_baseline: "Catalog version unavailable",
            no_dynamic_evidence: "No release reports available",
            insufficient_information: "Versions cannot be compared",
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
                expect(within(section).getByText("Version comparison")).toBeInTheDocument();
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
                expect(within(section).getByText("Catalog version")).toBeInTheDocument();
                expect(within(section).getByText("0.15.0")).toBeInTheDocument();
                expect(within(section).getByText("Catalog version source")).toBeInTheDocument();
                expect(within(section).getByText("Curated")).toBeInTheDocument();
                expect(within(section).getByText("Latest reported release")).toBeInTheDocument();
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
                expect(within(section).queryByText("Latest reported release")).not.toBeInTheDocument();
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
            expect(within(section).queryByText("Catalog version")).not.toBeInTheDocument();
            expect(within(section).queryByText("Catalog version source")).not.toBeInTheDocument();
            expect(within(section).queryByText("Latest reported release")).not.toBeInTheDocument();
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
                expect(section.textContent).toMatch(/cannot compare it with confidence|No update is recommended/);
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
                "Sources disagree, so Atlas does not choose a latest version. The catalog version remains the reference.",
            )).toBeInTheDocument();
            expect(within(section).queryByText("Latest reported release")).not.toBeInTheDocument();
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
                    /This is information only; no change is proposed or applied\./,
                ),
            ).toBeInTheDocument();
        });

        it("omits the release evaluation subsection when the field is absent", () => {
            render(<DiscoveryEvidencePanel evidence={evidence()} isLoading={false} error={null} />);
            expect(screen.queryByText("Version comparison")).not.toBeInTheDocument();
        });

        it("omits the release evaluation subsection when the field is null", () => {
            render(
                <DiscoveryEvidencePanel
                    evidence={evidence({ release_evaluation: null })}
                    isLoading={false}
                    error={null}
                />,
            );
            expect(screen.queryByText("Version comparison")).not.toBeInTheDocument();
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
