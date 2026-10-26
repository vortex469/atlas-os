import type { ProviderManagementV2 } from "../src/types/providerManagement";
import { expect, test } from "@playwright/test";
import { installMissionControlMocks, providers } from "./mission-control-fixtures";
import { management, operatorManagement, resource } from "./resource-monitoring-fixture";

const updated: ProviderManagementV2 = { ...management, resources: [{ ...management.resources[0], intent_status: "configured", intent_reason: "matching_active_intent", expectation: "stopped", record_version: 2 }] };
const nonce = "12345678-1234-1234-1234-123456789abc";

// One exact synthetic policy PUT; recovery must use GET only, never replay it.
for (const width of [320, 390, 1280]) {
    for (const outcome of ["lost", "post-commit-audit"] as const) {
        test.describe(`Uncertain monitoring save ${outcome} at ${width}px`, () => {
            test.use({ viewport: { width, height: 900 } });
            test("checks current state after a failed read without replaying the save", async ({ page, baseURL }) => {
                const mutations: string[] = [];
                await installMissionControlMocks(page, "available", mutations);
                await page.addInitScript(nonce => { Object.defineProperty(crypto, "randomUUID", { value: () => nonce }); }, nonce);
                await page.route("**/api/v1/providers", route => route.fulfill({ json: providers.map(provider => ({ ...provider, capabilities: ["resources"] })) }));
                await page.route("**/api/v1/operator-auth/session", route => route.fulfill({ headers: { "x-atlas-csrf-token": "fixture-csrf" }, json: {
                    authenticated: true, expires_at: "2999-01-01T00:00:00Z",
                    principal: { operator_id: "fixture-operator", authenticated_at: "2026-01-01T00:00:00Z", permissions: ["provider_intent:update"], auth_method: "core_session" },
                } }));
                await page.route("**/api/v1/providers/proxmox/resources", route => route.fulfill({ json: {
                    provider_id: "proxmox", provider_name: "Proxmox", refreshed_at: "2026-01-01T00:00:00Z",
                    resources: [{ ...resource, expectation: { value: null, label: "Needs Review", state: "needs_review", allowed_values: [] }, configured: false, needs_review: true, metadata: {} }],
                    summary: { total: 1, configured: 0, needs_review: 1, missing: 0, ignored: 0, by_type: { qemu: 1 }, by_state: { running: 1 } }, metadata: {},
                } }));
                let checkReads = 0;
                let writes = 0;
                await page.route("**/api/v1/providers/proxmox/management", route => {
                    expect(route.request().method()).toBe("GET");
                    if (writes === 0) return route.fulfill({ json: management });
                    checkReads += 1;
                    if (checkReads === 1) return route.fulfill({ status: 503, json: { detail: "read_unavailable" } });
                    return route.fulfill({ json: updated });
                });
                await page.route("**/api/v1/providers/proxmox/management/operator", route => route.fulfill({ json: operatorManagement(writes > 0 ? updated : management) }));
                await page.route("**/api/v1/providers/proxmox/management/operator/monitoring-suggestions", route => route.fulfill({ json: [] }));
                const origin = new URL(baseURL!).origin;
                await page.route("**/api/v1/providers/proxmox/management/resources/qemu/110/monitoring-intent", route => {
                    expect(route.request().method()).toBe("PUT");
                    expect(new URL(route.request().url()).origin).toBe(origin);
                    expect(route.request().headers()["x-atlas-csrf-token"]).toBe("fixture-csrf");
                    expect(route.request().postDataJSON()).toEqual({ request_id: `provider-intent-mutation-${nonce.replaceAll("-", "")}`,
                        expected_management_fingerprint: management.resources[0].management_fingerprint, expectation: "running",
                        expected_record_version: 0, acknowledge_monitoring_suppression: false });
                    writes += 1;
                    return outcome === "lost" ? route.abort("failed") : route.fulfill({ status: 503, json: { detail: "security_audit_unavailable" } });
                });
                await page.goto("/providers/proxmox");
                const row = page.getByTestId("resource-row-qemu-110");
                await row.getByRole("combobox").selectOption("running");
                await row.getByRole("button", { name: "Save", exact: true }).click();
                const warning = page.getByText("Save outcome not confirmed. Check monitoring state before saving again.", { exact: true });
                await expect(warning).toBeVisible();
                await expect(row.getByText("Unsaved change. Save to apply it.", { exact: true })).toHaveCount(0);
                await expect(row.getByRole("combobox")).toBeDisabled();
                await expect(row.getByRole("button", { name: "Save", exact: true })).toBeDisabled();
                await expect(page.getByRole("button", { name: "Refresh resources", exact: true })).toBeDisabled();
                await page.getByRole("button", { name: "Check monitoring state", exact: true }).click();
                await expect(page.getByText(/Monitoring unavailable —/)).toBeVisible();
                await expect(warning).toBeVisible();
                await expect(row.getByRole("button", { name: "Save", exact: true })).toBeDisabled();
                await page.getByRole("button", { name: "Check monitoring state", exact: true }).click();
                await expect(page.getByText("Current monitoring state reloaded. Review it before saving again.", { exact: true })).toBeVisible();
                await expect(row.getByRole("combobox")).toHaveValue("stopped");
                await expect(row.getByRole("combobox")).toBeEnabled();
                await expect(warning).toHaveCount(0);
                await expect(page.getByText(/saved and confirmed/i)).toHaveCount(0);
                expect(writes).toBe(1);
                expect(checkReads).toBe(2);
                expect(mutations).toEqual([`PUT ${origin}/api/v1/providers/proxmox/management/resources/qemu/110/monitoring-intent`]);
            });
        });
    }
}
