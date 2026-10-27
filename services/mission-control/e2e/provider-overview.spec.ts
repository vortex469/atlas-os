import { expect, test, providers } from "./mission-control-fixtures";
import { management, resource } from "./resource-monitoring-fixture";

for (const width of [320, 390, 1280]) for (const status of ["healthy", "offline"]) {
    test.describe(`Compact provider overview at ${width}px (${status})`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("keeps health and monitoring visible while details remain keyboard accessible", async ({ page, rejectedMutationRequests }) => {
            const updatedAt = "2026-10-26T12:34:56.000Z";
            await page.clock.setFixedTime(new Date(updatedAt));
            const message = status === "healthy" ? "Provider is reachable." : "Provider is not reachable.";
            await page.route("**/api/v1/providers", route => route.fulfill({ json: providers.map(provider => ({ ...provider, capabilities: ["resources"],
                health: { ...provider.health, status, message, details: { url: "https://example.invalid/provider-health" } },
            })) }));
            await page.route("**/api/v1/providers/proxmox/resources", route => route.fulfill({ json: {
                provider_id: "proxmox", provider_name: "Proxmox", refreshed_at: "2026-01-01T00:00:00Z",
                resources: [{ ...resource, expectation: { value: null, label: "Needs Review", state: "needs_review", allowed_values: [] }, configured: false, needs_review: true, metadata: {} }],
                summary: { total: 1, configured: 0, needs_review: 1, missing: 0, ignored: 0, by_type: { qemu: 1 }, by_state: { running: 1 } }, metadata: {},
            } }));
            await page.route("**/api/v1/providers/proxmox/management", route => route.fulfill({ json: management }));
            await page.goto("/providers/proxmox");
            await expect(page.getByRole("heading", { name: "Proxmox", level: 1 })).toBeVisible();
            const refreshTime = page.locator(`time[datetime="${updatedAt}"]`);
            await expect(refreshTime).toHaveText(await page.evaluate(value => new Date(value).toLocaleString(), updatedAt));
            const refreshButton = page.getByRole("button", { name: "Refresh", exact: true });
            for (const control of [refreshTime, refreshButton]) {
                const bounds = await control.boundingBox();
                expect(bounds).not.toBeNull();
                expect(bounds!.x).toBeGreaterThanOrEqual(0);
                expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width + 1);
            }
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
            if (status === "healthy" && width !== 320) await page.screenshot({ path: `/tmp/atlas-provider-refresh-date-${width}.png`, fullPage: true });
            await expect(page.getByText(message, { exact: true })).toBeInViewport();
            const monitoring = page.getByRole("heading", { name: "Resources and monitoring", exact: true });
            await expect(monitoring).toBeInViewport();
            const overview = page.locator("section").filter({ has: page.getByRole("heading", { name: "Proxmox", level: 1 }) });
            await expect(overview.locator("[data-mc-status]")).toHaveText(status === "healthy" ? "Healthy" : "Unavailable");
            const summary = overview.locator("summary");
            await expect(summary).toHaveText("Technical details");
            await expect(overview.getByText("Latency", { exact: true })).toBeHidden();
            await expect(overview.getByText("https://example.invalid/provider-health", { exact: true })).toBeHidden();
            await summary.focus();
            await summary.press("Enter");
            await expect(overview.getByText("Latency", { exact: true })).toBeVisible();
            await expect(overview.getByText("HTTP Status", { exact: true })).toBeVisible();
            await expect(overview.getByText("Version", { exact: true })).toBeVisible();
            await expect(overview.getByText("Workspace", { exact: true })).toBeVisible();
            await expect(overview.getByText("Capabilities", { exact: true })).toBeVisible();
            await expect(overview.getByText("https://example.invalid/provider-health", { exact: true })).toBeVisible();
            await summary.press("Space");
            await expect(overview.getByText("Latency", { exact: true })).toBeHidden();
            await expect(page.getByText(message, { exact: true })).toBeVisible();
            expect(rejectedMutationRequests).toEqual([]);
        });
    });
}
