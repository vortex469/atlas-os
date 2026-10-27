import { expect, test } from "@playwright/test";
import { installMissionControlMocks, providers } from "./mission-control-fixtures";
import { management, resource } from "./resource-monitoring-fixture";

for (const width of [320, 390, 1280]) for (const initialFailure of [false, true]) for (const expectation of ["running", "stopped"] as const) {
    test(`observed inventory recovery at ${width}px (initial: ${initialFailure}, expected: ${expectation})`, async ({ page, baseURL }) => {
        const mutations: string[] = [];
        await installMissionControlMocks(page, "available", mutations);
        await page.setViewportSize({ width, height: 900 });
        const inventory = (current_state: string) => ({ provider_id: "proxmox", provider_name: "Proxmox", refreshed_at: "2026-10-27T00:00:00Z",
            resources: [{ ...resource, current_state, expectation: { value: null, label: "Needs Review", state: "needs_review", allowed_values: [] },
                configured: false, needs_review: true, metadata: {} }],
            summary: { total: 1, configured: 0, needs_review: 1, missing: 0, ignored: 0, by_type: { qemu: 1 }, by_state: { [current_state]: 1 } }, metadata: {} });
        await page.route("**/api/v1/providers", route => route.fulfill({ json: providers.map(p => ({ ...p, capabilities: ["resources"] })) }));
        await page.route("**/api/v1/providers/proxmox/resources", route => route.fulfill(initialFailure
            ? { status: 503, json: { detail: "unavailable" } } : { json: inventory("running") }));
        await page.route("**/api/v1/providers/proxmox/management", route => route.fulfill({ json: { ...management, resources: [{ ...management.resources[0],
            intent_status: "configured", intent_reason: "matching_active_intent", expectation, record_version: 1,
        }] } }));
        let refreshes = 0;
        let finish: (() => void) | undefined;
        let pending = true;
        await page.route("**/api/v1/providers/proxmox/discovery/refresh", async route => {
            expect(route.request().method()).toBe("POST");
            expect(new URL(route.request().url()).origin).toBe(new URL(baseURL!).origin);
            expect(route.request().postData()).toBeNull();
            refreshes += 1;
            if (pending) await new Promise<void>(resolve => { finish = resolve; });
            return route.fulfill(refreshes === 1 ? { status: 503, json: { private: "PRIVATE-INVENTORY-CANARY" } } : { json: inventory("stopped") });
        });
        await page.goto("/providers/proxmox");
        const row = page.getByTestId("resource-row-qemu-110");
        const section = page.locator("section").filter({ has: page.getByRole("heading", { name: "Resources and monitoring", exact: true }) }).first();
        const refresh = page.getByRole("button", { name: "Refresh resources", exact: true });
        await expect(row.getByText(`Expected ${expectation}`, { exact: true })).toBeVisible();
        const unavailable = row.getByText("Configured — observed state unavailable", { exact: true });
        if (initialFailure) {
            await expect(unavailable).toBeVisible();
            await expect(row.getByText("Unavailable", { exact: true })).toBeVisible();
        } else await expect(row.getByText(expectation === "running" ? "Configured — matches observed state" : "Configured — does not match observed state", { exact: true })).toBeVisible();
        await refresh.click();
        await expect.poll(() => Boolean(finish)).toBe(true);
        await expect(unavailable).toBeVisible();
        if (!initialFailure) await expect(row.getByText("Last reported: Running", { exact: true })).toBeVisible();
        await expect(row.getByText("Configured — matches observed state", { exact: true })).toHaveCount(0);
        await expect(row.getByText("Configured — does not match observed state", { exact: true })).toHaveCount(0);
        finish!();
        await expect(section.getByRole("alert").filter({ hasText: "could not load observed resources" })).toBeVisible();
        await expect(unavailable).toBeVisible();
        await expect(page.getByText("PRIVATE-INVENTORY-CANARY")).toHaveCount(0);
        pending = false;
        await refresh.click();
        await expect(row.getByText("Stopped", { exact: true })).toBeVisible();
        await expect(row.getByText(expectation === "stopped" ? "Configured — matches observed state" : "Configured — does not match observed state", { exact: true })).toBeVisible();
        await expect(unavailable).toHaveCount(0);
        await expect(row.getByText(/Last reported:/)).toHaveCount(0);
        await expect(row.getByRole("button", { name: "Save", exact: true })).toHaveCount(0);
        expect(refreshes).toBe(2);
        const expectedRefresh = `POST ${new URL(baseURL!).origin}/api/v1/providers/proxmox/discovery/refresh`;
        expect(mutations).toEqual([expectedRefresh, expectedRefresh]);
    });
}
