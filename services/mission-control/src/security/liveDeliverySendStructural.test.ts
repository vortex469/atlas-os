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
        && !path.toLowerCase().includes("deliveryactivationpreflight")
        && !path.toLowerCase().includes("deliveryenablement")
    )),
);

const source = Object.entries(productionSources)
    .map(([path, contents]) => `${path}\n${contents}`)
    .join("\n");

const liveSendMarkers = [
    /live[-_ ]delivery[-_ ]send/i,
    /installation[-_ ]delivery[-_ ]sends/i,
    /live-delivery-send-(?:attempt|receipt|status|audit-evidence|error)-v1/i,
    /admitted_evidence_only/i,
    /send_attempt_id/i,
    /one_shot_only/i,
    /automatic_retries/i,
];

describe("v0.31 live delivery send Mission Control boundary", () => {
    it("has no client, read model, hook, component, page, route, or navigation", () => {
        expect(Object.keys(productionSources)).not.toEqual(expect.arrayContaining([
            expect.stringMatching(/live[-_]?delivery[-_]?send/i),
        ]));
        for (const marker of liveSendMarkers) {
            expect(source).not.toMatch(marker);
            expect(router).not.toMatch(marker);
            expect(navigation).not.toMatch(marker);
        }
    });

    it("has no create, readback, retry, resend, refresh, or navigation call", () => {
        expect(source).not.toMatch(/atlas\.(?:get|post|put|patch|delete)[^\n]*installation-delivery-sends/i);
        expect(source).not.toMatch(/(?:fetch|axios)[^\n]*installation-delivery-sends/i);
        expect(source).not.toMatch(/(?:href|to|navigate\()[^\n]*installation-delivery-sends/i);
        expect(source).not.toMatch(/(?:retry|resend|sendAgain|refreshLiveSend)\s*\(/i);
    });

    it("renders no secret, endpoint, raw envelope, response, or send evidence", () => {
        for (const marker of [
            /credential_(?:source|file|value)/i,
            /authorization_header/i,
            /ca_bundle_file/i,
            /tls_server_name/i,
            /request_body_fingerprint/i,
            /response_fingerprint/i,
            /acknowledgement_fingerprint/i,
            /api\/v1\/internal\/installation-intake/i,
        ]) {
            expect(source).not.toMatch(marker);
        }
    });

    it("adds no live-send action or prohibited authority control", () => {
        for (const label of [
            "install", "run", "execute", "deploy", "rollback", "dispatch",
            "start(?:-|\\s+)workflow", "retry", "resend", "send(?:-|\\s+)again",
            "worker", "mutate",
        ]) {
            expect(source).not.toMatch(new RegExp(
                `live[-_ ]delivery[-_ ]send[^\\n]{0,200}(?:>|aria-label=["'])\\s*${label}(?:\\s+now)?(?:\\s*<|["'])`,
                "i",
            ));
        }
    });

    it("has no Home Assistant live-send exception or deployment artifact", () => {
        expect(source).not.toMatch(/home assistant[^\n]{0,200}live[-_ ]delivery[-_ ]send/i);
        expect(source).not.toMatch(/live[-_ ]delivery[-_ ]send[^\n]{0,200}home assistant/i);
    });
});
