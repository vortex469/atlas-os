import { expect, test } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) {
    test(`attention and source history fit ${width}px with safe navigation`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        const label = "Action".repeat(45);
        const entry = { id: "audit/1", action_label: label, provider_name: "Provider".repeat(30), status: "failed", completed_at: "2026-09-01T12:00:00Z" };
        await page.route("**/api/v1/ops/actions/page?**", route => route.fulfill({ json: {
            items: [entry, entry], total: 2, offset: 0, limit: 5, has_more: false,
        } }));
        await page.goto("/");
        const attention = page.getByRole("region", { name: "Operator Attention" });
        const activity = page.getByRole("region", { name: "Recent Activity" });
        await expect(attention.getByText("Human action required", { exact: true })).toBeVisible();
        await expect(activity.getByRole("listitem")).toHaveCount(1);
        await expect(activity.getByText(`Error · ${label}`)).toBeVisible();
        await expect(page.getByTestId("overview-grid").locator(":scope > section")).toHaveCount(6);
        for (const card of [attention, activity]) {
            const box = await card.evaluate(node => ({ left: node.getBoundingClientRect().left, right: node.getBoundingClientRect().right, scroll: node.scrollWidth, client: node.clientWidth }));
            expect(box.left).toBeGreaterThanOrEqual(0);
            expect(box.right).toBeLessThanOrEqual(width);
            expect(box.scroll).toBeLessThanOrEqual(box.client);
        }
        await attention.getByRole("link", { name: "workflow-browser-baseline" }).click();
        await expect(page).toHaveURL(/\/workflows\/workflow-browser-baseline$/);
        await page.goBack();
        await activity.getByRole("link", { name: "Inspect action →" }).click();
        await expect(page).toHaveURL(/\/operations\/actions\/audit%2F1$/);
        await page.goBack();
        await activity.getByRole("link", { name: "Open operational history →" }).click();
        await expect(page).toHaveURL(/\/operations\/history$/);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
