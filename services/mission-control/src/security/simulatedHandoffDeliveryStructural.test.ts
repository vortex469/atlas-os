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
        && !path.toLowerCase().includes("deliveryactivationpreflight")
        && !path.toLowerCase().includes("deliveryenablement")
    )),
);

const source = Object.entries(productionSources)
    .map(([path, contents]) => `${path}\n${contents}`)
    .join("\n");

const v026Markers = [
    /installation[-_ ]handoff[-_ ]simulated[-_ ]delivery/i,
    /agent[-_ ]installation[-_ ]handoff[-_ ]simulated[-_ ]acknowledgement/i,
    /simulated[-_ ]delivery[-_ ](?:id|fingerprint)/i,
    /acknowledgement[-_ ]fingerprint/i,
    /agent_simulated_not_received/i,
    /simulation_attempt_recorded/i,
    /simulated_acknowledged/i,
];

describe("v0.26 simulated handoff delivery presentation boundary", () => {
    it("has no API client, type, hook, component, page, route, or navigation", () => {
        expect(Object.keys(productionSources)).not.toEqual(expect.arrayContaining([
            expect.stringMatching(/simulated[-_]?handoff|handoff[-_]?simulated/i),
        ]));

        for (const marker of v026Markers) {
            expect(source).not.toMatch(marker);
            expect(router).not.toMatch(marker);
            expect(navigation).not.toMatch(marker);
        }
    });

    it("has no v0.26 read, preservation, delivery, or acknowledgement mutation call", () => {
        expect(source).not.toMatch(
            /atlas(?:Agent)?\.(?:get|post|put|patch|delete)[^\n]*(?:simulated[-_/ ]handoff|handoff[-_/ ]simulated)/i,
        );
        expect(source).not.toMatch(
            /(?:fetch|axios)[^\n]*(?:simulated[-_/ ]handoff|handoff[-_/ ]simulated)/i,
        );
        expect(source).not.toMatch(
            /(?:href|to|navigate\()[^\n]*(?:simulated[-_/ ]handoff|handoff[-_/ ]simulated)/i,
        );
    });

    it("cannot present lifecycle, expiry, linkage, acknowledgement, or authority evidence", () => {
        for (const marker of [
            /pending_acknowledgement/i,
            /expired_unacknowledged/i,
            /expired_acknowledged/i,
            /agent_acknowledged_simulated_handoff_without_live_receipt/i,
            /installation-handoff-simulated-delivery-audit-evidence-v1/i,
            /agent-installation-handoff-simulated-acknowledgement-audit-evidence-v1/i,
        ]) {
            expect(source).not.toMatch(marker);
        }
    });

    it("has no live delivery, execution, Home Assistant exception, or authority control", () => {
        for (const label of [
            "install", "run", "execute", "deploy", "dispatch", "deliver",
            "send(?:-|\\s+)to(?:-|\\s+)agent", "start(?:-|\\s+)workflow", "rollback",
        ]) {
            expect(source).not.toMatch(new RegExp(
                `(?:simulated[-_ ]handoff|handoff[-_ ]simulated)[^\\n]{0,200}(?:>|aria-label=["'])\\s*${label}(?:\\s+now)?(?:\\s*<|["'])`,
                "i",
            ));
        }

        expect(source).not.toMatch(
            /home assistant[^\n]{0,200}(?:simulated[-_ ]handoff|handoff[-_ ]simulated)/i,
        );
    });
});
