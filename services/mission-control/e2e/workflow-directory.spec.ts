import type { WorkflowSummary } from "../src/types/atlasAgent";
import { expect, test } from "./mission-control-fixtures";

const allWorkflows: WorkflowSummary[] = Array.from({ length: 215 }, (_, index) => ({
    workflow_id: `directory-workflow-${String(index).padStart(3, "0")}`,
    workflow_source: "candidate", workflow_state: index === 214 ? "awaiting_commit_approval" : "completed",
    effect_kind: "repository_change", execution_intent: "update-compose-stack",
    candidate_id: `candidate-${index}`, planning_session_id: `planning-${index}`,
    repository: "/fixture/repository", target_id: "fixture-stack", last_result_summary: "Synthetic workflow history", timeline: [],
}));

for (const width of [320, 390, 1280]) {
    test(`the complete workflow directory is searchable at ${width}px`, async ({ page, baseURL, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 844 });
        const origin = new URL(baseURL ?? "http://127.0.0.1:5173").origin;
        const reads: Array<Record<string, string>> = [];
        await page.route("**/agent-api/api/v1/agent/workflows*", async (route) => {
            const request = route.request(); const url = new URL(request.url());
            if (request.method() !== "GET" || url.origin !== origin || url.pathname !== "/agent-api/api/v1/agent/workflows") {
                await route.fulfill({ status: 405, json: { detail: "Exact-origin directory reads only." } });
                return;
            }
            reads.push(Object.fromEntries(url.searchParams));
            const filters = url.searchParams;
            const selected = allWorkflows.filter((workflow) => {
                if (filters.has("state") && filters.get("state") !== workflow.workflow_state) return false;
                if (filters.has("source") && filters.get("source") !== workflow.workflow_source) return false;
                if (filters.has("candidate_id") && !workflow.candidate_id?.includes(filters.get("candidate_id")!)) return false;
                if (filters.has("workflow_id") && !workflow.workflow_id.includes(filters.get("workflow_id")!)) return false;
                const waiting = workflow.workflow_state === "awaiting_commit_approval";
                return !filters.has("waiting_for_approval") || waiting === (filters.get("waiting_for_approval") === "true");
            });
            const state_counts: Record<string, number> = {};
            for (const item of selected) state_counts[item.workflow_state] = (state_counts[item.workflow_state] ?? 0) + 1;
            const limit = Number(filters.get("limit")); const offset = Number(filters.get("offset"));
            await route.fulfill({ json: { items: selected.slice(offset, offset + limit), total: selected.length, limit, offset, state_counts } });
        });
        await page.goto("/workflows");
        await expect(page.getByText("directory-workflow-000", { exact: true })).toBeVisible();
        await expect(page.getByText("Showing 10 of 215 matching workflows", { exact: true })).toBeVisible();
        const applied = page.getByRole("region", {name: "Applied workflow filters", exact: true});
        await expect(applied).toContainText("All workflows");
        await expect(page.getByLabel("Source", {exact: true})).toBeAttached();
        await expect(page.getByLabel("Candidate ID", {exact: true})).toBeAttached();
        await expect(page.getByLabel("Source", {exact: true})).not.toBeVisible();
        await expect(page.getByLabel("Candidate ID", {exact: true})).not.toBeVisible();
        if (width !== 320) await page.locator('section[aria-labelledby="workflow-filters-heading"]').screenshot({path: `/tmp/atlas-workflow-filter-form-${width}.png`});
        const totals = page.locator('section[aria-labelledby="workflow-counts-heading"]');
        expect(await totals.evaluate(node => node.getBoundingClientRect().height)).toBeLessThan(width < 768 ? 600 : 500);
        await expect(totals.getByText("Completed", { exact: true }).locator("..").getByText("214", { exact: true })).toBeVisible();
        await expect(totals.getByText("Waiting for commit approval", { exact: true }).locator("..").getByText("1", { exact: true })).toBeVisible();
        if (width !== 320) await totals.screenshot({path: `/tmp/atlas-workflow-totals-${width}.png`});
        await page.getByRole("button", { name: "Next", exact: true }).click();
        await expect(page.getByText("directory-workflow-010", { exact: true })).toBeVisible();
        await page.getByLabel("Workflow ID search", { exact: true }).fill("directory-workflow-214");
        await page.getByRole("button", { name: "Apply filters", exact: true }).click();
        await expect(page.getByText("directory-workflow-214", { exact: true })).toBeVisible();
        await expect(page.getByText("Showing 1 of 1 matching workflows", { exact: true })).toBeVisible();
        await page.getByLabel("Workflow ID search", { exact: true }).fill("unmatched-workflow");
        await page.getByRole("button", { name: "Apply filters", exact: true }).click();
        await expect(page.getByText("No workflows match the current filters.", { exact: true })).toBeVisible();
        await expect(page.getByText("Try a broader search or clear the filters above.", { exact: true })).toBeVisible();
        await expect(page.getByRole("link", { name: "Review change proposals", exact: true })).toHaveCount(0);
        await page.getByRole("button", { name: "Clear filters", exact: true }).click();
        await expect(page.getByText("directory-workflow-000", { exact: true })).toBeVisible();
        await page.getByLabel("Waiting for approval", { exact: true }).selectOption("yes");
        await page.getByRole("button", { name: "Apply filters", exact: true }).click();
        await expect(page.getByText("directory-workflow-214", { exact: true })).toBeVisible();
        await page.getByLabel("Waiting for approval", { exact: true }).selectOption("no");
        await page.getByRole("button", { name: "Apply filters", exact: true }).click();
        await expect(page.getByText("Showing 10 of 214 matching workflows", { exact: true })).toBeVisible();
        const more = page.locator("summary", {hasText: "More filters"});
        await more.focus(); await page.keyboard.press("Enter");
        await expect(page.getByLabel("Source", {exact: true})).toBeVisible();
        await page.getByLabel("Source", {exact: true}).selectOption("candidate");
        await page.getByLabel("Candidate ID", {exact: true}).fill(" candidate-214 ");
        await page.getByLabel("Waiting for approval", {exact: true}).selectOption("");
        await expect(applied).toContainText("Approval: Not waiting for approval");
        expect(reads).toHaveLength(7);
        await page.getByRole("button", {name: "Apply filters", exact: true}).click();
        await expect(page.getByText("Showing 1 of 1 matching workflows", {exact: true})).toBeVisible();
        await expect(applied).toContainText("Source: Candidate");
        await expect(applied).toContainText("Candidate ID: candidate-214");
        await more.focus(); await page.keyboard.press("Enter");
        await expect(page.getByLabel("Candidate ID", {exact: true})).not.toBeVisible();
        await expect(applied).toBeVisible();
        expect(reads).toEqual([
            { limit: "10", offset: "0" }, { limit: "10", offset: "10" },
            { workflow_id: "directory-workflow-214", limit: "10", offset: "0" },
            { workflow_id: "unmatched-workflow", limit: "10", offset: "0" },
            { limit: "10", offset: "0" }, { waiting_for_approval: "true", limit: "10", offset: "0" },
            { waiting_for_approval: "false", limit: "10", offset: "0" },
            { source: "candidate", candidate_id: "candidate-214", limit: "10", offset: "0" },
        ]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}


test("a slow search keeps the form usable and cannot replace a newer result", async ({ page, baseURL, rejectedMutationRequests }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const origin = new URL(baseURL ?? "http://127.0.0.1:5173").origin;
    let release!: () => void;
    let requested!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    const started = new Promise<void>((resolve) => { requested = resolve; });
    await page.route("**/agent-api/api/v1/agent/workflows*", async (route) => {
        const request = route.request(); const url = new URL(request.url());
        if (request.method() !== "GET" || url.origin !== origin || url.pathname !== "/agent-api/api/v1/agent/workflows") {
            await route.fulfill({ status: 405 }); return;
        }
        const id = url.searchParams.get("workflow_id");
        if (id === "slow-query") { requested(); await held; }
        const selected = allWorkflows.filter((item) => !id || item.workflow_id.includes(id));
        const state_counts: Record<string, number> = {};
        for (const item of selected) state_counts[item.workflow_state] = (state_counts[item.workflow_state] ?? 0) + 1;
        await route.fulfill({ json: { items: selected.slice(0, 10), total: selected.length, limit: 10, offset: 0, state_counts } });
    });
    try {
        await page.goto("/workflows");
        await expect(page.getByText("directory-workflow-000", { exact: true })).toBeVisible();
        await page.getByLabel("Workflow ID search", { exact: true }).fill("slow-query");
        await page.getByRole("button", { name: "Apply filters", exact: true }).click();
        await started;
        await expect(page.getByLabel("Workflow ID search", { exact: true })).toBeVisible();
        await expect(page.getByText("directory-workflow-000", { exact: true })).toHaveCount(0);
        await page.getByLabel("Workflow ID search", { exact: true }).fill("directory-workflow-214");
        await page.getByRole("button", { name: "Apply filters", exact: true }).click();
        await expect(page.getByText("directory-workflow-214", { exact: true })).toBeVisible();
        const finished = page.waitForResponse((response) => new URL(response.url()).searchParams.get("workflow_id") === "slow-query");
        release(); await (await finished).finished();
        await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
        await expect(page.getByText("directory-workflow-214", { exact: true })).toBeVisible();
        await expect(page.getByText("Showing 1 of 1 matching workflows", { exact: true })).toBeVisible();
        expect(rejectedMutationRequests).toEqual([]);
    } finally { release(); }
});
