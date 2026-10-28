import { test, expect } from "./mission-control-fixtures";

for (const width of [390, 1440]) {
    test(`malformed policy health at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 1000 });
        await page.route("**/api/v1/policies/status", route => route.fulfill({ json: {
            status: {}, checked_at: "2026-02-30T00:00:00Z", error: { invalid: true },
        } }));
        await page.goto("/");
        const policy = page.getByRole("article", { name: "Policy settings check" });
        await expect(policy.getByText("Unknown", { exact: true })).toBeVisible();
        await expect(policy.getByText("Check time unavailable.")).toBeVisible();
        await expect(policy.getByText(/Checked \(UTC\)/)).toHaveCount(0);
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
        await expect(summary.getByRole("article", { name: "Overall service status" }).getByText("Unknown", { exact: true })).toBeVisible();
        const checks = page.getByRole("region", { name: "Service checks", exact: true });
        for (const state of ["Degraded", "Unavailable", "Blocked", "Unknown"]) {
            await expect(checks.getByText(state, { exact: true })).toBeVisible();
        }
        await expect(checks.getByText("Connection refused", { exact: true })).toBeVisible();
        await expect(summary.getByText("Last report: Healthy. Current status unknown.")).toBeVisible();
        await page.route("**/api/v1/health", route => route.fulfill({ status: 503, json: { detail: "Unavailable" } }));
        await page.getByRole("button", { name: "Refresh", exact: true }).click();
        await expect(checks.getByText("Last report: Unavailable. Current status unknown.")).toBeVisible();
        await expect(checks.getByText("Unavailable", { exact: true })).toHaveCount(0);
        await expect(summary.getByRole("article", { name: "System findings" }).getByText("Healthy", { exact: true })).toBeVisible();
        await page.route("**/api/v1/health", route => route.fulfill({ json: { atlas: "healthy", services: {} } }));
        await page.getByRole("button", { name: "Refresh", exact: true }).click();
        await expect(summary.getByRole("article", { name: "Overall service status" }).getByText("Healthy", { exact: true })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    });
}
