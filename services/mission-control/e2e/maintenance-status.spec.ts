import { expect, test } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) {
    for (const report of ["missing", "incomplete"] as const) {
        test.describe(`Maintenance status ${report} at ${width}px`, () => {
            test.use({ viewport: { width, height: 900 } });
            test("keeps unknown evidence visible without presenting success", async ({ page, baseURL, rejectedMutationRequests }) => {
                const origin = new URL(baseURL!).origin;
                const reads: string[] = [];
                await page.route("**/agent-api/api/v1/agent/workflows**", async (route) => {
                    const request = route.request();
                    const url = new URL(request.url());
                    expect(request.method()).toBe("GET");
                    expect(url.origin).toBe(origin);
                    reads.push(url.pathname);
                    if (url.pathname.endsWith("/workflows")) {
                        await route.fulfill({ json: { items: [{ workflow_id: "maintenance-status", workflow_source: "candidate", workflow_state: "completed", effect_kind: "operational_action", execution_intent: "restart-service", target_id: "Read-only fixture", timeline: [] }], total: 1, limit: 10, offset: 0 } });
                    } else if (url.pathname.endsWith("/recovery-diagnostic") && report === "incomplete") {
                        await route.fulfill({ json: { applicable: true, diagnostic_status: "healthy", correlation: { workflow_id: "maintenance-status" } } });
                    } else {
                        await route.fulfill({ status: 404, json: { detail: "Not published" } });
                    }
                });
                await page.goto("/operations/history");
                await expect(page.getByText("Restart service · Status unavailable", { exact: true })).toBeVisible();
                const readCount = reads.length;
                await page.getByRole("combobox", { name: "Status", exact: true }).selectOption("unavailable");
                await expect(page.getByRole("link", { name: "Open workflow", exact: true })).toBeVisible();
                await expect(page.getByRole("heading", { name: "Healthy", exact: true })).toHaveCount(0);
                await page.getByRole("combobox", { name: "Completion", exact: true }).selectOption("non_terminal");
                await expect(page.getByText("No requests on this page match your filters.")).toBeVisible();
                await page.getByRole("button", { name: "Clear filters", exact: true }).click();
                await expect(page.getByRole("link", { name: "Open workflow", exact: true })).toBeVisible();
                expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
                expect(reads.length).toBe(readCount);
                expect(rejectedMutationRequests).toEqual([]);
            });
        });
    }
}
