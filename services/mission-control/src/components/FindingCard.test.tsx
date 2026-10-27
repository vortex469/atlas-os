import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AceFinding } from "../types/ace";
import { FindingCard } from "./FindingCard";

const finding: AceFinding = {
    id: "finding-1", severity: "warning", source: "homeassistant", category: "availability",
    title: "Reported issue", message: "Reported evidence", recommendation: null, component: "homeassistant",
    affects_health: true, score_penalty: 1, metric: {}, details: {},
};

describe("finding entity details", () => {
    it("contains non-displayable fields from the public free-form details dictionary", () => {
        render(<FindingCard finding={{ ...finding, details: { unavailable_entities: [
            { entity_id: { private: "PRIVATE-ENTITY-CANARY" }, name: ["PRIVATE-ENTITY-CANARY"], state: { private: "PRIVATE-ENTITY-CANARY" } },
            { entity_id: "sensor.power", name: "Power", state: "unavailable" },
            null, 42, [],
        ] } }} />);
        expect(screen.getByText("Reported evidence")).toBeVisible();
        expect(screen.getByText("Unknown entity")).toBeVisible();
        expect(screen.getByText("unknown")).toBeVisible();
        expect(screen.getByText("Power")).toBeVisible();
        expect(screen.getByText("Showing 2 of 2")).toBeVisible();
        expect(screen.queryByText(/PRIVATE-ENTITY-CANARY/)).not.toBeInTheDocument();
    });
});
