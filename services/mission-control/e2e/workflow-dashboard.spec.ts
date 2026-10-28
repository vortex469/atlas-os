import { expect, test } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) {
    test(`workflow cards keep approval status visible and reference details optional at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/workflows");

        await expect(page.getByLabel("Workflow status")).toBeVisible();
        await expect(page.getByLabel("Approval status")).toBeVisible();
        await expect(page.getByLabel("Workflow ID contains")).toBeHidden();
        await page.getByText("More filters", { exact: true }).click();
        await expect(page.getByLabel("Workflow ID contains")).toBeVisible();

        const heading = page.getByRole("heading", { name: "Update Compose Stack", exact: true });
        await expect(heading).toBeVisible();
        const card = heading.locator("xpath=ancestor::article[1]");
        await expect(card.getByText("Stage: Change approval", { exact: true })).toBeVisible();
        await expect(card.getByText("Your approval is needed", { exact: true })).toBeVisible();
        await expect(card.getByText("Current State", { exact: true })).toHaveCount(0);
        await expect(card.getByText("Workflow ID", { exact: true })).toBeHidden();
        await expect(card.getByText("workflow-browser-baseline", { exact: true })).toBeHidden();
        await expect(card.getByText("Candidate ID", { exact: true })).toBeHidden();

        await card.getByText("Workflow details", { exact: true }).click();
        await expect(card.getByText("Workflow ID", { exact: true })).toBeVisible();
        await expect(card.getByText("workflow-browser-baseline", { exact: true })).toBeVisible();
        await expect(card.getByText("Candidate ID", { exact: true })).toBeVisible();
        await expect(card.getByText("candidate-browser-baseline", { exact: true })).toBeVisible();
        await expect(card.getByRole("link", { name: "Open workflow", exact: true })).toHaveAttribute(
            "href",
            "/workflows/workflow-browser-baseline",
        );

        await page.getByLabel("Workflow status").selectOption("completed");
        await expect(page.getByText("These filter changes haven't been applied yet. Select Apply filters to update the workflow list.")).toBeVisible();
        await page.getByRole("button", { name: "Apply filters" }).click();
        await expect(page.getByText("These filter changes haven't been applied yet. Select Apply filters to update the workflow list.")).toHaveCount(0);
        await expect(page.getByText("No workflows match the current filters.")).toBeVisible();
        await page.getByRole("button", { name: "Clear filters" }).click();
        await expect(page.getByRole("heading", { name: "Update Compose Stack", exact: true })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`workflow empty state explains the result without a duplicate count at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/api/v1/agent/workflows**", route => route.fulfill({ json: {
            items: [], total: 0, limit: 200, offset: 0,
        } }));
        await page.goto("/workflows");
        await expect(page.getByText("No workflows yet.", { exact: true })).toBeVisible();
        await expect(page.getByText("0 workflows", { exact: true })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

for (const width of [320, 390, 1280]) {
    test(`malformed workflow data offers a read-only retry at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let reads = 0;
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/api/v1/agent/workflows**", route => {
            reads += 1;
            return route.fulfill({ json: reads === 1
                ? { items: [null], total: 1, limit: 200, offset: 0 }
                : { items: [], total: 0, limit: 200, offset: 0 } });
        });
        await page.goto("/workflows");

        const alert = page.getByRole("alert");
        await expect(alert).toContainText("Workflows unavailable");
        await expect(alert).toContainText("Mission Control could not load the workflow list.");
        await expect(page.getByRole("heading", { name: "This page could not load" })).toHaveCount(0);
        if (width < 1024) {
            await page.getByRole("button", { name: "Open navigation" }).click();
            await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
            await page.getByRole("button", { name: "Close navigation" }).click();
        }

        await alert.getByRole("button", { name: "Try again" }).click();
        await expect(page.getByText("No workflows yet.", { exact: true })).toBeVisible();
        expect(reads).toBe(2);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
