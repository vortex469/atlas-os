import { expect, test } from "@playwright/test";
import { installMissionControlMocks } from "./mission-control-fixtures";

// These cases allow one exact, synthetic, confirmed fixture POST. The shared
// read-only suite and its mutation rejection remain unchanged.
const action = { id: "review-fixture", label: "Review fixture", description: "Synthetic action; no provider is contacted.",
    icon: "info", requires_confirmation: true, destructive: false, enabled: true, parameters: {} };

for (const width of [320, 390, 1280]) for (const outcome of ["lost", "unbound"] as const) {
    test.describe(`Unconfirmed provider outcome ${outcome} at ${width}px`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("pauses actions and refreshes status without replaying the request", async ({ page, baseURL }) => {
            const mutations: string[] = [];
            await installMissionControlMocks(page, "available", mutations);
            await page.route("**/api/v1/providers/proxmox/actions", route => route.fulfill({ json: [action] }));
            let posts = 0;
            const origin = new URL(baseURL!).origin;
            await page.route("**/api/v1/providers/proxmox/actions/review-fixture", async (route) => {
                expect(route.request().method()).toBe("POST");
                expect(new URL(route.request().url()).origin).toBe(origin);
                expect(route.request().postDataJSON()).toEqual({ confirmed: true, parameters: {} });
                posts += 1;
                await route.fulfill(outcome === "lost"
                    ? { status: 503, json: { detail: "private response canary" } }
                    : { json: { provider_id: "foreign", action_id: action.id, status: "succeeded", success: true,
                        message: "private response canary", data: {}, warnings: [] } });
            });
            await page.goto("/providers/proxmox");
            const button = page.getByRole("button", { name: "Review fixture", exact: true });
            await expect(button).toBeEnabled();
            page.once("dialog", async (dialog) => {
                expect(dialog.message()).toBe("Review fixture requires confirmation. Continue?");
                await dialog.accept();
            });
            await button.click();
            await expect(page.getByText("Action outcome not confirmed", { exact: true })).toBeVisible();
            await expect(button).toBeDisabled();
            await expect(page.getByText("Action failed", { exact: true })).toHaveCount(0);
            await expect(page.getByText("Action completed", { exact: true })).toHaveCount(0);
            await expect(page.locator("main")).not.toContainText("private response canary");
            await expect(page.getByRole("link", { name: "Review action history", exact: true })).toHaveAttribute("href", "/operations");
            await page.getByRole("button", { name: "Refresh provider status", exact: true }).click();
            await expect(page.getByRole("button", { name: "Refresh provider status", exact: true })).toBeEnabled();
            await expect(button).toBeDisabled();
            await expect(page.getByText("Action outcome not confirmed", { exact: true })).toBeVisible();
            expect(posts).toBe(1);
            expect(mutations).toEqual([`POST ${origin}/api/v1/providers/proxmox/actions/review-fixture`]);
        });
    });
}

test("a declined fixture confirmation sends no action request", async ({ page }) => {
    const mutations: string[] = [];
    await installMissionControlMocks(page, "available", mutations);
    await page.route("**/api/v1/providers/proxmox/actions", route => route.fulfill({ json: [action] }));
    await page.goto("/providers/proxmox");
    page.once("dialog", dialog => dialog.dismiss());
    await page.getByRole("button", { name: "Review fixture", exact: true }).click();
    expect(mutations).toEqual([]);
    await expect(page.getByRole("button", { name: "Review fixture", exact: true })).toBeEnabled();
});

test("a confirmed result remains visible when the provider overview refresh fails", async ({ page, baseURL }) => {
    const mutations: string[] = [];
    await installMissionControlMocks(page, "available", mutations);
    await page.setViewportSize({ width: 390, height: 900 });
    await page.route("**/api/v1/providers/proxmox/actions", route => route.fulfill({ json: [action] }));
    let completed = false;
    let posts = 0;
    await page.route("**/api/v1/ace/summary", async route => {
        if (completed) await route.fulfill({ status: 503, json: { detail: "synthetic overview read failure" } });
        else await route.fallback();
    });
    const origin = new URL(baseURL!).origin;
    await page.route("**/api/v1/providers/proxmox/actions/review-fixture", async route => {
        expect(route.request().method()).toBe("POST");
        expect(new URL(route.request().url()).origin).toBe(origin);
        expect(route.request().postDataJSON()).toEqual({ confirmed: true, parameters: {} });
        posts += 1; completed = true;
        await route.fulfill({ json: { provider_id: "proxmox", action_id: action.id, status: "succeeded", success: true,
            message: "Synthetic action result confirmed.", data: {}, warnings: [] } });
    });
    await page.goto("/providers/proxmox");
    page.once("dialog", dialog => dialog.accept());
    await page.getByRole("button", { name: "Review fixture", exact: true }).click();
    await expect(page.getByText("Action completed", { exact: true })).toBeVisible();
    await expect(page.getByText("Synthetic action result confirmed.", { exact: true })).toBeVisible();
    await expect(page.getByText("Mission Control could not retrieve the latest state from Atlas Core.", { exact: true })).toBeVisible();
    await expect(page.getByText("Action outcome not confirmed", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Action failed", { exact: true })).toHaveCount(0);
    expect(posts).toBe(1);
    expect(mutations).toEqual([`POST ${origin}/api/v1/providers/proxmox/actions/review-fixture`]);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: "/tmp/atlas-provider-confirmed-refresh-failed.png", fullPage: true });
});
