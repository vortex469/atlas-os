import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { installMissionControlMocks } from "./mission-control-fixtures";
import type { ExecutionCandidate } from "../src/types/executionCandidates";

const proposal: ExecutionCandidate = {
    id: "candidate-recovery", effect_kind: "repository_change", source_recommendation_id: "recommendation-fixture",
    source_subsystem: "ace", recommendation_class: "maintenance", target_id: "fixture-service", target_type: "service",
    execution_category: "update", execution_intent: "update-compose-stack", status: "eligible", required_approval_level: "standard",
    rationale: "Original proposal", constraints: [], evidence_ids: [], relationship_ids: [], created_at: "2026-10-27T00:00:00Z", expires_at: null,
};
const path = `/execution-candidates/${proposal.id}`;
async function setup(page: Page, width: number, mutations: string[]) {
    await installMissionControlMocks(page, "available", mutations);
    await page.setViewportSize({ width, height: 900 });
}
for (const width of [320, 390, 1280]) {
    for (const failure of ["missing", "unavailable", "foreign"] as const) test(`proposal detail retries ${failure} at ${width}px`, async ({ page, baseURL }) => {
        const mutations: string[] = [];
        await setup(page, width, mutations);
        let failed = true;
        let finish!: () => void;
        const pending = new Promise<void>(resolve => { finish = resolve; });
        let retryReads = 0;
        await page.route(`**/api/v1${path}`, async route => {
            expect(route.request().method()).toBe("GET");
            expect(new URL(route.request().url()).origin).toBe(new URL(baseURL!).origin);
            if (failed) return route.fulfill(failure === "foreign" ? { json: { ...proposal, id: "foreign-proposal", rationale: "FOREIGN-PROPOSAL-CANARY" } }
                : { status: failure === "missing" ? 404 : 503, json: { detail: "fixture read unavailable" } });
            retryReads += 1;
            await pending;
            return route.fulfill({ json: proposal });
        });
        await page.goto(path);
        const retry = page.getByRole("button", { name: "Try again", exact: true });
        await expect(retry).toBeVisible();
        await expect(page.getByRole("button", { name: "Start planning", exact: true })).toHaveCount(0);
        failed = false;
        await retry.click();
        await expect.poll(() => retryReads).toBe(1);
        await expect(page.getByRole("status")).toHaveText("Loading change proposal…");
        await expect(page.getByRole("link", { name: "← Change proposals", exact: true })).toBeVisible();
        await expect(page.getByRole("button", { name: "Start planning", exact: true })).toHaveCount(0);
        finish();
        await expect(page.getByRole("button", { name: "Start planning", exact: true })).toBeEnabled();
        await expect(page.getByText("Original proposal", { exact: true })).toBeVisible();
        await expect(page.getByText("FOREIGN-PROPOSAL-CANARY")).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(mutations).toEqual([]);
    });
    test(`proposal refresh rechecks eligibility at ${width}px without planning`, async ({ page, baseURL }) => {
        const mutations: string[] = [];
        await setup(page, width, mutations);
        let updated = false;
        await page.route(`**/api/v1${path}`, route => {
            expect(route.request().method()).toBe("GET");
            expect(new URL(route.request().url()).origin).toBe(new URL(baseURL!).origin);
            return route.fulfill({ json: updated ? { ...proposal, status: "expired", rationale: "Updated proposal" } : proposal });
        });
        await page.goto(path);
        await expect(page.getByRole("button", { name: "Start planning", exact: true })).toBeEnabled();
        updated = true;
        await page.getByRole("button", { name: "Refresh proposal", exact: true }).click();
        await expect(page.getByText("Updated proposal", { exact: true })).toBeVisible();
        await expect(page.getByRole("button", { name: "Start planning", exact: true })).toBeDisabled();
        await expect(page.getByText("Original proposal", { exact: true })).toHaveCount(0);
        expect(mutations).toEqual([]);
    });
    test(`stale planning recovers by reading at ${width}px without resubmission`, async ({ page, baseURL }) => {
        const mutations: string[] = [];
        await setup(page, width, mutations);
        let updated = false, reads = 0;
        let finish!: () => void;
        const pending = new Promise<void>(resolve => { finish = resolve; });
        await page.route(`**/api/v1${path}`, route => {
            expect(route.request().method()).toBe("GET");
            reads += 1;
            return route.fulfill({ json: updated ? { ...proposal, status: "expired", rationale: "Updated proposal" } : proposal });
        });
        await page.route("**/agent-api/candidate-planning", async route => {
            expect(route.request().method()).toBe("POST");
            expect(new URL(route.request().url()).origin).toBe(new URL(baseURL!).origin);
            expect(route.request().postDataJSON()).toEqual({ candidate_id: proposal.id });
            await pending;
            return route.fulfill({ json: { candidate_id: proposal.id, session_id: null, status: "stale_before_planning", planning_allowed: false,
                intake_status: "stale", intake_reason_codes: [], candidate_fingerprint: null, unsupported_reason: null, plan: null,
                planning_failure: { code: "candidate_stale", message: "The proposal changed" } } });
        });
        await page.goto(path);
        await page.getByRole("button", { name: "Start planning", exact: true }).click();
        const refresh = page.getByRole("button", { name: "Refresh proposal", exact: true });
        await expect(refresh).toBeDisabled();
        finish();
        const message = page.getByText("This proposal changed or expired. Choose Refresh proposal to check its latest details.", { exact: true });
        await expect(message).toBeVisible();
        const before = reads;
        updated = true;
        await refresh.click();
        await expect(page.getByText("Updated proposal", { exact: true })).toBeVisible();
        await expect(message).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Start planning", exact: true })).toBeDisabled();
        expect(reads).toBe(before + 1);
        expect(mutations).toEqual([`POST ${new URL(baseURL!).origin}/agent-api/candidate-planning`]);
    });
}
