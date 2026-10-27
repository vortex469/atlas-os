import { test, expect } from "./mission-control-fixtures";

for (const width of [390, 1440]) {
    test(`malformed policy health at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 1000 });
        await page.route("**/api/v1/policies/status", route => route.fulfill({ json: {
            status: {}, checked_at: "2026-02-30T00:00:00Z", error: { invalid: true },
        } }));
        await page.goto("/");
        const policy = page.getByRole("article", { name: "Policy status" });
        await expect(policy.getByText("Unknown", { exact: true })).toBeVisible();
        await expect(policy.getByText(/Update time unknown/)).toBeVisible();
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
        await expect(summary.getByRole("article", { name: "Atlas health" }).getByText("Unknown", { exact: true })).toBeVisible();
        const core = page.getByRole("region", { name: "Service health", exact: true });
        for (const state of ["Degraded", "Unavailable", "Blocked", "Unknown"]) {
            await expect(core.getByText(state, { exact: true })).toBeVisible();
        }
        await expect(core.getByText("Connection refused", { exact: true })).toBeVisible();
        await expect(summary.getByText(/Last-known status: Healthy/)).toBeVisible();
        await page.route("**/api/v1/health", route => route.fulfill({ status: 503, json: { detail: "Unavailable" } }));
        await page.getByRole("button", { name: "Refresh", exact: true }).click();
        await expect(core.getByText(/Last-known status: Unavailable/)).toBeVisible();
        await expect(core.getByText("Unavailable", { exact: true })).toHaveCount(0);
        await expect(summary.getByRole("article", { name: "System assessment" }).getByText("Healthy", { exact: true })).toBeVisible();
        await page.route("**/api/v1/health", route => route.fulfill({ json: { atlas: "healthy", services: {} } }));
        await page.getByRole("button", { name: "Refresh", exact: true }).click();
        await expect(summary.getByRole("article", { name: "Atlas health" }).getByText("Healthy", { exact: true })).toBeVisible();
        const help = summary.getByText("How to read health", { exact: true });
        const note = summary.getByText("Core aggregate update time is not supplied.", { exact: true });
        await expect(note).not.toBeVisible();
        for (const name of ["Atlas health", "System assessment", "Policy status"]) await expect(summary.getByRole("heading", { name, exact: true, level: 3 })).toBeVisible();
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: `/tmp/atlas-plain-main-health-${width}.png`, fullPage: true });
        await help.focus();
        await page.keyboard.press("Enter");
        await expect(note).toBeVisible();
        await expect(summary.getByText(/Policy status reports whether the policy rules loaded successfully/)).toBeVisible();
        await page.keyboard.press("Enter");
        await expect(note).not.toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    });
}
