import { describe, expect, it } from "vitest";

import router from "../app/router.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";

const sourceModules = import.meta.glob(
    "../**/*.{ts,tsx}",
    { eager: true, import: "default", query: "?raw" },
) as Record<string, string>;

const productionSources = Object.fromEntries(
    Object.entries(sourceModules).filter(([path]) => (
        !path.includes(".test.")
        && !path.includes("/test/")
        && !path.includes("/security/")
    )),
);

const source = Object.entries(productionSources)
    .map(([path, contents]) => `${path}\n${contents}`)
    .join("\n");

describe("v0.25 Agent intake simulation presentation boundary", () => {
    it("has no API client, hook, type, component, page, or route", () => {
        expect(Object.keys(productionSources)).not.toEqual(expect.arrayContaining([
            expect.stringMatching(/agent[-_]?intake[-_]?simulation/i),
        ]));
        expect(source).not.toMatch(/agent[-_ ]installation[-_ ]intake[-_ ]simulation/i);
        expect(source).not.toMatch(/agent[-_ ]intake[-_ ]simulation/i);
        expect(source).not.toMatch(/intake[-_ ]record/i);
        expect(router).not.toMatch(/intake|simulation/i);
        expect(navigation).not.toMatch(/intake|simulation/i);
    });

    it("has no simulated-intake mutation, action navigation, or execution label", () => {
        expect(source).not.toMatch(/atlas(?:Agent)?\.(?:post|put|patch|delete)[^\n]*(?:intake|simulation)/i);
        expect(source).not.toMatch(/(?:href|to|navigate\()[^\n]*simulation/i);

        for (const label of [
            "install", "run", "execute", "deploy", "dispatch", "deliver",
            "send(?:-|\\s+)to(?:-|\\s+)agent", "start(?:-|\\s+)workflow", "rollback",
        ]) {
            expect(source).not.toMatch(new RegExp(
                `(?:intake|simulation)[^\\n]{0,160}(?:>|aria-label=["'])\\s*${label}(?:\\s+now)?(?:\\s*<|["'])`,
                "i",
            ));
        }
    });

    it("cannot expose simulated evidence or sensitive intake details", () => {
        for (const marker of [
            "agent_simulated_not_received",
            "simulated_valid",
            "agent_validated_injected_handoff_without_admission",
        ]) {
            expect(source).not.toContain(marker);
        }
    });
});
