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

const v028Markers = [
    /dormant[-_ ](?:core[-_ ](?:to[-_ ])?)?agent[-_ ](?:intake[-_ ])?delivery/i,
    /core[-_ ]agent[-_ ]intake[-_ ]delivery/i,
    /dormant[-_ ]delivery[-_ ]wiring/i,
    /dormant-agent-intake-delivery-configuration-v1/i,
    /core-agent-intake-delivery-(?:preparation|audit-evidence|response-validation)-v1/i,
    /prepared_dormant/i,
    /core_prepared_agent_intake_delivery_wiring_only/i,
    /production_delivery_observed/i,
];

describe("v0.28 dormant Core-to-Agent delivery wiring presentation boundary", () => {
    it("has no type, API client, hook, component, page, route, or navigation", () => {
        expect(Object.keys(productionSources)).not.toEqual(expect.arrayContaining([
            expect.stringMatching(
                /dormant[-_]?delivery|core[-_]?agent[-_]?(?:intake[-_]?)?delivery/i,
            ),
        ]));

        for (const marker of v028Markers) {
            expect(source).not.toMatch(marker);
            expect(router).not.toMatch(marker);
            expect(navigation).not.toMatch(marker);
        }
    });

    it("has no read, prepare, response-validation, or mutation call", () => {
        expect(source).not.toMatch(
            /atlas(?:Agent)?\.(?:get|post|put|patch|delete)[^\n]*(?:dormant[-_/ ]delivery|agent[-_/ ]intake[-_/ ]delivery)/i,
        );
        expect(source).not.toMatch(
            /(?:fetch|axios)[^\n]*(?:dormant[-_/ ]delivery|agent[-_/ ]intake[-_/ ]delivery)/i,
        );
        expect(source).not.toMatch(
            /(?:href|to|navigate\()[^\n]*(?:dormant[-_/ ]delivery|agent[-_/ ]intake[-_/ ]delivery)/i,
        );
        expect(source).not.toMatch(
            /(?:prepare|validateResponse|getPreparation)\s*\([^\n]*(?:delivery|intake)/i,
        );
    });

    it("renders no endpoint, authentication reference, secret, or evidence", () => {
        for (const marker of [
            /endpoint_fingerprint/i,
            /credential_(?:source|file)/i,
            /ca_bundle_file/i,
            /tls_server_name/i,
            /installation_intake:create/i,
            /mode-0400-file/i,
        ]) {
            expect(source).not.toMatch(marker);
        }
        expect(source).not.toMatch(/authorization:\s*bearer/i);
        expect(source).not.toMatch(/api\/v1\/internal\/installation-intake/i);
    });

    it("has no live delivery, execution, or authority control", () => {
        for (const label of [
            "install", "run", "execute", "deploy", "dispatch", "deliver",
            "send(?:-|\\s+)to(?:-|\\s+)agent", "start(?:-|\\s+)workflow", "rollback",
        ]) {
            expect(source).not.toMatch(new RegExp(
                `(?:dormant[-_ ]delivery|agent[-_ ]intake[-_ ]delivery)[^\\n]{0,200}(?:>|aria-label=["'])\\s*${label}(?:\\s+now)?(?:\\s*<|["'])`,
                "i",
            ));
        }
    });

    it("has no Home Assistant delivery exception or deployment surface", () => {
        expect(source).not.toMatch(
            /home assistant[^\n]{0,200}(?:dormant[-_ ]delivery|agent[-_ ]intake[-_ ]delivery)/i,
        );
        expect(source).not.toMatch(
            /(?:dormant[-_ ]delivery|agent[-_ ]intake[-_ ]delivery)[^\n]{0,200}home assistant/i,
        );
    });
});
