import { expect, test } from "./mission-control-fixtures";

const sessionId = "stale-workflow-planning-session";
const workflow = {
    candidate_planning_session_id: sessionId,
    candidate_id: "stale-proposal",
    candidate_fingerprint: "current-fingerprint",
    candidate_plan_id: "reviewed-plan",
    candidate_plan_fingerprint: "reviewed-plan-fingerprint",
    workflow_session_id: null,
    workflow_status: null,
    implementation_approval_request_id: null,
    conversion_status: "stale_before_workflow",
    core_revalidation_status: "stale",
    reason_codes: ["stale"],
    failure: { code: "candidate_stale", message: "Candidate changed" },
};

for (const width of [390, 1280]) {
    test(`explains a stale proposal clearly at ${width}px and keeps codes in details`, async ({ page, baseURL, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 844 });
        const expectedOrigin = new URL(baseURL ?? "http://127.0.0.1:5173").origin;
        let reads = 0;
        await page.route(`**/agent-api/candidate-planning/${sessionId}/workflow`, async (route) => {
            const request = route.request();
            if (request.method() !== "GET" || new URL(request.url()).origin !== expectedOrigin) {
                await route.fulfill({ status: 405, json: { detail: "Fixture permits exact-origin reads only." } });
                return;
            }
            reads += 1;
            await route.fulfill({ json: workflow });
        });

        await page.goto(`/candidate-planning/${sessionId}/workflow`);
        await expect(page.getByRole("heading", { name: "Workflow summary", exact: true })).toBeVisible();
        await expect(page.getByText("The proposal changed after this plan was created. Review the current proposal before planning again.", { exact: true })).toBeVisible();
        await expect(page.getByText("Needs review", { exact: true })).toBeVisible();
        await expect(page.getByText("stale", { exact: true })).toBeHidden();
        await expect(page.getByText("candidate_stale - Candidate changed", { exact: true })).toBeHidden();
        const details = page.getByText("Technical details", { exact: true });
        await expect(details.locator("..")).not.toHaveAttribute("open");
        await details.click();
        await expect(page.getByText("stale", { exact: true })).toBeVisible();
        await expect(page.getByText("candidate_stale - Candidate changed", { exact: true })).toBeVisible();
        expect(reads).toBe(1);
        expect(rejectedMutationRequests).toEqual([]);
        await expect(page.getByRole("button", { name: /approve|execute|prepare exact request/i })).toHaveCount(0);
    });
}
