import { aceSummary, expect, test } from "./mission-control-fixtures";

const snapshots = [{ id: "reported-history", collected_at: "2026-10-26T12:00:00Z", telemetry: aceSummary.telemetry }];

for (const width of [320, 390, 1280]) for (const initiallyUnavailable of [false, true]) for (const failure of ["http", "shape", "metric"] as const) {
    test.describe(`Provider history at ${width}px (initial failure: ${initiallyUnavailable}, ${failure})`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("isolates an optional read failure and recovers without provider mutations", async ({ page, rejectedMutationRequests }) => {
            let phase: "initial" | "failed" | "recovered" = "initial";
            await page.route("**/api/v1/intelligence/telemetry/history?*", route => {
                if (phase === "failed" || (phase === "initial" && initiallyUnavailable)) {
                    if (failure === "http") return route.fulfill({ status: 503, json: { detail: "unavailable" } });
                    return route.fulfill({ json: failure === "shape" ? { private_detail: "private-history-canary", items: [] } : [{ ...snapshots[0], telemetry: { ...aceSummary.telemetry, providers: [{ ...aceSummary.telemetry.providers[0], duration_ms: null }] } }] });
                }
                return route.fulfill({ json: phase === "recovered" ? [] : snapshots });
            });
            await page.goto("/providers/proxmox");
            const overview = page.locator("section").filter({ has: page.getByRole("heading", { name: "Proxmox", level: 1 }) });
            const history = page.locator("section").filter({ has: page.getByRole("heading", { name: "Intelligence History", exact: true }) });
            await expect(overview.locator("[data-mc-status='success']")).toBeVisible();
            if (!initiallyUnavailable) {
                await expect(history.getByRole("img", { name: "Proxmox intelligence duration trend" })).toBeVisible();
                phase = "failed";
                await page.getByRole("button", { name: "Refresh", exact: true }).click();
            }
            if (initiallyUnavailable) {
                await expect(history.getByText("Collection history could not be loaded. Use Refresh to try again.", { exact: true })).toBeVisible();
                await expect(history.getByText(/No intelligence collection history/)).toHaveCount(0);
            } else {
                await expect(history.getByText("Collection history could not be refreshed. Showing the last reported history.", { exact: true })).toBeVisible();
                await expect(history.getByText("Last reported", { exact: true })).toBeVisible();
                await expect(history.getByRole("img", { name: "Proxmox intelligence duration trend" })).toBeVisible();
            }
            await expect(overview.locator("[data-mc-status='success']")).toBeVisible();
            await expect(page.getByText("Atlas Core unavailable", { exact: true })).toHaveCount(0);
            await expect(page.getByText("private-history-canary", { exact: false })).toHaveCount(0);
            phase = "recovered";
            await page.getByRole("button", { name: "Refresh", exact: true }).click();
            await expect(history.getByText("No intelligence collection history is available for this provider yet.", { exact: true })).toBeVisible();
            await expect(history.getByText(/Collection history could not/)).toHaveCount(0);
            await expect(history.getByRole("img")).toHaveCount(0);
            expect(rejectedMutationRequests).toEqual([]);
        });
    });
}
