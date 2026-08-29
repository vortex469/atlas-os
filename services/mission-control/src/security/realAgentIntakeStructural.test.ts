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

const v027Markers = [
    /real[-_ ]agent[-_ ]intake/i,
    /agent[-_ ]installation[-_ ]intake[-_ ](?:request|admission|result)/i,
    /admitted_for_evidence_only/i,
    /authenticated_core_intake_evidence_only/i,
    /installation_intake:create/i,
    /api\/v1\/internal\/installation-intake/i,
];

describe("v0.27 real Agent intake presentation boundary", () => {
    it("has no type, API client, hook, component, page, route, or navigation", () => {
        expect(Object.keys(productionSources)).not.toEqual(expect.arrayContaining([
            expect.stringMatching(/real[-_]?agent[-_]?intake|installation[-_]?intake/i),
        ]));
        for (const marker of v027Markers) {
            expect(source).not.toMatch(marker);
            expect(router).not.toMatch(marker);
            expect(navigation).not.toMatch(marker);
        }
    });

    it("has no read, delivery, admission, mutation, or navigation call", () => {
        expect(source).not.toMatch(
            /atlas(?:Agent)?\.(?:get|post|put|patch|delete)[^\n]*(?:installation[-_/ ]intake|real[-_/ ]intake)/i,
        );
        expect(source).not.toMatch(
            /(?:fetch|axios)[^\n]*(?:installation[-_/ ]intake|real[-_/ ]intake)/i,
        );
        expect(source).not.toMatch(
            /(?:href|to|navigate\()[^\n]*(?:installation[-_/ ]intake|real[-_/ ]intake)/i,
        );
    });

    it("has no prohibited action label or authority control", () => {
        for (const label of [
            "install", "run", "execute", "deploy", "dispatch", "deliver",
            "send(?:-|\\s+)to(?:-|\\s+)agent", "start(?:-|\\s+)workflow", "rollback",
        ]) {
            expect(source).not.toMatch(new RegExp(
                `(?:installation[-_ ]intake|real[-_ ]intake)[^\\n]{0,200}(?:>|aria-label=["'])\\s*${label}(?:\\s+now)?(?:\\s*<|["'])`,
                "i",
            ));
        }
    });

    it("has no Home Assistant exception or evidence rendering", () => {
        expect(source).not.toMatch(
            /home assistant[^\n]{0,200}(?:installation[-_ ]intake|real[-_ ]intake)/i,
        );
        for (const marker of [
            "agent_accepted_authenticated_handoff_for_intake_evidence_only",
            "delivery_received",
            "evidence_admission_granted",
            "execution_admission_granted",
        ]) {
            expect(source).not.toContain(marker);
        }
    });
});
