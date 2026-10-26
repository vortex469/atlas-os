import { expect, test } from "./mission-control-fixtures";

const clockStart = Date.parse("2026-10-26T12:00:00Z");
const report = {
    status: "healthy", score: 100, checked_at: new Date(clockStart).toISOString(), configuration_ok: true,
    checks: [{ name: "Docker", passed: true, error: null }], critical: [], warnings: [], information: ["Synthetic read-only snapshot."],
};

for (const width of [320, 390, 1280]) for (const malformed of ["partial", "nested"] as const) {
    test.describe(`Reliable Doctor report ${malformed} at ${width}px`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("recovers a malformed report and ages evidence without another diagnostic", async ({ page, baseURL, rejectedMutationRequests }) => {
            await page.clock.install({ time: new Date(clockStart) });
            let reads = 0;
            await page.route("**/api/v1/ops/doctor", async (route) => {
                expect(route.request().method()).toBe("GET");
                expect(new URL(route.request().url()).origin).toBe(new URL(baseURL!).origin);
                reads += 1;
                const bad = malformed === "partial"
                    ? { status: "healthy", score: 100, critical: ["private malformed health canary"] }
                    : { ...report, checks: [{ name: "Docker", passed: "true", error: null }], critical: ["private malformed health canary"] };
                await route.fulfill({ json: reads === 1 ? bad : reads === 2 ? report : {
                    ...report, status: "degraded", score: 95, checked_at: new Date(clockStart + 60_001).toISOString(),
                    warnings: ["Reported optional service warning."],
                } });
            });
            await page.goto("/operations");
            await page.getByText("Check Atlas health", { exact: true }).click();
            const panel = page.getByRole("region", { name: "Atlas Doctor", exact: true });
            expect(reads).toBe(0);
            await panel.getByRole("button", { name: "Run Doctor", exact: true }).click();
            await expect(panel.getByRole("alert")).toContainText("health-check report is incomplete or unreadable");
            await expect(panel.getByText("100/100", { exact: true })).toHaveCount(0);
            await expect(panel).not.toContainText("private malformed health canary");
            await panel.getByRole("button", { name: "Run Doctor", exact: true }).click();
            await expect(panel.getByText("healthy", { exact: true })).toBeVisible();
            await expect(panel.getByText("Results collected: 1 of 1 checks", { exact: true })).toBeVisible();
            await expect(panel.locator("time")).toHaveAttribute("datetime", report.checked_at);
            await expect(panel.getByText("Synthetic read-only snapshot.", { exact: true })).toBeHidden();
            await panel.getByText("Check details", { exact: true }).click();
            await expect(panel.getByText("Synthetic read-only snapshot.", { exact: true })).toBeVisible();
            expect(reads).toBe(2);
            await page.clock.fastForward(60_001);
            await expect(panel.getByText("Needs refresh", { exact: true })).toBeVisible();
            await expect(panel.getByText("Last reported status: healthy. Current health is unknown.", { exact: true })).toBeVisible();
            await expect(panel.getByText("healthy", { exact: true })).toHaveCount(0);
            expect(reads).toBe(2);
            await panel.getByRole("button", { name: "Run Doctor", exact: true }).click();
            await expect(panel.getByText("degraded", { exact: true })).toBeVisible();
            await expect(panel.getByText("Reported optional service warning.", { exact: false })).toBeVisible();
            await expect(panel.getByText("Needs refresh", { exact: true })).toHaveCount(0);
            expect(reads).toBe(3);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
            expect(rejectedMutationRequests).toEqual([]);
            if (malformed === "partial") {
                await page.evaluate(() => window.scrollTo(0, 0));
                await page.screenshot({ path: `/tmp/atlas-doctor-report-${width}.png`, fullPage: true });
            }
        });
    });
}

test("a future report remains unverified and preserves its critical findings", async ({ page, baseURL, rejectedMutationRequests }) => {
    await page.setViewportSize({ width: 390, height: 900 });
    await page.clock.install({ time: new Date(clockStart) });
    let reads = 0;
    await page.route("**/api/v1/ops/doctor", async (route) => {
        expect(route.request().method()).toBe("GET");
        expect(new URL(route.request().url()).origin).toBe(new URL(baseURL!).origin);
        reads += 1;
        await route.fulfill({ json: { ...report, status: "critical", score: 60, configuration_ok: false,
            checked_at: new Date(clockStart + 300_000).toISOString(), checks: [], critical: ["Configuration needs attention."] } });
    });
    await page.goto("/operations");
    await page.getByText("Check Atlas health", { exact: true }).click();
    const panel = page.getByRole("region", { name: "Atlas Doctor", exact: true });
    await panel.getByRole("button", { name: "Run Doctor", exact: true }).click();
    await expect(panel.getByText("Report time unverified", { exact: true })).toBeVisible();
    await expect(panel.getByText("Configuration needs attention.", { exact: false })).toBeVisible();
    await expect(panel.getByText("No individual checks were reported.", { exact: true })).toBeVisible();
    await page.clock.fastForward(600_000);
    await expect(panel.getByText("Report time unverified", { exact: true })).toBeVisible();
    await expect(panel.getByText("Last reported status: critical. Current health is unknown.", { exact: true })).toBeVisible();
    expect(reads).toBe(1);
    expect(rejectedMutationRequests).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: "/tmp/atlas-doctor-future-report-390.png", fullPage: true });
});
