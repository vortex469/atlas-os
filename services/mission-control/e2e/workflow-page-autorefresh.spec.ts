import { workflowDetail } from "../src/test/workflowDetail";
import { expect, test } from "./mission-control-fixtures";

const runningWorkflow = workflowDetail({
    workflow_id: "workflow-running",
    workflow_state: "verifying",
    implementation_approval_status: "approved",
    timeline: [
        { name: "Execution Candidate", status: "completed" },
        { name: "Planning Session", status: "completed" },
        { name: "Candidate Plan", status: "completed" },
        { name: "Workflow", status: "completed" },
        { name: "Implementation Approval", status: "completed" },
        { name: "Execution", status: "completed" },
        { name: "Verification", status: "current" },
        { name: "Review", status: "waiting" },
        { name: "Commit", status: "waiting" },
    ],
});

for (const width of [320, 1280]) {
    test(`active workflow explains automatic status checks at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/api/v1/agent/workflows/workflow-running/implementation-request", route =>
            route.fulfill({ json: runningWorkflow }));
        await page.goto("/workflows/workflow-running");

        await expect(page.getByRole("heading", { name: "Review workflow", exact: true })).toBeVisible();
        await expect(page.getByText(
            "When work is running, Atlas checks this workflow every 5 seconds. Workflow actions pause while each check finishes.",
            { exact: true },
        )).toBeVisible();
        await expect(page.getByText(
            "Checking current workflow status. Approval and action buttons are unavailable until this check finishes.",
            { exact: true },
        )).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
