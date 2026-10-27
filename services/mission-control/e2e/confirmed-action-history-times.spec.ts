import { expect, test } from "./mission-control-fixtures";

const entry = {
    id: "future-time-audit", provider_id: "fixture", provider_name: "Example provider",
    action_id: "inspect-service", action_label: "Inspect fixture service", status: "succeeded", success: true,
    message: "Reported inspection succeeded.", confirmed: true, destructive: false,
    parameter_names: [], request_id: "future-time-request",
    started_at: "2099-10-27T12:00:00Z", completed_at: "2099-10-27T12:00:01Z", duration_ms: 1000,
};

for (const width of [320, 390, 1280]) {
    const reportedEntry = { ...entry, confirmed: width !== 320 };
    test(`future action times stay unknown at ${width}px while the reported result remains readable`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        const reads: string[] = [];
        await page.route("**/api/v1/ops/actions/**", route => {
            expect(route.request().method()).toBe("GET");
            const path = new URL(route.request().url()).pathname;
            reads.push(path);
            if (path.endsWith("/page")) return route.fulfill({ json: { items: [reportedEntry], total: 1, offset: 0, limit: 25, has_more: false } });
            if (path.endsWith("/summary")) return route.fulfill({ json: { entry_count: 1, max_entries: 5000, retention_days: 90, oldest_entry_at: entry.completed_at, newest_entry_at: entry.completed_at } });
            if (path.endsWith("/providers")) return route.fulfill({ json: [{ id: entry.provider_id, name: entry.provider_name }] });
            expect(path).toBe(`/api/v1/ops/actions/${entry.id}`);
            return route.fulfill({ json: reportedEntry });
        });
        await page.goto("/operations");
        await expect(page.getByText("Unknown time", { exact: true })).toBeVisible();
        await expect(page.getByText(entry.message, { exact: true })).toBeVisible();
        await expect(page.getByRole("article").getByText("succeeded", { exact: true })).toBeVisible();
        if (reportedEntry.confirmed) await expect(page.getByRole("article").getByText("Request confirmed", { exact: true })).toBeVisible();
        else await expect(page.getByRole("article").getByText("Request confirmed", { exact: true })).toHaveCount(0);
        await expect.poll(() => reads.length).toBe(3);
        await page.getByRole("link", { name: "View audit details", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Audit details", exact: true })).toBeVisible();
        await expect(page.locator("time").getByText("Unknown time", { exact: true })).toBeVisible();
        await expect(page.getByText(entry.message, { exact: true })).toBeVisible();
        if (reportedEntry.confirmed) await expect(page.getByText("Request confirmed", { exact: true })).toBeVisible();
        else await expect(page.getByText("Request confirmed", { exact: true })).toHaveCount(0);
        const details = page.getByText("Technical details", { exact: true });
        await details.focus();
        await page.keyboard.press("Enter");
        for (const label of ["Started", "Completed"]) {
            await expect(page.getByText(label, { exact: true }).locator("..").locator("dd")).toHaveText("Unknown time");
        }
        await expect(page.getByText(entry.request_id, { exact: true })).toBeVisible();
        expect(reads.sort()).toEqual(["/api/v1/ops/actions/page", "/api/v1/ops/actions/providers", "/api/v1/ops/actions/summary", `/api/v1/ops/actions/${entry.id}`].sort());
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await page.evaluate(() => window.scrollTo(0, 0));
        if (width !== 320) await page.screenshot({ path: `/tmp/atlas-action-confirmation-${width}.png`, fullPage: true });
    });
}
