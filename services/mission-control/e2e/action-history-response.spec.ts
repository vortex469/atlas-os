import fixture from "../src/test/actionHistory.fixture.json" with { type: "json" };
import { expect, test } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) {
    for (const mode of ["record", "page", "metadata"] as const) {
        test.describe(`Validated history ${mode} at ${width}px`, () => {
            test.use({ viewport: { width, height: 900 } });
            test("owns malformed successful responses and recovers through reads", async ({ page, baseURL, rejectedMutationRequests }) => {
                const origin = new URL(baseURL!).origin;
                const reads = { page: 0, summary: 0, providers: 0 };
                await page.route("**/api/v1/ops/actions/**", async (route) => {
                    const request = route.request();
                    const url = new URL(request.url());
                    expect(request.method()).toBe("GET");
                    expect(url.origin).toBe(origin);
                    if (url.pathname.endsWith("/page")) {
                        reads.page += 1;
                        expect(url.searchParams.get("limit")).toBe("25");
                        expect(url.searchParams.get("offset")).toBe("0");
                        const data = reads.page === 1 && mode === "record"
                            ? { ...fixture.page, items: [{ ...fixture.entry, duration_ms: "invalid", message: "private response canary" }] }
                            : reads.page === 1 && mode === "page" ? { ...fixture.page, total: 2 } : fixture.page;
                        await route.fulfill({ json: data });
                    } else if (url.pathname.endsWith("/summary")) {
                        reads.summary += 1;
                        await route.fulfill({ json: mode === "metadata" && reads.summary === 1
                            ? { ...fixture.summary, retention_days: 0 } : fixture.summary });
                    } else if (url.pathname.endsWith("/providers")) {
                        reads.providers += 1;
                        await route.fulfill({ json: mode === "metadata" && reads.providers === 1
                            ? { private_native_canary: "not an array" } : fixture.providers });
                    } else throw new Error(`Unexpected history read: ${url.pathname}`);
                });
                await page.goto("/operations");
                await expect(page.getByRole("heading", { name: "Action History", exact: true })).toBeVisible();
                if (mode === "metadata") {
                    await expect(page.getByRole("heading", { name: fixture.entry.action_label, exact: true })).toBeVisible();
                } else {
                    await expect(page.getByRole("alert")).toContainText("action history report is incomplete or inconsistent");
                    await expect(page.getByRole("heading", { name: fixture.entry.action_label, exact: true })).toHaveCount(0);
                }
                await page.getByText("Export and cleanup", { exact: true }).click();
                const cleanup = page.getByRole("button", { name: "Prune expired", exact: true });
                await expect(cleanup).toBeDisabled();
                if (mode === "metadata") {
                    await expect(page.getByText("Retention policy unavailable.", { exact: true })).toBeVisible();
                    await page.getByText("Search and filters", { exact: true }).click();
                    await expect(page.getByText(/Provider choices are unavailable/)).toBeVisible();
                }
                await expect(page.getByText("private response canary", { exact: true })).toHaveCount(0);
                await expect(page.getByText("not an array", { exact: true })).toHaveCount(0);
                await page.getByRole("button", { name: "Refresh history", exact: true }).click();
                await expect(page.getByRole("heading", { name: fixture.entry.action_label, exact: true })).toBeVisible();
                await expect(cleanup).toBeEnabled();
                await expect(page.getByRole("alert")).toHaveCount(0);
                await expect(page.getByText(/Provider choices are unavailable/)).toHaveCount(0);
                await expect.poll(() => reads).toEqual({ page: 2, summary: 2, providers: 2 });
                expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
                expect(rejectedMutationRequests).toEqual([]);
            });
        });
    }
    test.describe(`Validated audit detail at ${width}px`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("does not display a contradictory success and retries only the read", async ({ page, baseURL, rejectedMutationRequests }) => {
            let reads = 0;
            await page.route(`**/api/v1/ops/actions/${fixture.entry.id}`, async (route) => {
                expect(route.request().method()).toBe("GET");
                expect(new URL(route.request().url()).origin).toBe(new URL(baseURL!).origin);
                reads += 1;
                await route.fulfill({ json: reads === 1
                    ? { ...fixture.entry, success: false, message: "private contradictory result canary" } : fixture.entry });
            });
            await page.goto(`/operations/actions/${fixture.entry.id}`);
            await expect(page.getByRole("alert")).toContainText("audit record is incomplete or inconsistent");
            await expect(page.getByRole("heading", { name: fixture.entry.action_label, exact: true })).toHaveCount(0);
            await expect(page.getByText("private contradictory result canary", { exact: true })).toHaveCount(0);
            await page.getByRole("button", { name: "Try again", exact: true }).click();
            await expect(page.getByRole("heading", { name: fixture.entry.action_label, exact: true })).toBeVisible();
            await expect(page.getByRole("alert")).toHaveCount(0);
            expect(reads).toBe(2);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
            expect(rejectedMutationRequests).toEqual([]);
        });
    });
}
