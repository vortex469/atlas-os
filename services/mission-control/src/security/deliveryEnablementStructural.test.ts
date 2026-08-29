import { describe, expect, it } from "vitest";

import api from "../api/deliveryEnablement.ts?raw";
import component from "../features/discovery/DeliveryEnablements.tsx?raw";
import router from "../app/router.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";

const productionModules = import.meta.glob(
    "../**/*.{ts,tsx}",
    { eager: true, import: "default", query: "?raw" },
) as Record<string, string>;

describe("v0.30 operator-controlled delivery enablement presentation boundary", () => {
    it("uses only guarded Core create, list, and item-read", () => {
        expect((api.match(/atlas\.get</g) ?? [])).toHaveLength(2);
        expect((api.match(/atlas\.post</g) ?? [])).toHaveLength(1);
        expect(api).toContain('atlas.get<unknown>("/installation-delivery-enablements"');
        expect(api).toContain("atlas.get<unknown>(`/installation-delivery-enablements/${encodeURIComponent(id)}`");
        expect(api).toContain('atlas.post<unknown>("/installation-delivery-enablements"');
        expect(api).not.toMatch(/atlas\.(?:put|patch|delete)/);
        expect(api).not.toMatch(/from ["'][^"']*(?:agent|credential|provider|repository|workflow|worker|docker|podman|shell|process)/i);
        expect(api).not.toMatch(/(?:fetch|axios|agent|provider|repository|workflow|worker|transport)\.(?:get|post|send|register|execute)/i);
    });

    it("adds no route, navigation, or prohibited authority control", () => {
        expect(router).not.toMatch(/delivery[-_ ]enablement/i);
        expect(navigation).not.toMatch(/delivery[-_ ]enablement/i);
        const labels = [...component.matchAll(/<button[^>]*>([^<]+)/g)].map((match) => match[1]).join(" ");
        expect(labels).not.toMatch(/\bsend\b|\bdeliver\b|\bactivate\b|\brun\b|\binstall\b|\bexecute\b|\bdeploy\b|\bdispatch\b|start workflow|\brollback\b/i);
        expect(component).not.toMatch(/href=|<Link|navigate\(/);
    });

    it("contains no sensitive fields or external integration", () => {
        expect(component).not.toMatch(/raw_provider_payload|credential_(?:file|path)|ca_bundle|tls_server_name|authorization_header|cookie_value|raw_command|internal_path|repository_path|guest_path|endpoint_address/i);
        expect(component).not.toMatch(/agent\.(?:get|post)|transport\.(?:send|register)|worker\.|workflow\.|provider\.|repository\./i);
    });

    it("has no enablement consumer or mutation outside the evidence presenter", () => {
        const allowed = /(?:api|types)\/deliveryEnablement\.ts$|features\/discovery\/(?:DeliveryEnablements|InstallationDispatchHandoffs)\.tsx$/;
        const markers = /DeliveryEnablementOperationV1|operator-controlled-delivery-enablement-record-v1|core_operator_controlled_delivery_enablement_v1/;
        const consumers = Object.entries(productionModules)
            .filter(([path]) => !path.includes(".test.") && !path.includes("/test/") && !path.includes("/security/"))
            .filter(([path, source]) => markers.test(source) && !allowed.test(path));
        expect(consumers).toEqual([]);
        const enablementSources = Object.entries(productionModules)
            .filter(([path]) => path.toLowerCase().includes("deliveryenablement") && !path.includes(".test."))
            .map(([, source]) => source).join("\n");
        expect((enablementSources.match(/atlas\.post</g) ?? [])).toHaveLength(1);
        expect(enablementSources).not.toMatch(/atlas\.(?:put|patch|delete)/);
    });
});
