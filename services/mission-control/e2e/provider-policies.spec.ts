import { expect, policies, test } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) for (const initiallyUnavailable of [false, true]) {
    test.describe(`Provider policy reads at ${width}px (initial failure: ${initiallyUnavailable})`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("retains reference settings and suppresses unconfirmed threshold comparisons", async ({ page, rejectedMutationRequests }) => {
            let phase: "initial" | "failed" | "recovered" = "initial";
            await page.route("**/api/v1/policies", route => {
                if (phase === "failed" || (phase === "initial" && initiallyUnavailable)) return route.fulfill({ status: 503, json: { detail: "unavailable" } });
                return route.fulfill({ json: { ...policies,
                    proxmox: { guests: { "110": { expected: phase === "recovered" ? "running" : "stopped" } } },
                    intelligence: { providers: { proxmox: { maximum_collection_duration_ms: phase === "recovered" ? 30 : 10, severity: "warning" } } },
                } });
            });
            await page.goto("/providers/proxmox");
            const overview = page.locator("section").filter({ has: page.getByRole("heading", { name: "Proxmox", level: 1 }) });
            const history = page.locator("section").filter({ has: page.getByRole("heading", { name: "Intelligence History", exact: true }) });
            const settings = page.locator("section").filter({ has: page.getByRole("heading", { name: "Legacy policy evidence", exact: true }) });
            await expect(overview.locator("[data-mc-status='success']")).toBeVisible();
            if (!initiallyUnavailable) {
                await expect(history.getByLabel("Policy threshold 10 ms", { exact: true })).toBeVisible();
                await expect(settings.getByText("110: stopped", { exact: true })).toBeVisible();
                phase = "failed";
                await page.getByRole("button", { name: "Refresh", exact: true }).click();
            }
            await expect(history.getByText("Performance threshold could not be checked. Threshold comparisons are unavailable.", { exact: true })).toBeVisible();
            await expect(history.getByText("Over threshold", { exact: true })).toHaveCount(0);
            await expect(history.getByLabel("Policy threshold 10 ms", { exact: true })).toHaveCount(0);
            await expect(history.getByRole("img", { name: "Proxmox intelligence duration trend" })).toBeVisible();
            if (initiallyUnavailable) {
                await expect(settings.getByText("Policy settings could not be loaded. Use Refresh to try again.", { exact: true })).toBeVisible();
            } else {
                await expect(settings.getByText("Policy settings could not be refreshed. Showing the last reported settings.", { exact: true })).toBeVisible();
                await expect(settings.getByText("110: stopped", { exact: true })).toBeVisible();
            }
            await expect(overview.locator("[data-mc-status='success']")).toBeVisible();
            await expect(page.getByText("Atlas Core unavailable", { exact: true })).toHaveCount(0);
            phase = "recovered";
            await page.getByRole("button", { name: "Refresh", exact: true }).click();
            await expect(history.getByLabel("Policy threshold 30 ms", { exact: true })).toBeVisible();
            await expect(history.getByText("Over threshold", { exact: true })).toBeVisible();
            await expect(settings.getByText("110: running", { exact: true })).toBeVisible();
            await expect(settings.getByText(/Policy settings could not/)).toHaveCount(0);
            await expect(history.getByText(/Threshold comparisons are unavailable/)).toHaveCount(0);
            expect(rejectedMutationRequests).toEqual([]);
        });
    });
}
