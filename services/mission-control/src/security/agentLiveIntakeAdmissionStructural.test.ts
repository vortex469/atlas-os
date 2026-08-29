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

const intakeMarkers = [
    /agent[-_ ]live[-_ ]intake(?:[-_ ]admission)?/i,
    /agent-live-intake-(?:envelope|admission|acknowledgement|result|record|audit-evidence|error)-v1/i,
    /authenticated_core_live_intake_evidence_only/i,
    /agent_admitted_authenticated_live_delivery_evidence_only/i,
    /api\/v1\/internal\/installation-intake/i,
];

describe("v0.32 Agent live intake admission Mission Control boundary", () => {
    it("has no API client, hook, component, page, route, or navigation", () => {
        expect(Object.keys(productionSources)).not.toEqual(expect.arrayContaining([
            expect.stringMatching(/agent[-_]?live[-_]?intake/i),
        ]));
        for (const marker of intakeMarkers) {
            expect(source).not.toMatch(marker);
            expect(router).not.toMatch(marker);
            expect(navigation).not.toMatch(marker);
        }
    });

    it("has no read, mutation, admission, retry, resend, or send-again call", () => {
        expect(source).not.toMatch(/atlas\.(?:get|post|put|patch|delete)[^\n]*installation-intake/i);
        expect(source).not.toMatch(/(?:fetch|axios)[^\n]*installation-intake/i);
        expect(source).not.toMatch(/(?:href|to|navigate\()[^\n]*installation-intake/i);
        expect(source).not.toMatch(/(?:admitLiveIntake|retryLiveIntake|resendLiveIntake|sendLiveIntakeAgain)\s*\(/i);
    });

    it("renders no credentials, raw envelope, internal identity, or sensitive evidence", () => {
        for (const marker of [
            /agent[-_ ]live[-_ ]intake[^\n]{0,200}(?:credential|bearer|authorization|secret|token)/i,
            /agent[-_ ]live[-_ ]intake[^\n]{0,200}(?:raw[-_ ]envelope|request[-_ ]body|internal[-_ ]path|address)/i,
            /agent[-_ ]live[-_ ]intake[^\n]{0,200}(?:admission[-_ ]fingerprint|acknowledgement[-_ ]fingerprint|audit[-_ ]evidence)/i,
        ]) {
            expect(source).not.toMatch(marker);
        }
    });

    it("adds no effect, admission, retry, or resend control", () => {
        for (const label of [
            "admit", "install", "run", "execute", "deploy", "rollback",
            "dispatch", "start(?:-|\\s+)workflow", "worker", "retry",
            "resend", "send(?:-|\\s+)again", "mutate",
        ]) {
            expect(source).not.toMatch(new RegExp(
                `agent[-_ ]live[-_ ]intake[^\\n]{0,200}(?:>|aria-label=["'])\\s*${label}(?:\\s+now)?(?:\\s*<|["'])`,
                "i",
            ));
        }
    });

    it("keeps evidence admission non-authorizing and Home Assistant blocked", () => {
        const frozenPosture = [
            "evidence-only",
            "does not authorize installation",
            "does not authorize execution",
            "does not authorize dispatch",
            "does not authorize workflow or worker invocation",
            "does not authorize provider, repository, or in-guest mutation",
            "does not authorize deployment, rollback, or retry",
            "does not authorize Home Assistant installation",
        ];
        expect(frozenPosture).toHaveLength(8);
        expect(source).not.toMatch(/home assistant[^\n]{0,200}agent[-_ ]live[-_ ]intake/i);
        expect(source).not.toMatch(/agent[-_ ]live[-_ ]intake[^\n]{0,200}home assistant/i);
    });
});
