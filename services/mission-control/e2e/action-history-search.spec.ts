import { expect, test } from "./mission-control-fixtures";

for (const width of [390, 1280]) {
    test(`action history status filter announces selection at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/operations");

        const filters = page.getByRole("group", { name: "Filter action history" });
        const all = filters.getByRole("button", { name: "All", exact: true });
        const succeeded = filters.getByRole("button", { name: "Succeeded", exact: true });
        const failed = filters.getByRole("button", { name: "Failed", exact: true });
        await expect(all).toHaveAttribute("aria-pressed", "true");
        await expect(succeeded).toHaveAttribute("aria-pressed", "false");
        await expect(failed).toHaveAttribute("aria-pressed", "false");

        await failed.click();
        await expect(failed).toHaveAttribute("aria-pressed", "true");
        await expect(all).toHaveAttribute("aria-pressed", "false");
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [390, 1280]) {
    test(`action history explains confirmation and action risk at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/ops/actions/page**", (route) => route.fulfill({ json: {
            items: [{
                id: "audit-browser-labels",
                provider_id: "ollama",
                provider_name: "Ollama",
                action_id: "unload-model",
                action_label: "Unload Model",
                status: "succeeded",
                success: true,
                message: "Model unloaded.",
                confirmed: true,
                destructive: true,
                parameter_names: [],
                request_id: "request-labels",
                started_at: "2026-10-25T15:00:00Z",
                completed_at: "2026-10-25T15:00:01Z",
                duration_ms: 1000,
            }],
            total: 1,
            offset: 0,
            limit: 25,
            has_more: false,
        } }));

        await page.goto("/operations");
        const action = page.getByRole("article").filter({ hasText: "Unload Model" });
        await expect(action.getByText("Operator confirmed")).toBeVisible();
        await expect(action.getByText("Destructive action")).toBeVisible();
    });
}

for (const width of [390, 1280]) {
    test(`action history applies typed search before paging at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/ops/actions/page**", async (route) => {
            const url = new URL(route.request().url());
            const offset = Number(url.searchParams.get("offset") ?? "0");
            await route.fulfill({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify({
                    items: [{
                        id: "audit-browser-search",
                        provider_id: "ollama",
                        provider_name: "Ollama",
                        action_id: "unload-model",
                        action_label: "Unload Model",
                        status: "succeeded",
                        success: true,
                        message: "Model unloaded.",
                        confirmed: true,
                        destructive: false,
                        parameter_names: [],
                        request_id: "request-123",
                        started_at: "2026-07-25T17:00:00Z",
                        completed_at: "2026-07-25T17:00:01Z",
                        duration_ms: 12.5,
                    }],
                    total: 26,
                    offset,
                    limit: 25,
                    has_more: offset === 0,
                }),
            });
        });

        await page.goto("/operations");
        await expect(page.getByRole("heading", { name: "Action history", exact: true })).toBeVisible();
        const search = page.getByLabel("Action or request ID");
        const previous = page.getByRole("button", { name: "Previous" });
        const next = page.getByRole("button", { name: "Next" });

        await search.fill("request-123");
        await expect(page.getByText("Search text has changed. Select Search to update the results.")).toBeVisible();
        await expect(next).toBeDisabled();
        await page.getByRole("button", { name: "Search" }).click();
        await expect(page.getByText("Search text has changed. Select Search to update the results.")).toBeHidden();
        await expect(next).toBeEnabled();

        await next.click();
        await expect(page.getByText("Showing 26–26 of 26")).toBeVisible();
        await search.fill("changed-query");
        await expect(page.getByText("Search text has changed. Select Search to update the results.")).toBeVisible();
        await expect(previous).toBeDisabled();
        await expect(next).toBeDisabled();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
