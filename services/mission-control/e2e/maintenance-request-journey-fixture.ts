import { isDeepStrictEqual } from "node:util";
import type { Page } from "@playwright/test";
import { installMaintenanceJourney, maintenanceCandidate } from "./repository-journey-fixture";
import { capability, resource } from "./maintenance-selector-fixture";

// Extend the exact simulated workflow with login and candidate creation only.
// Unknown writes still fall through to the original fixture's rejection path.
export async function installMaintenanceRequestJourney(page: Page, baseURL?: string) {
    const origin = new URL(baseURL ?? "http://127.0.0.1:5173").origin;
    await page.clock.setFixedTime(new Date("2026-10-26T00:00:00.000Z"));
    const workflow = await installMaintenanceJourney(page, baseURL);
    const writes: string[] = [];
    const expectedWrites = ["/operator-auth/login", "/execution-candidates/operator-intents"];
    const unexpected: string[] = [];
    const session = { authenticated: true, expires_at: "2999-01-01T00:00:00Z", principal: {
        operator_id: "browser-operator", authenticated_at: "2026-10-26T00:00:00Z",
        permissions: ["operational_intent:create"], auth_method: "core_session",
    } };
    await page.route("**/api/v1/**", async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin !== origin) return route.fallback();
        const path = url.pathname.slice("/api/v1".length);
        if (request.method() === "POST" && expectedWrites.includes(path)) {
            const expectedBody = path === "/operator-auth/login"
                ? { operator_id: "browser-operator", password: "fixture-only-password" }
                : { execution_intent: "restart-service", provider_id: "proxmox", resource_id: "110", resource_type: "qemu",
                    expected_target_fingerprint: resource.operational_target_fingerprint, expires_at: maintenanceCandidate.expires_at };
            if (expectedWrites[writes.length] !== path || !isDeepStrictEqual(request.postDataJSON(), expectedBody)
                || (path !== "/operator-auth/login" && request.headers()["x-atlas-csrf-token"] !== "fixture-only-csrf")) {
                unexpected.push(`${request.method()} ${path}`);
                return route.fulfill({ status: 409, json: { detail: "Not the exact simulated maintenance request." } });
            }
            writes.push(path);
            return route.fulfill(path === "/operator-auth/login"
                ? { headers: { "x-atlas-csrf-token": "fixture-only-csrf" }, json: session }
                : { json: { outcome: "created", candidate_id: maintenanceCandidate.id, candidate: maintenanceCandidate } });
        }
        if (request.method() !== "GET") return route.fallback();
        if (path === "/operator-auth/session") return route.fulfill(writes.length > 0
            ? { headers: { "x-atlas-csrf-token": "fixture-only-csrf" }, json: session }
            : { status: 401, json: { detail: "Sign in required." } });
        if (path === "/execution-candidates/operator-intents/capabilities") return route.fulfill({ json: { capabilities: [capability] } });
        if (path === `/execution-candidates/operator-intents/capabilities/${capability.selector_id}/resources`) return route.fulfill({ json: {
            execution_intent: "restart-service", provider_id: "proxmox", resource_type: "qemu",
            generated_at: "2026-10-26T00:00:00Z", resources: [resource],
        } });
        return route.fallback();
    });
    return Object.assign(workflow, { entryWrites: writes, expectedEntryWrites: expectedWrites, entryUnexpected: unexpected });
}
