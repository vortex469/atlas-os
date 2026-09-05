import { describe, expect, it } from "vitest";

import router from "../app/router.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";

const sourceModules = import.meta.glob(
    "../**/*.{ts,tsx}",
    { eager: true, import: "default", query: "?raw" },
) as Record<string, string>;

const approvedLaterQueueObservationSurface = new Set([
    "../api/queueObservation.ts",
    "../features/installation/QueueObservationEvidence.tsx",
    "../types/queueObservation.ts",
]);

const isProductionSource = (path: string) => (
    !path.includes(".test.")
    && !path.includes("/test/")
    && !path.includes("/security/")
    && !path.toLowerCase().includes("installationreadinessreview")
    && !path.toLowerCase().includes("deliveryactivationpreflight")
    && !path.toLowerCase().includes("deliveryenablement")
    && !path.toLowerCase().includes("runnerbindingplan")
    && !approvedLaterQueueObservationSurface.has(path)
);

const combinedSource = (sources: Record<string, string>) => Object.entries(sources)
    .map(([path, contents]) => `${path}\n${contents}`)
    .join("\n");

const productionSources = Object.fromEntries(
    Object.entries(sourceModules).filter(([path]) => isProductionSource(path)),
);

const source = combinedSource(productionSources);

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

function expectNoDormantDeliveryTransport(sourceText: string) {
    expect(sourceText).not.toMatch(
        /atlas(?:Agent)?\.(?:get|post|put|patch|delete)[^\n]*(?:dormant[-_/ ]delivery|agent[-_/ ]intake[-_/ ]delivery)/i,
    );
    expect(sourceText).not.toMatch(
        /(?:fetch|axios)[^\n]*(?:dormant[-_/ ]delivery|agent[-_/ ]intake[-_/ ]delivery)/i,
    );
    expect(sourceText).not.toMatch(
        /(?:href|to|navigate\()[^\n]*(?:dormant[-_/ ]delivery|agent[-_/ ]intake[-_/ ]delivery)/i,
    );
    expect(sourceText).not.toMatch(
        /(?:prepare|validateResponse|getPreparation)\s*\([^\n]*(?:delivery|intake)/i,
    );
}

function expectNoEndpointAuthenticationSecretEvidence(sourceText: string) {
    for (const marker of [
        /endpoint_fingerprint/i,
        /credential_(?:source|file)/i,
        /ca_bundle_file/i,
        /tls_server_name/i,
        /installation_intake:create/i,
        /mode-0400-file/i,
    ]) {
        expect(sourceText).not.toMatch(marker);
    }
    expect(sourceText).not.toMatch(/authorization:\s*bearer/i);
    expect(sourceText).not.toMatch(/api\/v1\/internal\/installation-intake/i);
}

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
        expectNoDormantDeliveryTransport(source);
    });

    it("renders no endpoint, authentication reference, secret, or evidence", () => {
        expectNoEndpointAuthenticationSecretEvidence(source);
    });

    it("still catches dormant delivery endpoint and authentication leaks while ignoring approved queue observation fields", () => {
        const scopedEndpointSource = combinedSource(Object.fromEntries(
            Object.entries({
                "../api/queueObservation.ts": "const NETWORK = ['allowed_endpoint_fingerprints']; const path = '/installation/candidate-records/id/queue-observations';",
                "../features/installation/DormantDeliveryLeak.ts": "atlas.get('/dormant-delivery'); const endpoint_fingerprint = 'leaked';",
            }).filter(([path]) => isProductionSource(path)),
        ));
        const scopedAuthenticationSource = combinedSource(Object.fromEntries(
            Object.entries({
                "../api/queueObservation.ts": "const NETWORK = ['allowed_endpoint_fingerprints'];",
                "../features/installation/DormantDeliveryLeak.ts": "const leaked = 'authorization: bearer leaked';",
            }).filter(([path]) => isProductionSource(path)),
        ));

        expect(scopedEndpointSource).not.toMatch(/allowed_endpoint_fingerprints/);
        expect(scopedAuthenticationSource).not.toMatch(/allowed_endpoint_fingerprints/);
        expect(() => expectNoDormantDeliveryTransport(scopedEndpointSource)).toThrow();
        expect(() => expectNoEndpointAuthenticationSecretEvidence(scopedEndpointSource)).toThrow();
        expect(() => expectNoEndpointAuthenticationSecretEvidence(scopedAuthenticationSource)).toThrow();
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
