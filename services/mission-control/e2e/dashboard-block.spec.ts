import { expect, test } from "./mission-control-fixtures";

test("dashboard explains unavailable workflow data once and translates network errors", async ({ page, rejectedMutationRequests }) => {
    await page.route("**/api/v1/health", route => route.fulfill({ json: {
        atlas: "degraded",
        services: {
            refused: { status: "offline", message: "[Errno 111] Connection refused" },
            unreachable: { status: "offline", message: "[Errno 113] No route to host" },
        },
    } }));
    await page.route(/\/agent-api\/api\/v1\/agent\/workflows(?:\?.*)?$/, route => route.fulfill({
        status: 503,
        json: { detail: "Fixture workflow service unavailable." },
    }));

    await page.goto("/");

    const attention = page.getByRole("region", { name: "Operator Attention" });
    const workActivity = page.getByRole("region", { name: "Work activity" });
    await expect(attention.getByText("Some information is missing. Atlas cannot confirm this list includes everything that needs attention.")).toBeVisible();
    await attention.getByText("Source status").click();
    await expect(attention.getByText("Workflows: current information could not be loaded.")).toBeVisible();
    await expect(attention.getByText("Workflow results are incomplete.")).toHaveCount(0);
    await expect(workActivity.getByText("Workflow status could not be loaded.")).toBeVisible();
    await expect(workActivity.getByText("Running workflows", { exact: true })).toHaveCount(0);
    await expect(workActivity.getByText("Blocked workflows", { exact: true })).toHaveCount(0);
    await expect(attention.getByText("The service refused the connection.")).toBeVisible();
    await expect(attention.getByText("The service could not be reached over the network.")).toBeVisible();
    await expect(page.getByText(/\[Errno \d+\]/)).toHaveCount(0);
    expect(rejectedMutationRequests).toEqual([]);
});

for (const width of [320, 390, 1280]) {
    test(`attention and source history fit ${width}px with safe navigation`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        const label = "Action".repeat(45);
        const entry = {
            id: "audit/1", provider_id: "fixture-provider", provider_name: "Provider".repeat(30),
            action_id: "fixture-action", action_label: label, status: "failed", success: false,
            message: "Fixture action failed.", confirmed: true, destructive: false,
            parameter_names: [], request_id: "request-123",
            started_at: "2026-09-01T11:59:59Z", completed_at: "2026-09-01T12:00:00Z", duration_ms: 1000,
        };
        await page.route("**/api/v1/ops/actions/page?**", route => {
            const url = new URL(route.request().url());
            const limit = Number(url.searchParams.get("limit") ?? "25");
            const items = limit === 5 ? [entry, entry] : [entry];
            return route.fulfill({ json: {
                items, total: items.length, offset: 0, limit, has_more: false,
            } });
        });
        await page.goto("/");
        const attention = page.getByRole("region", { name: "Operator Attention" });
        const activity = page.getByRole("region", { name: "Recent provider actions" });
        await expect(attention.getByText("Action needed: Waiting for implementation approval", { exact: true })).toBeVisible();
        await expect(activity.getByRole("listitem")).toHaveCount(1);
        await expect(activity.getByText(`Failed · ${label.slice(0, 240)}`)).toBeVisible();
        await expect(activity.getByText(/^Completed \(local time\) /)).toBeVisible();
        const activityColumns = await activity.getByRole("list").evaluate(node => getComputedStyle(node).gridTemplateColumns.split(" ").length);
        expect(activityColumns).toBe(width >= 768 ? 2 : 1);
        await expect(page.getByTestId("overview-grid").locator(":scope > section")).toHaveCount(6);
        for (const card of [attention, activity]) {
            const box = await card.evaluate(node => ({ left: node.getBoundingClientRect().left, right: node.getBoundingClientRect().right, scroll: node.scrollWidth, client: node.clientWidth }));
            expect(box.left).toBeGreaterThanOrEqual(0);
            expect(box.right).toBeLessThanOrEqual(width);
            expect(box.scroll).toBeLessThanOrEqual(box.client);
        }
        await attention.getByRole("link", { name: "Update Compose Stack" }).click();
        await expect(page).toHaveURL(/\/workflows\/workflow-browser-baseline$/);
        await page.goBack();
        await activity.getByRole("link", { name: "Inspect action →" }).click();
        await expect(page).toHaveURL(/\/operations\/actions\/audit%2F1$/);
        await page.goBack();
        await activity.getByRole("link", { name: "Open action history →" }).click();
        await expect(page).toHaveURL(/\/operations$/);
        await expect(page.getByRole("heading", { name: "Action history" })).toBeVisible();
        await expect(page.getByText(label, { exact: true })).toBeVisible();
        expect(rejectedMutationRequests).toEqual([]);
    });
}
