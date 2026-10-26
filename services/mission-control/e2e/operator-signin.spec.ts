import { expect, test } from "@playwright/test";
import { discoveryItemsPage } from "./mission-control-fixtures";
import type { DiscoveryProposalNavigation } from "../src/types/discovery";
import { capability, resource } from "./maintenance-selector-fixture";

// Separate from the default GET-only fixture: exactly one simulated login is
// allowed. All other mutations are recorded and rejected; no backend is used.
const proposal: DiscoveryProposalNavigation = {
    proposal_id: `discovery-operator-proposal-${"a".repeat(64)}`,
    destination_kind: "operator_maintenance_selection", catalog_item_id: "fixture-app",
    catalog_source_type: "curated", compatibility_status: "compatible",
    finding_reference_count: 0, evidence_reference_count: 1, status: "current",
    reason: "compatible", intent_hint: "restart-service",
    target_hints: [{ catalog_target_id: "untrusted-hint", provider_hint: "advisory-only" }],
    generated_at: "2026-01-01T00:00:00Z", expires_at: "2999-01-01T00:00:00Z",
    actionable_navigation: true,
};

for (const width of [390, 1280]) {
    test(`Discovery context survives sign-in without selecting or requesting maintenance at ${width}px`, async ({ page }) => {
        let logins = 0;
        let proposalReads = 0;
        const unexpectedMutations: string[] = [];
        await page.setViewportSize({ width, height: 844 });
        await page.route("**/agent-api/**", (route) => {
            if (route.request().method() !== "GET") unexpectedMutations.push(`${route.request().method()} Agent`);
            return route.fulfill({ status: 404, json: { detail: "No Agent calls in sign-in fixture." } });
        });
        await page.route("**/api/v1/**", async (route) => {
            const request = route.request();
            const path = new URL(request.url()).pathname.replace(/^\/api\/v1/, "");
            if (request.method() === "POST" && path === "/operator-auth/login") {
                logins += 1;
                expect(request.postDataJSON()).toEqual({ operator_id: "browser-operator", password: "fixture-only-password" });
                await route.fulfill({ headers: { "x-atlas-csrf-token": "fixture-only-csrf" }, json: {
                    authenticated: true, expires_at: "2999-01-01T00:00:00Z",
                    principal: { operator_id: "browser-operator", authenticated_at: "2026-01-01T00:00:00Z", permissions: ["operational_intent:create"], auth_method: "core_session" },
                } });
                return;
            }
            if (request.method() !== "GET") {
                unexpectedMutations.push(`${request.method()} ${path}`);
                await route.fulfill({ status: 405, json: { detail: "Only the exact mock login is allowed." } });
                return;
            }
            if (path === "/operator-auth/session") return route.fulfill({ status: 401, json: { detail: "Sign in required." } });
            if (path === "/discovery/items/fixture-app") return route.fulfill({ json: discoveryItemsPage.entries[0] });
            if (path === "/discovery/items/fixture-app/relationships") return route.fulfill({ json: { item_id: "fixture-app", incoming: [], outgoing: [] } });
            if (path === "/discovery/proposals") return route.fulfill({ json: { proposals: [proposal], total: 1, limit: 25 } });
            if (path === `/discovery/proposals/${proposal.proposal_id}`) {
                proposalReads += 1;
                return route.fulfill({ json: proposal });
            }
            if (path === "/execution-candidates/operator-intents/capabilities") return route.fulfill({ json: { capabilities: [capability] } });
            if (path === `/execution-candidates/operator-intents/capabilities/${capability.selector_id}/resources`) return route.fulfill({ json: {
                execution_intent: "restart-service", provider_id: "proxmox", resource_type: "qemu",
                generated_at: "2026-01-01T00:00:00Z", resources: [resource],
            } });
            return route.fulfill({ status: 404, json: { detail: "Optional information unavailable in fixture." } });
        });
        await page.goto("/discovery/items/fixture-app");
        await page.getByRole("link", { name: "Continue to maintenance selection for fixture-app" }).click();
        await expect(page.getByRole("heading", { name: "Operator login" })).toBeVisible();
        await expect(page.getByText(/maintenance will reload the proposal/)).toBeVisible();
        await page.getByLabel("Operator ID").fill("browser-operator");
        await page.getByLabel("Password").fill("fixture-only-password");
        await page.getByRole("button", { name: "Sign in", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Request service restart" })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Advisory proposal context" })).toBeVisible();
        await expect(page.getByRole("radio", { name: /Browser fixture VM/ })).not.toBeChecked();
        await expect(page.getByRole("button", { name: "Request restart candidate" })).toBeDisabled();
        expect(logins).toBe(1);
        expect(proposalReads).toBe(1);
        expect(unexpectedMutations).toEqual([]);
        expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}
