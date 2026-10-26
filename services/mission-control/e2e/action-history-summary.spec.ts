import { expect, test } from "./mission-control-fixtures";

const entry = {
    id: `audit-${"a".repeat(64)}`, provider_id: "fixture", provider_name: "Example provider",
    action_id: "restart-service", action_label: "Restart fixture service", status: "succeeded", success: true,
    message: `Fixture service restarted. ${"x".repeat(160)}`, confirmed: true, destructive: false,
    parameter_names: ["service"], request_id: `request-${"b".repeat(64)}`,
    started_at: "2026-10-01T12:00:00Z", completed_at: "2026-10-01T12:00:01Z", duration_ms: 1000,
};

for (const width of [320, 390, 1280]) {
    for (const metadata of ["available", "failed", "delayed"] as const) {
        test.describe(`Readable action history at ${width}px with ${metadata} metadata`, () => {
            test.use({ viewport: { width, height: 900 } });
            test("prioritizes records and scopes optional read problems", async ({ page, baseURL, rejectedMutationRequests }) => {
                const origin = new URL(baseURL!).origin;
                const queries: Array<string | null> = [];
                const providerQueries: Array<string | null> = [];
                let summaryReads = 0;
                let providerReads = 0;
                let release!: () => void;
                const gate = new Promise<void>((resolve) => { release = resolve; });
                await page.route("**/api/v1/ops/actions/**", async (route) => {
                    const request = route.request();
                    const url = new URL(request.url());
                    expect(request.method()).toBe("GET");
                    expect(url.origin).toBe(origin);
                    if (url.pathname.endsWith("/page")) {
                        queries.push(url.searchParams.get("status"));
                        providerQueries.push(url.searchParams.get("provider_id"));
                        expect(url.searchParams.get("limit")).toBe("25");
                        expect(url.searchParams.get("offset")).toBe("0");
                        const items = url.searchParams.get("status") === "failed" ? [] : [entry];
                        await route.fulfill({ json: { items, total: items.length, offset: 0, limit: 25, has_more: false } });
                    } else if (url.pathname.endsWith("/summary")) {
                        summaryReads += 1;
                        if (metadata === "delayed" && summaryReads === 1) await gate;
                        await route.fulfill(metadata === "failed" && summaryReads === 1
                            ? { status: 503, json: { detail: "Private retention exception" } }
                            : { json: { entry_count: 1, max_entries: 5000, retention_days: 90, oldest_entry_at: entry.completed_at, newest_entry_at: entry.completed_at } });
                    } else if (url.pathname.endsWith("/providers")) {
                        providerReads += 1;
                        if (metadata === "delayed" && providerReads === 1) await gate;
                        await route.fulfill(metadata === "failed" && providerReads === 1
                            ? { status: 503, json: { detail: "Private provider exception" } }
                            : { json: [{ id: "fixture", name: "Example provider" }] });
                    } else {
                        throw new Error(`Unexpected history request: ${url.pathname}`);
                    }
                });
                try {
                    await page.goto("/operations");
                    const heading = page.getByRole("heading", { name: entry.action_label, exact: true });
                    await expect(heading).toBeVisible();
                    for (const label of ["Search and filters", "Export and cleanup", "Check Atlas health", "Technical details"]) {
                        await expect(page.getByText(label, { exact: true }).locator("..")).not.toHaveAttribute("open");
                    }
                    await expect(page.getByText(entry.request_id, { exact: true })).toBeHidden();
                    await expect(page.getByRole("button", { name: "Prune expired" })).toBeHidden();
                    await expect(page.getByRole("button", { name: "Run Doctor", exact: true })).toBeHidden();
                    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
                    if (metadata === "available") await page.screenshot({ path: `/tmp/atlas-action-history-${width}.png`, fullPage: true });
                    await page.getByText("Export and cleanup", { exact: true }).click();
                    const cleanup = page.getByRole("button", { name: "Prune expired" });
                    if (metadata === "delayed") {
                        await expect(page.getByText("Loading retention policy...")).toBeVisible();
                        await expect(cleanup).toBeDisabled();
                        release();
                        await expect(cleanup).toBeEnabled();
                    } else if (metadata === "failed") {
                        await expect(page.getByText("Retention policy unavailable.")).toBeVisible();
                        await expect(cleanup).toBeDisabled();
                    } else await expect(cleanup).toBeEnabled();
                    await page.getByText("Search and filters", { exact: true }).click();
                    await expect(page.getByText("Dates use UTC. Results below show the current search.")).toBeVisible();
                    if (metadata === "failed") {
                        await expect(page.getByText(/Provider choices are unavailable/)).toBeVisible();
                        await page.getByRole("button", { name: "Refresh history", exact: true }).click();
                        await expect(page.getByText(/Provider choices are unavailable/)).toHaveCount(0);
                        await expect(cleanup).toBeEnabled();
                    }
                    await page.getByText("Technical details", { exact: true }).click();
                    await expect(page.getByText(entry.request_id, { exact: true })).toBeVisible();
                    expect(queries).toEqual(metadata === "failed" ? [null, null] : [null]);
                    const filteredRead = page.waitForResponse((response) => {
                        const url = new URL(response.url());
                        return url.pathname === "/api/v1/ops/actions/page" && url.searchParams.get("provider_id") === "fixture";
                    });
                    await page.getByLabel("Provider", { exact: true }).selectOption("fixture");
                    await filteredRead;
                    await expect(page.getByText("Filters are active.", { exact: true })).toBeVisible();
                    await expect(heading).toBeVisible();
                    expect(providerQueries.at(-1)).toBe("fixture");
                    await page.getByText("Search and filters", { exact: true }).click();
                    await expect(page.getByLabel("Provider", { exact: true })).toBeHidden();
                    await expect(page.getByText("Filters are active.", { exact: true })).toBeVisible();
                    const clearedRead = page.waitForResponse((response) => {
                        const url = new URL(response.url());
                        return url.pathname === "/api/v1/ops/actions/page" && !url.searchParams.has("provider_id");
                    });
                    await page.getByRole("button", { name: "Show all actions", exact: true }).click();
                    await clearedRead;
                    await expect(heading).toBeVisible();
                    await expect(page.getByText("Filters are active.", { exact: true })).toHaveCount(0);
                    expect(providerQueries.at(-1)).toBeNull();
                    await page.getByRole("button", { name: "Failed", exact: true }).click();
                    await expect(page.getByText("No matching actions", { exact: true })).toBeVisible();
                    await page.getByRole("button", { name: "Show all actions", exact: true }).click();
                    await expect(heading).toBeVisible();
                    expect(queries.slice(-2)).toEqual(["failed", null]);
                    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
                    expect(rejectedMutationRequests).toEqual([]);
                    await expect(page.getByText("Private retention exception")).toHaveCount(0);
                    await expect(page.getByText("Private provider exception")).toHaveCount(0);
                } finally { release(); }
            });
        });
    }
}

test("a page emptied by retention offers a working way back", async ({ page, baseURL, rejectedMutationRequests }) => {
    await page.setViewportSize({ width: 390, height: 900 });
    const offsets: number[] = [];
    await page.route("**/api/v1/ops/actions/**", async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        expect(request.method()).toBe("GET");
        expect(url.origin).toBe(new URL(baseURL!).origin);
        if (url.pathname.endsWith("/page")) {
            const offset = Number(url.searchParams.get("offset"));
            offsets.push(offset);
            const items = offset > 0 ? [] : Array.from({ length: offsets.length === 1 ? 25 : 1 }, (_, index) => ({ ...entry, id: `audit-${index}`, action_label: `Recorded action ${index + 1}` }));
            await route.fulfill({ json: { items, offset, limit: 25, total: offsets.length === 1 ? 26 : 1, has_more: offsets.length === 1 } });
        } else if (url.pathname.endsWith("/summary")) {
            await route.fulfill({ json: { entry_count: 1, max_entries: 5000, retention_days: 90, oldest_entry_at: entry.completed_at, newest_entry_at: entry.completed_at } });
        } else if (url.pathname.endsWith("/providers")) {
            await route.fulfill({ json: [{ id: "fixture", name: "Example provider" }] });
        } else throw new Error(`Unexpected history request: ${url.pathname}`);
    });
    await page.goto("/operations");
    await expect(page.getByRole("heading", { name: "Recorded action 1", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(page.getByText("No actions on this page", { exact: true })).toBeVisible();
    await expect(page.getByText("No actions recorded", { exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Previous page", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Recorded action 1", exact: true })).toBeVisible();
    expect(offsets).toEqual([0, 25, 0]);
    expect(rejectedMutationRequests).toEqual([]);
});
