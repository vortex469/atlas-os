import { expect, test } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) {
    test(`workflow cards show the next step and keep reference details optional at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/workflows");

        const summaryCounts = page.getByRole("region", { name: "Workflow summary counts" });
        await expect(summaryCounts.getByRole("article")).toHaveCount(1);
        await expect(summaryCounts).toContainText("Needs your input");
        await expect(summaryCounts).not.toContainText("Running");
        await expect(summaryCounts).not.toContainText("Blocked");
        await expect(summaryCounts).not.toContainText("Completed");
        await expect(summaryCounts).not.toContainText("Status unavailable");

        await expect(page.getByLabel("Workflow status")).toBeVisible();
        await expect(page.getByRole("option", { name: "Prepare change for review" })).toBeAttached();
        await expect(page.getByRole("option", { name: "Review checks, then run if approved" })).toBeAttached();
        await expect(page.getByRole("option", { name: "Review commit, then record if approved" })).toBeAttached();
        await expect(page.getByLabel("Next step")).toBeVisible();
        await expect(page.getByLabel("Workflow ID contains")).toBeHidden();
        await page.getByText("More filters", { exact: true }).click();
        await expect(page.getByLabel("Workflow ID contains")).toBeVisible();

        const heading = page.getByRole("heading", { name: "Update Compose Stack", exact: true });
        await expect(heading).toBeVisible();
        const card = heading.locator("xpath=ancestor::article[1]");
        await expect(card.getByText("Stage: Change approval", { exact: true })).toBeVisible();
        await expect(card.getByText("Review the change. If approved, choose Run approved change.", { exact: true })).toBeVisible();
        await expect(card.getByText("Your approval is needed", { exact: true })).toHaveCount(0);
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
            "/workflows/workflow-browser-baseline?returnTo=%2Fworkflows",
        );

        await page.getByLabel("Workflow status").selectOption("completed");
        await expect(page.getByText("These filter changes haven't been applied yet. Select Apply filters to update the workflow list.")).toBeVisible();
        await page.getByRole("button", { name: "Apply filters" }).click();
        await expect(page.getByText("These filter changes haven't been applied yet. Select Apply filters to update the workflow list.")).toHaveCount(0);
        await expect(page.getByText("No workflows match the current filters.")).toBeVisible();
        await expect(page.getByRole("region", { name: "Workflow summary counts" })).toHaveCount(0);
        await page.getByRole("button", { name: "Clear filters" }).click();
        await expect(page.getByRole("heading", { name: "Update Compose Stack", exact: true })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 1280]) {
    test(`workflow list explains background updates while work is running at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/api/v1/agent/workflows**", route => route.fulfill({ json: {
            items: [{
                workflow_id: "workflow-running",
                workflow_source: "candidate",
                workflow_state: "executing",
                effect_kind: "repository_change",
                execution_intent: "update-compose-stack",
                candidate_id: "candidate-running",
                planning_session_id: "planning-running",
                repository: "/repo",
                target_id: null,
                last_result_summary: "Applying the change.",
                timeline: [],
            }],
            total: 1,
            limit: 200,
            offset: 0,
        } }));
        await page.goto("/workflows");

        const note = page.getByText("The list checks for updates every 5 seconds while a workflow is running.", { exact: true });
        const refreshButton = page.getByRole("button", { name: "Refresh", exact: true });
        await expect(note).toBeVisible();
        await expect(refreshButton).toHaveAttribute("aria-describedby", "workflow-auto-refresh-note");
        await expect(page.getByText("Refreshing workflows...", { exact: true })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`maintenance workflow card shows its safe next step at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/api/v1/agent/workflows**", route => route.fulfill({ json: {
            items: [{
                workflow_id: "maintenance-review",
                workflow_source: "candidate",
                workflow_state: "awaiting_implementation_approval",
                effect_kind: "operational_action",
                execution_intent: "restart-service",
                candidate_id: null,
                planning_session_id: null,
                repository: null,
                target_id: "VM 110",
                last_result_summary: "Waiting for implementation approval",
                timeline: [],
            }],
            total: 1,
            limit: 200,
            offset: 0,
        } }));
        await page.goto("/workflows");

        const title = page.getByRole("heading", { name: "Restart Service", exact: true });
        await expect(title).toBeVisible();
        const card = title.locator("xpath=ancestor::article[1]");
        await expect(card.getByText("Stage: Maintenance request approval", { exact: true })).toBeVisible();
        await expect(card.getByText("Review the maintenance request. If approved, choose Run approved maintenance.", { exact: true })).toBeVisible();
        await expect(card.getByRole("link", { name: "Review maintenance request", exact: true })).toHaveAttribute("href", "/workflows/maintenance-review?returnTo=%2Fworkflows");
        await expect(card.getByText("Your approval is needed", { exact: true })).toHaveCount(0);
        await expect(card.getByText("Stage: Change approval", { exact: true })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`workflow preparation state is described as a review step at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/api/v1/agent/workflows**", route => route.fulfill({ json: {
            items: [{
                workflow_id: "workflow-preparation",
                workflow_source: "candidate",
                workflow_state: "awaiting_approval",
                effect_kind: "repository_change",
                execution_intent: "update-compose-stack",
                candidate_id: "candidate-preparation",
                planning_session_id: "planning-preparation",
                repository: "/repo",
                target_id: null,
                last_result_summary: "No result yet",
                timeline: [],
            }],
            total: 1,
            limit: 200,
            offset: 0,
        } }));
        await page.goto("/workflows");

        const title = page.getByRole("heading", { name: "Update Compose Stack", exact: true });
        await expect(title).toBeVisible();
        const card = title.locator("xpath=ancestor::article[1]");
        await expect(card.getByText("Stage: Prepare change", { exact: true })).toBeVisible();
        await expect(card.getByText("Prepare the change for review.", { exact: true })).toBeVisible();
        await expect(card.getByText("Your approval is needed", { exact: true })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`unknown workflow status is clear and its reported value stays optional at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/api/v1/agent/workflows**", route => route.fulfill({ json: {
            items: [{
                workflow_id: "workflow-future-status",
                workflow_source: "candidate",
                workflow_state: "future_state",
                effect_kind: "repository_change",
                execution_intent: "future-task",
                candidate_id: null,
                planning_session_id: null,
                repository: null,
                target_id: null,
                last_result_summary: "Result unavailable",
                timeline: [],
            }],
            total: 1,
            limit: 200,
            offset: 0,
        } }));
        await page.goto("/workflows");

        const title = page.getByRole("heading", { name: "Future Task", exact: true });
        await expect(title).toBeVisible();
        const card = title.locator("xpath=ancestor::article[1]");
        await expect(card.getByText("Stage: Status unavailable", { exact: true })).toBeVisible();
        await expect(page.getByRole("region", { name: "Workflow summary counts" })).toContainText("Status unavailable");
        await expect(card.getByText("Reported workflow status", { exact: true })).toBeHidden();
        await card.getByText("Workflow details", { exact: true }).click();
        await expect(card.getByText("future_state", { exact: true })).toBeVisible();
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
        await expect(page.getByRole("region", { name: "Workflow summary counts" })).toHaveCount(0);
        await expect(page.getByText("0 workflows", { exact: true })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

test("workflow empty state stays clear when a saved filter has no matches", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 900 });
    await page.route("**/agent-api/api/v1/agent/workflows**", route => route.fulfill({ json: {
        items: [], total: 0, limit: 200, offset: 0,
    } }));
    await page.goto("/workflows?workflow=missing");

    await expect(page.getByText("No workflows match the current filters.", { exact: true })).toBeVisible();
    await expect(page.getByText("No workflows yet.", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Additional filters are applied")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

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
        await expect(alert).toContainText("Atlas couldn't load your workflows. Try again to get the latest list.");
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
