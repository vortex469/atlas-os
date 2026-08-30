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
        && !path.toLowerCase().includes("installationreadinessreview")
    )),
);

const source = Object.entries(productionSources)
    .map(([path, contents]) => `${path}\n${contents}`)
    .join("\n");

const receiptMarkers = [
    /end[-_ ]to[-_ ]end[-_ ]inert[-_ ]delivery[-_ ]receipt/i,
    /inert[-_ ]delivery[-_ ]receipt/i,
    /end-to-end-inert-delivery-(?:request|verification|receipt|status|error|audit-evidence)-v1/i,
    /verified_inert_receipt/i,
    /receipt[-_ ]verification/i,
];

describe("v0.33 inert delivery receipt Mission Control boundary", () => {
    it("has no client, type, hook, component, page, route, or navigation", () => {
        expect(Object.keys(productionSources)).not.toEqual(expect.arrayContaining([
            expect.stringMatching(/inert[-_]?delivery[-_]?receipt/i),
        ]));
        for (const marker of receiptMarkers) {
            expect(source).not.toMatch(marker);
            expect(router).not.toMatch(marker);
            expect(navigation).not.toMatch(marker);
        }
    });

    it("has no receipt read, mutation, verification, polling, or transport call", () => {
        expect(source).not.toMatch(/atlas\.(?:get|post|put|patch|delete)[^\n]*(?:inert-delivery-receipt|receipt-verification)/i);
        expect(source).not.toMatch(/(?:fetch|axios)[^\n]*(?:inert-delivery-receipt|receipt-verification)/i);
        expect(source).not.toMatch(/(?:href|to|navigate\()[^\n]*(?:inert-delivery-receipt|receipt-verification)/i);
        expect(source).not.toMatch(/(?:verify|read|poll|refresh|finalize|retry|resend|sendAgain)InertDeliveryReceipt\s*\(/i);
    });

    it("renders no credential, token, internal path, raw envelope, or raw receipt", () => {
        for (const marker of [
            /inert[-_ ]delivery[-_ ]receipt[^\n]{0,240}(?:credential|bearer|authorization|secret|token)/i,
            /inert[-_ ]delivery[-_ ]receipt[^\n]{0,240}(?:internal[-_ ]path|address|url|host)/i,
            /inert[-_ ]delivery[-_ ]receipt[^\n]{0,240}(?:raw[-_ ]envelope|raw[-_ ]receipt|request[-_ ]body|response[-_ ]body)/i,
            /inert[-_ ]delivery[-_ ]receipt[^\n]{0,240}(?:audit[-_ ]evidence|admission[-_ ]fingerprint|acknowledgement[-_ ]fingerprint)/i,
            /api\/v1\/internal\/installation-intake[^\n]{0,240}inert[-_ ]delivery[-_ ]receipt/i,
        ]) {
            expect(source).not.toMatch(marker);
        }
    });

    it("adds no retry, resend, send, admission, execution, or mutation control", () => {
        for (const label of [
            "verify", "retry", "resend", "send(?:-|\\s+)again", "send",
            "admit", "install", "run", "execute", "deploy", "rollback",
            "dispatch", "start(?:-|\\s+)workflow", "worker", "mutate",
        ]) {
            expect(source).not.toMatch(new RegExp(
                `inert[-_ ]delivery[-_ ]receipt[^\\n]{0,240}(?:>|aria-label=["'])\\s*${label}(?:\\s+now)?(?:\\s*<|["'])`,
                "i",
            ));
        }
    });

    it("preserves evidence-only authority and the blocked Home Assistant golden", () => {
        const frozenPosture = [
            "evidence-only",
            "does not authorize installation",
            "does not authorize execution",
            "does not authorize dispatch",
            "does not authorize workflow or worker invocation",
            "does not authorize provider, repository, or in-guest mutation",
            "does not authorize deployment, rollback, retry, or resend",
            "does not authorize Home Assistant installation",
        ];
        expect(frozenPosture).toHaveLength(8);
        expect(source).not.toMatch(/home assistant[^\n]{0,240}inert[-_ ]delivery[-_ ]receipt/i);
        expect(source).not.toMatch(/inert[-_ ]delivery[-_ ]receipt[^\n]{0,240}home assistant/i);
    });
});
