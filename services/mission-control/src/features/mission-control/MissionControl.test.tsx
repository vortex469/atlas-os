import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useOverviewEvidence } from "./useOverviewEvidence";
import { MissionControl } from "./MissionControl";

vi.mock("./useOverviewEvidence", () => ({ useOverviewEvidence: vi.fn() }));

describe("MissionControl overview refresh label", () => {
    beforeEach(() => vi.mocked(useOverviewEvidence).mockReset());

    it.each([
        { loading: true, hasLoaded: false, label: "Loading…" },
        { loading: true, hasLoaded: true, label: "Refreshing…" },
        { loading: false, hasLoaded: true, label: "Refresh" },
    ])("labels loading=$loading, hasLoaded=$hasLoaded as $label", ({ loading, hasLoaded, label }) => {
        vi.mocked(useOverviewEvidence).mockReturnValue({
            evidence: {},
            loading,
            hasLoaded,
            refresh: vi.fn(),
        });

        render(<MemoryRouter><MissionControl /></MemoryRouter>);

        const button = screen.getByRole("button", { name: label });
        if (loading) expect(button).toBeDisabled();
        else expect(button).toBeEnabled();
    });
});
