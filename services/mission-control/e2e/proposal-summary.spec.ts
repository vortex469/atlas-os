import type { ExecutionCandidate } from "../src/types/executionCandidates";
import { expect, test } from "./mission-control-fixtures";

const proposal: ExecutionCandidate = {
    id: `candidate-${"a".repeat(64)}`, effect_kind: "repository_change",
    source_recommendation_id: `recommendation-${"b".repeat(64)}`,
    source_subsystem: "orion", recommendation_class: "update-compose-stack",
    target_id: `repository/${"atlas-stack-".repeat(12)}`, target_type: "compose_stack",
    execution_category: "update", execution_intent: "update-compose-stack",
    status: "eligible", required_approval_level: "elevated",
    rationale: `Review the proposed stack update before planning. ${"context".repeat(60)}`,
    constraints: ["service_disruption"], evidence_ids: [`evidence-${"c".repeat(64)}`],
    compatibility_assessment_id: "assessment-1", compatibility_status: "compatible_with_warnings",
    relationship_ids: [], created_at: "2026-10-20T12:00:00Z", expires_at: null,
};

for (const width of [320, 390, 1280]) {
    for (const sample of [
        { name: "eligible", status: "eligible", expires_at: null, expiryLabel: "No expiry" },
        { name: "expired", status: "expired", expires_at: null, expiryLabel: "No expiry" },
        { name: "unverified expiry", status: "eligible", expires_at: "", expiryLabel: "Unverified expiry" },
    ]) {
        test(`${sample.name} proposal stays readable at ${width}px without sending decisions`, async ({ page, baseURL, rejectedMutationRequests }) => {
            const currentProposal = { ...proposal, status: sample.status, expires_at: sample.expires_at };
            await page.setViewportSize({ width, height: 844 });
            const origin = new URL(baseURL ?? "http://127.0.0.1:5173").origin;
            let reads = 0;
            await page.route("**/api/v1/execution-candidates**", async (route) => {
                const request = route.request(); const url = new URL(request.url());
                if (request.method() !== "GET" || url.origin !== origin) {
                    await route.fulfill({ status: 405, json: { detail: "Exact-origin reads only." } });
                    return;
                }
                reads += 1;
                if (url.pathname === "/api/v1/execution-candidates") {
                    await route.fulfill({ json: { candidates: [currentProposal], total: 1, limit: 25, offset: 0, has_more: false } });
                } else if (url.pathname === `/api/v1/execution-candidates/${proposal.id}`) {
                    await route.fulfill({ json: currentProposal });
                } else {
                    await route.fulfill({ status: 404, json: { detail: "Unknown synthetic proposal." } });
                }
            });
            await page.goto("/execution-candidates");
            const link = page.getByRole("link", { name: `Update Compose Stack for ${proposal.target_id}`, exact: true });
            await expect(link).toBeVisible();
            await expect(page.getByText(proposal.id, { exact: true })).toBeHidden();
            await expect(page.getByText("Compatible With Warnings", { exact: true })).toBeVisible();
            await expect(page.getByText("Elevated", { exact: true })).toBeVisible();
            await expect(page.getByText(sample.expiryLabel, { exact: true })).toBeVisible();
            const filterSummary = page.getByText("Filter proposals", { exact: true });
            await expect(filterSummary.locator("..")).not.toHaveAttribute("open");
            const initialReads = reads;
            await filterSummary.click();
            await expect(page.getByRole("form", { name: "Filter change proposals" })).toBeVisible();
            await filterSummary.click();
            expect(reads).toBe(initialReads);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
            if (sample.name === "eligible") await page.screenshot({ path: `/tmp/atlas-proposal-list-${width}.png`, fullPage: true });
            await link.click();
            await expect(page.getByRole("heading", { name: "Update Compose Stack", level: 1 })).toBeVisible();
            const planning = page.getByRole("button", { name: "Start planning", exact: true });
            if (sample.name === "eligible") await expect(planning).toBeEnabled();
            else await expect(planning).toBeDisabled();
            await expect(page.getByText("Compatible With Warnings", { exact: true })).toBeVisible();
            await expect(page.getByText("Elevated", { exact: true })).toBeVisible();
            await expect(page.getByText(sample.expiryLabel, { exact: true })).toBeVisible();
            await expect(page.getByText(proposal.constraints[0], { exact: true })).toBeVisible();
            const context = page.getByRole("region", { name: "Proposal review context", exact: true });
            await expect(context.getByText(proposal.rationale, { exact: true })).toBeVisible();
            const contextBox = await context.boundingBox();
            const planningBox = await page.getByRole("region", { name: "Plan this change", exact: true }).boundingBox();
            expect(contextBox!.y + contextBox!.height).toBeLessThanOrEqual(planningBox!.y);
            await expect(page.getByText(proposal.evidence_ids[0], { exact: true })).toBeHidden();
            const disclosure = page.locator("details").filter({ has: page.getByText("Technical details", { exact: true }) });
            await expect(disclosure).not.toHaveAttribute("open");
            await expect(page.getByText(proposal.id, { exact: true })).toBeHidden();
            const detailReads = reads;
            await disclosure.locator("summary").click();
            await expect(page.getByText(proposal.id, { exact: true })).toBeVisible();
            await expect(page.getByText(proposal.evidence_ids[0], { exact: true })).toBeVisible();
            expect(reads).toBe(detailReads);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
            await disclosure.locator("summary").click();
            if (sample.name === "eligible") {
                await page.evaluate(() => window.scrollTo(0, 0));
                await page.screenshot({ path: `/tmp/atlas-proposal-review-context-${width}.png`, fullPage: true });
            }
            expect(rejectedMutationRequests).toEqual([]);
        });
    }
}


test("failed proposal reads can recover while filters stay collapsed", async ({ page, baseURL, rejectedMutationRequests }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const origin = new URL(baseURL ?? "http://127.0.0.1:5173").origin;
    let reads = 0;
    await page.route("**/api/v1/execution-candidates*", async (route) => {
        const request = route.request();
        if (request.method() !== "GET" || new URL(request.url()).origin !== origin) {
            await route.fulfill({ status: 405 });
            return;
        }
        reads += 1;
        if (reads === 1) await route.fulfill({ status: 503, json: { detail: "Synthetic outage" } });
        else await route.fulfill({ json: { candidates: [proposal], total: 1, limit: 25, offset: 0, has_more: false } });
    });
    await page.goto("/execution-candidates");
    await expect(page.getByRole("alert")).toContainText("Change proposals unavailable");
    await expect(page.getByRole("form", { name: "Filter change proposals" })).toBeHidden();
    await page.getByRole("button", { name: "Try again", exact: true }).click();
    await expect(page.getByRole("link", { name: `Update Compose Stack for ${proposal.target_id}`, exact: true })).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
    expect(reads).toBe(2);
    expect(rejectedMutationRequests).toEqual([]);
});
