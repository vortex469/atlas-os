import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AceFinding } from "../types/ace";
import { FindingCard } from "./FindingCard";

function finding(unavailableEntities: unknown[]): AceFinding {
    return {
        id: "finding-1",
        severity: "warning",
        category: "provider_unavailable",
        source: "atlas_core",
        title: "Provider data unavailable",
        message: "Atlas could not read one or more entities.",
        recommendation: null,
        component: null,
        metric: {},
        details: { unavailable_entities: unavailableEntities },
        affects_health: true,
        score_penalty: 1,
    };
}

describe("FindingCard unavailable entity labels", () => {
    it("uses the entity ID and a readable state when the name is missing", () => {
        render(<FindingCard finding={finding([{ entity_id: "light.office", state: "unavailable" }])} />);

        expect(screen.getByText("light.office")).toBeVisible();
        expect(screen.getByText("Unavailable")).toBeVisible();
    });

    it("explains when an entity identity and status are missing", () => {
        render(<FindingCard finding={finding([{}])} />);

        expect(screen.getByText("Entity not identified")).toBeVisible();
        expect(screen.getByText("Status unknown")).toBeVisible();
    });

    it("ignores malformed array entries and trims readable fields", () => {
        render(<FindingCard finding={finding([null, [], { name: "  Office lamp  ", state: "  unknown " }])} />);

        expect(screen.getByText("Office lamp")).toBeVisible();
        expect(screen.getByText("Status unknown")).toBeVisible();
        expect(screen.queryByText("unknown", { exact: true })).not.toBeInTheDocument();
    });
});
