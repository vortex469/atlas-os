import { expect, test } from "@playwright/test";
import { installMissionControlMocks, providers } from "./mission-control-fixtures";
import { management, operatorManagement, resource } from "./resource-monitoring-fixture";

for (const width of [320, 390, 1280]) for (const outcome of ["ready", "failed", "shape", "revoked"] as const) {
    test(`editing permissions recheck at ${width}px (${outcome})`, async ({ page, baseURL }) => {
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
        await page.route("**/api/v1/providers/proxmox/management", route => route.fulfill({ json: management }));
        await page.route("**/api/v1/providers/proxmox/management/operator/monitoring-suggestions", route => route.fulfill({ json: [] }));
        let rechecking = false;
        let finish: (() => void) | undefined;
        await page.route("**/api/v1/providers/proxmox/management/operator", async route => {
            expect(route.request().method()).toBe("GET");
            const state = operatorManagement();
            if (rechecking) {
                await new Promise<void>(resolve => { finish = resolve; });
                if (outcome === "failed") return route.fulfill({ status: 503, json: { private: "PRIVATE-PERMISSIONS-CANARY" } });
                if (outcome === "shape") return route.fulfill({ json: { ...state, resources: [{ ...state.resources[0], caller_can_mutate: { private: "PRIVATE-PERMISSIONS-CANARY" } }] } });
                if (outcome === "revoked") state.resources[0].caller_can_mutate = false;
            }
            return route.fulfill({ json: state });
        });
        await page.goto("/providers/proxmox");
        const row = page.getByTestId("resource-row-qemu-110");
        const save = row.getByRole("button", { name: "Save", exact: true });
        const refresh = page.getByRole("button", { name: "Refresh resources", exact: true });
        await expect(row.getByRole("combobox")).toBeEnabled();
        await row.getByRole("combobox").selectOption("ignored");
        await row.getByRole("checkbox").check();
        await expect(save).toBeEnabled();
        rechecking = true;
        await refresh.click();
        await expect.poll(() => Boolean(finish)).toBe(true);
        // The public read has finished; the permission check alone pauses saving.
        await expect(row.getByText(/Last reported:/)).toHaveCount(0);
        const notice = page.getByText("Checking editing permissions. Your draft is kept; saving is paused.", { exact: true });
        await expect(notice).toBeVisible();
        await expect(save).toBeDisabled();
        await expect(row.getByRole("combobox")).toBeDisabled();
        await expect(row.getByRole("combobox")).toHaveValue("ignored");
        await expect(row.getByRole("checkbox")).toBeChecked();
        finish!();
        await expect(notice).toHaveCount(0);
        if (outcome === "ready") {
            await expect(save).toBeEnabled();
            await expect(row.getByRole("combobox")).toHaveValue("ignored");
            await expect(row.getByRole("checkbox")).toBeChecked();
        } else {
            await expect(save).toHaveCount(0);
            await expect(row.getByText((outcome === "failed" || outcome === "shape") ? "Your editing permissions could not be checked." : "You do not have permission to edit monitoring expectations.", { exact: true })).toBeVisible();
            rechecking = false;
            await refresh.click();
            await expect(row.getByRole("combobox")).toBeEnabled();
            await expect(row.getByRole("combobox")).toHaveValue("");
            await row.getByRole("combobox").selectOption("ignored");
            await expect(row.getByRole("checkbox")).not.toBeChecked();
            await expect(save).toBeDisabled();
        }
        await expect(page.getByText("PRIVATE-PERMISSIONS-CANARY")).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        const allowed = `POST ${new URL(baseURL!).origin}/api/v1/providers/proxmox/discovery/refresh`;
        expect(mutations).toEqual(outcome === "ready" ? [allowed] : [allowed, allowed]);
    });
}
