import { test, expect } from "./mission-control-fixtures";

for (const width of [390, 1440]) {
    test(`malformed policy health at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 1000 });
        await page.route("**/api/v1/policies/status", route => route.fulfill({ json: {
            status: {}, checked_at: "2026-02-30T00:00:00Z", error: { invalid: true },
        } }));
        await page.goto("/");
        const policy = page.getByRole("article", { name: "Policy reload" });
        await expect(policy.getByText("Unknown", { exact: true })).toBeVisible();
        await expect(policy.getByText(/Evidence age unknown/)).toBeVisible();
        await expect(policy.getByText(/Current evidence/)).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    });

    test(`system health evidence at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 1000 });
        await page.route("**/api/v1/health", route => route.fulfill({ json: {
            services: {
                Slow: { status: "degraded", message: "Unexpected HTTP status from the provider." },
                Down: { status: "offline", message: "Connection refused" },
                Gated: { status: "blocked", message: "Policy denies access" },
                Missing: null,
            },
        } }));
        await page.goto("/");
        const summary = page.getByRole("region", { name: "System health", exact: true });
        await expect(summary.getByRole("article", { name: "Atlas Core health aggregate" }).getByText("Unknown", { exact: true })).toBeVisible();
        const core = page.getByRole("region", { name: "Core health", exact: true });
        for (const state of ["Degraded", "Unavailable", "Blocked", "Unknown"]) {
            await expect(core.getByText(state, { exact: true })).toBeVisible();
        }
        await expect(core.getByText("Connection refused", { exact: true })).toBeVisible();
        await expect(summary.getByText(/Last-known status: Healthy/)).toBeVisible();
        await page.route("**/api/v1/health", route => route.fulfill({ status: 503, json: { detail: "Unavailable" } }));
        await page.getByRole("button", { name: "Refresh", exact: true }).click();
        await expect(core.getByText(/Last-known status: Unavailable/)).toBeVisible();
        await expect(core.getByText("Unavailable", { exact: true })).toHaveCount(0);
        await expect(summary.getByRole("article", { name: "ACE assessment" }).getByText("Healthy", { exact: true })).toBeVisible();
        await page.route("**/api/v1/health", route => route.fulfill({ json: { atlas: "healthy", services: {} } }));
        await page.getByRole("button", { name: "Refresh", exact: true }).click();
        await expect(summary.getByRole("article", { name: "Atlas Core health aggregate" }).getByText("Healthy", { exact: true })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    });
}
