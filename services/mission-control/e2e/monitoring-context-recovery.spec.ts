import { expect, test } from "@playwright/test";
import { installMissionControlMocks, providers } from "./mission-control-fixtures";
import { management, operatorManagement, resource } from "./resource-monitoring-fixture";

for (const width of [320, 390, 1280]) for (const failure of ["http", "shape"] as const) {
    test(`monitoring settings recovery at ${width}px (${failure})`, async ({ page, baseURL }) => {
        const mutations: string[] = [];
        await installMissionControlMocks(page, "available", mutations);
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/providers", route => route.fulfill({ json: providers.map(p => ({ ...p, capabilities: ["resources"] })) }));
        await page.route("**/api/v1/operator-auth/session", route => route.fulfill({ headers: { "x-atlas-csrf-token": "fixture-csrf" }, json: {
            authenticated: true, expires_at: "2999-01-01T00:00:00Z",
            principal: { operator_id: "fixture-operator", authenticated_at: "2026-01-01T00:00:00Z", permissions: ["provider_intent:update"], auth_method: "core_session" },
        } }));
        const inventory = { provider_id: "proxmox", provider_name: "Proxmox", refreshed_at: "2026-10-27T00:00:00Z",
            resources: [{ ...resource, expectation: { value: null, label: "Needs Review", state: "needs_review", allowed_values: [] }, configured: false, needs_review: true, metadata: {} }],
            summary: { total: 1, configured: 0, needs_review: 1, missing: 0, ignored: 0, by_type: { qemu: 1 }, by_state: { running: 1 } }, metadata: {} };
        await page.route("**/api/v1/providers/proxmox/resources", route => route.fulfill({ json: inventory }));
        await page.route("**/api/v1/providers/proxmox/discovery/refresh", route => {
            expect(route.request().method()).toBe("POST");
            expect(route.request().postData()).toBeNull();
            expect(new URL(route.request().url()).origin).toBe(new URL(baseURL!).origin);
            return route.fulfill({ json: inventory });
        });
        const configured = { ...management, resources: [{ ...management.resources[0], intent_status: "configured" as const,
            intent_reason: "matching_active_intent" as const, expectation: "running" as const, record_version: 1 }] };
        let reads = 0;
        let failing = false;
        let finish: (() => void) | undefined;
        await page.route("**/api/v1/providers/proxmox/management", async route => {
            expect(route.request().method()).toBe("GET");
            reads += 1;
            if (failing) {
                await new Promise<void>(resolve => { finish = resolve; });
                return route.fulfill(failure === "http" ? { status: 503, json: { private: "PRIVATE-MONITORING-CANARY" } }
                    : { json: { ...configured, resources: [{ ...configured.resources[0], identity_assurance: "PRIVATE-MONITORING-CANARY" }] } });
            }
            return route.fulfill({ json: configured });
        });
        await page.route("**/api/v1/providers/proxmox/management/operator", route => route.fulfill({ json: operatorManagement(configured) }));
        await page.route("**/api/v1/providers/proxmox/management/operator/monitoring-suggestions", route => route.fulfill({ json: [] }));
        await page.goto("/providers/proxmox");
        const row = page.getByTestId("resource-row-qemu-110");
        const save = row.getByRole("button", { name: "Save", exact: true });
        const refresh = page.getByRole("button", { name: "Refresh resources", exact: true });
        await expect(save).toBeEnabled();
        await expect(row.getByText("Configured — matches observed state", { exact: true })).toBeVisible();
        await row.getByRole("combobox").selectOption("ignored");
        await row.getByRole("checkbox").check();
        await expect(save).toBeEnabled();
        const initialReads = reads;
        failing = true;
        await refresh.click();
        await expect.poll(() => Boolean(finish)).toBe(true);
        await expect(save).toBeDisabled();
        await expect(row.getByRole("combobox")).toBeDisabled();
        await expect(row.getByText("Last reported: Verified", { exact: true })).toBeVisible();
        await expect(row.getByText("Last reported: Expected running", { exact: true })).toBeVisible();
        await expect(row.getByText("Configured — matches observed state", { exact: true })).toHaveCount(0);
        finish!();
        await expect(page.getByText(/Monitoring unavailable —/)).toBeVisible();
        await expect(save).toBeDisabled();
        await expect(row.getByText("Current monitoring settings could not be checked.", { exact: true })).toBeVisible();
        await expect(page.getByText("PRIVATE-MONITORING-CANARY")).toHaveCount(0);
        failing = false;
        await refresh.click();
        await expect(row.getByRole("combobox")).toBeEnabled();
        await expect(row.getByRole("combobox")).toHaveValue("running");
        await expect(row.getByText("Configured — matches observed state", { exact: true })).toBeVisible();
        await row.getByRole("combobox").selectOption("ignored");
        await expect(row.getByRole("checkbox")).not.toBeChecked();
        await expect(save).toBeDisabled();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(reads).toBe(initialReads + 2);
        const allowed = `POST ${new URL(baseURL!).origin}/api/v1/providers/proxmox/discovery/refresh`;
        expect(mutations).toEqual([allowed, allowed]);
    });
}
