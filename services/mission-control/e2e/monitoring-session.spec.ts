import { expect, test } from "@playwright/test";
import { installMissionControlMocks, providers } from "./mission-control-fixtures";
import { management, operatorManagement, resource } from "./resource-monitoring-fixture";

const nonce = "12345678-1234-1234-1234-123456789abc";
const inventory = { provider_id: "proxmox", provider_name: "Proxmox", refreshed_at: "2026-01-01T00:00:00Z",
    resources: [{ ...resource, expectation: { value: null, label: "Needs Review", state: "needs_review", allowed_values: [] },
        configured: false, needs_review: true, metadata: {} }],
    summary: { total: 1, configured: 0, needs_review: 1, missing: 0, ignored: 0, by_type: { qemu: 1 }, by_state: { running: 1 } }, metadata: {} };

// Two exact synthetic requests: an observation refresh and a rejected policy save.
for (const width of [320, 390, 1280]) {
    test.describe(`Monitoring session expiry at ${width}px`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("keeps public facts and ignores a ready response from the expired session", async ({ page, baseURL }) => {
            const mutations: string[] = [];
            await installMissionControlMocks(page, "available", mutations);
            await page.addInitScript(nonce => { Object.defineProperty(crypto, "randomUUID", { value: () => nonce }); }, nonce);
            await page.route("**/api/v1/providers", route => route.fulfill({ json: providers.map(provider => ({ ...provider, capabilities: ["resources"] })) }));
            await page.route("**/api/v1/operator-auth/session", route => route.fulfill({ headers: { "x-atlas-csrf-token": "fixture-csrf" }, json: {
                authenticated: true, expires_at: "2999-01-01T00:00:00Z",
                principal: { operator_id: "fixture-operator", authenticated_at: "2026-01-01T00:00:00Z", permissions: ["provider_intent:update"], auth_method: "core_session" },
            } }));
            await page.route("**/api/v1/providers/proxmox/resources", route => route.fulfill({ json: inventory }));
            await page.route("**/api/v1/providers/proxmox/management", route => route.fulfill({ json: management }));
            await page.route("**/api/v1/providers/proxmox/management/operator/monitoring-suggestions", route => route.fulfill({ json: [] }));
            let hold = false;
            let held = 0;
            let release!: () => void;
            const pending = new Promise<void>(resolve => { release = resolve; });
            await page.route("**/api/v1/providers/proxmox/management/operator", async route => {
                if (hold) { held += 1; await pending; }
                return route.fulfill({ json: operatorManagement() });
            });
            const origin = new URL(baseURL!).origin;
            await page.route("**/api/v1/providers/proxmox/discovery/refresh", route => {
                expect(route.request().method()).toBe("POST");
                expect(new URL(route.request().url()).origin).toBe(origin);
                expect(route.request().postData()).toBeNull();
                return route.fulfill({ json: inventory });
            });
            await page.route("**/api/v1/providers/proxmox/management/resources/qemu/110/monitoring-intent", route => {
                expect(route.request().method()).toBe("PUT");
                expect(new URL(route.request().url()).origin).toBe(origin);
                expect(route.request().headers()["x-atlas-csrf-token"]).toBe("fixture-csrf");
                expect(route.request().postDataJSON()).toEqual({ request_id: `provider-intent-mutation-${nonce.replaceAll("-", "")}`,
                    expected_management_fingerprint: management.resources[0].management_fingerprint, expectation: "ignored",
                    expected_record_version: 0, acknowledge_monitoring_suppression: true });
                return route.fulfill({ status: 401, json: { detail: "session_expired" } });
            });
            await page.goto("/providers/proxmox");
            const row = page.getByTestId("resource-row-qemu-110");
            await row.getByRole("combobox").selectOption("ignored");
            await row.getByRole("checkbox").check();
            hold = true;
            await page.getByRole("button", { name: "Refresh resources", exact: true }).click();
            await expect.poll(() => held).toBeGreaterThan(0);
            await row.getByRole("button", { name: "Save", exact: true }).click();
            await expect(row.getByText("Sign in with Provider Intent permission to edit this public monitoring state.", { exact: true })).toBeVisible();
            await expect(row.getByRole("combobox")).toHaveCount(0);
            const response = page.waitForResponse(response => new URL(response.url()).pathname.endsWith("/management/operator") && response.status() === 200);
            release();
            await (await response).finished();
            await page.waitForLoadState("networkidle");
            await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
            await expect(row.getByRole("heading", { name: resource.display_name, exact: true })).toBeVisible();
            await expect(row.getByRole("button", { name: "Save", exact: true })).toHaveCount(0);
            await expect(row.getByRole("checkbox")).toHaveCount(0);
            expect(mutations).toEqual([`POST ${origin}/api/v1/providers/proxmox/discovery/refresh`, `PUT ${origin}/api/v1/providers/proxmox/management/resources/qemu/110/monitoring-intent`]);
        });
    });
}
