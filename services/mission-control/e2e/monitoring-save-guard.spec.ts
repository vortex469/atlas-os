import type { ProviderManagementV2 } from "../src/types/providerManagement";
import { expect, test } from "@playwright/test";
import { installMissionControlMocks, providers } from "./mission-control-fixtures";
import { management, operatorManagement, resource } from "./resource-monitoring-fixture";

const fingerprint = management.resources[0].management_fingerprint;
const second = { ...management.resources[0], resource_id: "111", display_name: "Backup", management_fingerprint: `provider-management-fingerprint-v1:${"b".repeat(64)}` };
const initial: ProviderManagementV2 = { ...management, resources: [management.resources[0], second] };
const updated: ProviderManagementV2 = { ...initial, resources: [{ ...initial.resources[0], intent_status: "configured", intent_reason: "matching_active_intent", expectation: "running", record_version: 1 }, second] };
const nonce = "12345678-1234-1234-1234-123456789abc";
const requestId = `provider-intent-mutation-${nonce.replaceAll("-", "")}`;

// Exactly one synthetic monitoring-policy PUT is allowed. No provider is run.
for (const width of [320, 390, 1280]) {
    test.describe(`Monitoring save guard at ${width}px`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("keeps other rows blocked until the save and its reads finish", async ({ page, baseURL }) => {
            const mutations: string[] = [];
            await installMissionControlMocks(page, "available", mutations);
            await page.addInitScript(nonce => { Object.defineProperty(crypto, "randomUUID", { value: () => nonce }); }, nonce);
            await page.route("**/api/v1/providers", route => route.fulfill({ json: providers.map(provider => ({ ...provider, capabilities: ["resources"] })) }));
            await page.route("**/api/v1/operator-auth/session", route => route.fulfill({ headers: { "x-atlas-csrf-token": "fixture-csrf" }, json: {
                authenticated: true, expires_at: "2999-01-01T00:00:00Z",
                principal: { operator_id: "fixture-operator", authenticated_at: new Date().toISOString(), permissions: ["provider_intent:update"], auth_method: "core_session" },
            } }));
            await page.route("**/api/v1/providers/proxmox/resources", route => route.fulfill({ json: {
                provider_id: "proxmox", provider_name: "Proxmox", refreshed_at: new Date().toISOString(),
                resources: [resource, { ...resource, resource_id: "111", display_name: "Backup" }].map(value => ({ ...value,
                    expectation: { value: null, label: "Needs Review", state: "needs_review", allowed_values: [] }, configured: false, needs_review: true, metadata: {} })),
                summary: { total: 2, configured: 0, needs_review: 2, missing: 0, ignored: 0, by_type: { qemu: 2 }, by_state: { running: 2 } }, metadata: {},
            } }));
            let saved = false;
            let writes = 0;
            let followupReads = 0;
            let release!: () => void;
            const pending = new Promise<void>(resolve => { release = resolve; });
            await page.route("**/api/v1/providers/proxmox/management", async route => {
                if (saved) { followupReads += 1; await pending; }
                return route.fulfill({ json: saved ? updated : initial });
            });
            await page.route("**/api/v1/providers/proxmox/management/operator", route => route.fulfill({ json: operatorManagement(saved ? updated : initial) }));
            await page.route("**/api/v1/providers/proxmox/management/operator/monitoring-suggestions", route => route.fulfill({ json: [] }));
            const origin = new URL(baseURL!).origin;
            await page.route("**/api/v1/providers/proxmox/management/resources/qemu/110/monitoring-intent", route => {
                expect(route.request().method()).toBe("PUT");
                expect(new URL(route.request().url()).origin).toBe(origin);
                expect(route.request().headers()["x-atlas-csrf-token"]).toBe("fixture-csrf");
                expect(route.request().postDataJSON()).toEqual({ request_id: requestId, expected_management_fingerprint: fingerprint,
                    expectation: "running", expected_record_version: 0, acknowledge_monitoring_suppression: false });
                writes += 1; saved = true;
                return route.fulfill({ json: { outcome: "created", request_id: requestId, provider_id: "proxmox", resource_type: "qemu",
                    resource_id: "110", management_fingerprint: fingerprint, expectation: "running", record_version: 1, superseded_previous_incarnation: false } });
            });
            await page.goto("/providers/proxmox");
            const first = page.getByTestId("resource-row-qemu-110");
            const other = page.getByTestId("resource-row-qemu-111");
            await first.getByRole("combobox").selectOption("running");
            await other.getByRole("combobox").selectOption("running");
            await page.evaluate(() => {
                const first = document.querySelector('[data-testid="resource-row-qemu-110"] button') as HTMLButtonElement;
                const other = document.querySelector('[data-testid="resource-row-qemu-111"] button') as HTMLButtonElement;
                first.click(); other.click(); first.click();
            });
            await expect.poll(() => followupReads).toBeGreaterThan(0);
            await expect(other.getByRole("button", { name: "Save", exact: true })).toBeDisabled();
            await expect(page.getByRole("button", { name: "Refreshing...", exact: true })).toBeDisabled();
            await expect(page.getByText("Monitoring update in progress. Other saves are temporarily paused.", { exact: true })).toBeVisible();
            expect(writes).toBe(1);
            release();
            await expect(other.getByRole("button", { name: "Save", exact: true })).toBeEnabled();
            await expect(first.getByText("Monitoring expectation saved and confirmed by Atlas Core.", { exact: true })).toBeVisible();
            await first.getByRole("combobox").selectOption("stopped");
            await expect(first.getByText("Monitoring expectation saved and confirmed by Atlas Core.", { exact: true })).toHaveCount(0);
            await expect(first.getByText("Unsaved change. Save to apply it.", { exact: true })).toBeVisible();
            await first.getByRole("combobox").selectOption("running");
            await expect(first.getByText("Unsaved change. Save to apply it.", { exact: true })).toHaveCount(0);
            expect(writes).toBe(1);
            expect(mutations).toEqual([`PUT ${origin}/api/v1/providers/proxmox/management/resources/qemu/110/monitoring-intent`]);
        });
    });
}
