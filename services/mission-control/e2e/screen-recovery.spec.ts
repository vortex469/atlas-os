import { expect, test } from "./mission-control-fixtures";

for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
    test(`unknown pages retain navigation at ${viewport.width}px`, async ({ page }) => {
        await page.setViewportSize(viewport);
        await page.goto("/page-that-does-not-exist");
        await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
        if (viewport.width < 1024) {
            await page.getByRole("button", { name: "Open navigation" }).click();
        }
        const navigation = page.getByRole("navigation", { name: "Primary" }).filter({ visible: true });
        await navigation.getByRole("link", { name: "Workflows", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Workflows", exact: true })).toBeVisible();
        await expect(page.getByText("workflow-browser-baseline")).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

test("an empty provider catalog has a clear way back", async ({ page }) => {
    await page.route("**/api/v1/providers", (route) => route.fulfill({
        status: 200, contentType: "application/json", body: "[]",
    }));
    await page.goto("/providers/proxmox");
    await expect(page.getByRole("heading", { name: "Provider not found" })).toBeVisible();
    await expect(page.getByText("Not updated yet")).not.toBeVisible();
    await page.getByRole("link", { name: "Return to Mission Control" }).click();
    await expect(page.getByRole("main", { name: "Mission Control command center" })).toBeVisible();
});

test("workflows recover from an initial outage without reloading", async ({ page }) => {
    let attempts = 0;
    await page.route("**/agent-api/**", async (route) => {
        if (new URL(route.request().url()).pathname.endsWith("/workflows")) {
            attempts += 1;
            if (attempts === 1) {
                await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Temporarily unavailable" }) });
                return;
            }
        }
        await route.fallback();
    });
    await page.goto("/workflows");
    await expect(page.getByRole("heading", { name: "Workflows unavailable" })).toBeVisible();
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByText("workflow-browser-baseline")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Workflows unavailable" })).not.toBeVisible();
    expect(attempts).toBe(2);
});

test("a broken page keeps navigation and hides raw error details", async ({ page }) => {
    await page.route("**/api/v1/discovery/items?**", (route) => route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ entries: [null], total: 1, offset: 0, limit: 25, has_more: false }),
    }));
    await page.goto("/discovery");
    await expect(page.getByRole("heading", { name: "This page could not load" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Reload page" })).toBeVisible();
    await expect(page.getByText("Unexpected Application Error!")).toHaveCount(0);
    await expect(page.getByText(/TypeError:|Cannot read properties/)).toHaveCount(0);
    await page.getByRole("link", { name: "Return to Mission Control" }).click();
    await expect(page.getByRole("main", { name: "Mission Control command center" })).toBeVisible();
});

test("maintenance history keeps unavailable requests findable and details optional", async ({ page }) => {
    let reads = 0;
    await page.route("**/agent-api/**", async (route) => {
        const path = new URL(route.request().url()).pathname;
        if (path.endsWith("/workflows")) {
            reads += 1;
            await route.fulfill({ json: {
                items: [{ workflow_id: "maintenance-test", workflow_source: "candidate",
                    workflow_state: "completed", effect_kind: "operational_action",
                    execution_intent: "restart-service", candidate_id: null,
                    planning_session_id: null, repository: null, target_id: "VM 110",
                    last_result_summary: "", timeline: [] }],
                total: 1, limit: 10, offset: 0,
            } });
            return;
        }
        if (path.includes("/workflows/maintenance-test/")) {
            await route.fulfill({ status: 503, json: { detail: "Unavailable" } });
            return;
        }
        await route.fallback();
    });
    await page.goto("/operations/history");
    await expect(page.getByRole("heading", { name: "VM 110" })).toBeVisible();
    await page.getByRole("combobox", { name: "Status", exact: true }).selectOption("unavailable");
    await expect(page.getByRole("heading", { name: "VM 110" })).toBeVisible();
    await expect(page.getByText("A diagnostic network failure is not an operational failure.")).toBeVisible();
    await expect(page.getByText("Workflow State", { exact: true })).toBeHidden();
    await page.getByText("Workflow details", { exact: true }).click();
    await expect(page.getByText("Workflow State", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open workflow" })).toHaveAttribute("href", "/workflows/maintenance-test");
    expect(reads).toBe(1);
});

for (const width of [390, 1280]) {
    test(`provider registry is reachable and links back from details at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/");
        await page.getByRole("link", { name: "View provider registry", exact: true }).click();
        await expect(page).toHaveURL(/\/providers$/);
        await expect(page.getByRole("heading", { name: "Providers", exact: true })).toBeVisible();
        await expect(page.getByLabel("Current page: Providers", { exact: true })).toBeVisible();
        await page.getByRole("link", { name: "Open Proxmox provider", exact: true }).click();
        await expect(page).toHaveURL(/\/providers\/proxmox$/);
        await expect(page.getByRole("heading", { name: "Proxmox", exact: true })).toBeVisible();
        await page.getByRole("link", { name: /All providers/ }).click();
        await expect(page).toHaveURL(/\/providers$/);
        await expect(page.getByRole("link", { name: "Open Proxmox provider" })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    });
}

test("provider registry retries an unavailable read", async ({ page }) => {
    let attempts = 0;
    await page.route("**/api/v1/providers", async (route) => {
        attempts += 1;
        if (attempts === 1) {
            await route.fulfill({ status: 503, json: { detail: "PRIVATE_SERVER_ERROR" } });
            return;
        }
        await route.fallback();
    });
    await page.goto("/providers");
    await expect(page.getByRole("alert")).toHaveText("Providers could not loadTry again to get the latest provider list.Try again");
    await expect(page.getByText("PRIVATE_SERVER_ERROR")).toHaveCount(0);
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("link", { name: "Open Proxmox provider" })).toBeVisible();
    expect(attempts).toBe(2);
});
