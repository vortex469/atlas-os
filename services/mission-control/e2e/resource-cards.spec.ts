import { expect, test, providers } from "./mission-control-fixtures";
import { resource, management } from "./resource-monitoring-fixture";

for (const width of [320, 390, 1280]) for (const authenticated of [false, true]) {
    test.describe(`Resource cards at ${width}px (${authenticated ? "editable" : "read-only"})`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("keeps resource facts and read-only guidance inside the viewport", async ({ page }) => {
            await page.route("**/api/v1/providers", route => route.fulfill({ json: providers.map(p => ({ ...p, capabilities: ["resources"] })) }));
            await page.route("**/api/v1/providers/proxmox/resources", route => route.fulfill({ json: {
                provider_id: "proxmox", provider_name: "Proxmox", refreshed_at: new Date().toISOString(),
                resources: [{ ...resource, expectation: { value: null, label: "Needs Review", state: "needs_review", allowed_values: [] },
                    configured: false, needs_review: true, metadata: { vmid: 110, node: "long-node-name-without-any-spaces-for-layout-coverage" } }],
                summary: { total: 1, configured: 0, needs_review: 1, missing: 0, ignored: 0, by_type: { qemu: 1 }, by_state: { running: 1 } }, metadata: {},
            } }));
            await page.route("**/api/v1/providers/proxmox/management", route => route.fulfill({ json: management }));
            if (authenticated) {
                await page.route("**/api/v1/operator-auth/session", route => route.fulfill({ headers: { "x-atlas-csrf-token": "fixture-csrf" }, json: {
                    authenticated: true, expires_at: "2999-01-01T00:00:00Z",
                    principal: { operator_id: "fixture-operator", authenticated_at: new Date().toISOString(), permissions: ["provider_intent:update"], auth_method: "core_session" },
                } }));
                await page.route("**/api/v1/providers/proxmox/management/operator", route => route.fulfill({ json: {
                    ...management, schema_version: "provider-management-v3", caller_has_provider_intent_update: true,
                    resources: management.resources.map(resource => ({ ...resource, resource_live: true,
                        provider_intent_mutation_supported: true, mutation_readiness: "ready", editable_in_principle: true, caller_can_mutate: true })),
                } }));
                await page.route("**/api/v1/providers/proxmox/management/operator/monitoring-suggestions", route => route.fulfill({ json: [] }));
            }
            await page.goto("/providers/proxmox");
            const card = page.getByTestId("resource-row-qemu-110");
            await expect(card.getByRole("heading", { name: resource.display_name })).toBeVisible();
            if (authenticated) {
                await card.getByRole("combobox").selectOption("ignored");
                await expect(card.getByRole("checkbox")).toBeVisible();
                await expect(card.getByRole("button", { name: "Save", exact: true })).toBeDisabled();
            } else {
                await expect(card).toContainText("Sign in with Provider Intent permission");
                await expect(card.getByRole("button", { name: "Save", exact: true })).toHaveCount(0);
            }
            const bounds = await card.evaluate(element => {
                const parent = element.getBoundingClientRect();
                return { viewport: document.documentElement.clientWidth, right: Math.max(parent.right,
                    ...Array.from(element.querySelectorAll("*")).map(child => child.getBoundingClientRect().right)),
                    scroll: element.scrollWidth, width: element.clientWidth };
            });
            expect(bounds.right).toBeLessThanOrEqual(bounds.viewport);
            expect(bounds.scroll).toBeLessThanOrEqual(bounds.width);
        });
    });
}
