import type { ExecutionCandidate } from "../src/types/executionCandidates";
import { expect, test } from "@playwright/test";
import { installMissionControlMocks } from "./mission-control-fixtures";

const proposal: ExecutionCandidate = {
    effect_kind: "repository_change",
    id: "proposal-planning-outcome",
    source_recommendation_id: "finding-planning-outcome",
    source_subsystem: "ace",
    recommendation_class: "maintenance",
    target_id: "fixture-service",
    target_type: "service",
    execution_category: "update",
    execution_intent: "update-compose-stack",
    status: "eligible",
    required_approval_level: "standard",
    rationale: "Review this fixture change.",
    constraints: [],
    evidence_ids: [],
    relationship_ids: [],
    created_at: "2026-10-26T00:00:00Z",
    expires_at: null,
};

for (const width of [320, 390, 1280]) {
    test(`explains a planning check failure at ${width}px and keeps diagnostic codes in details`, async ({ page, baseURL }) => {
        const mutations: string[] = [];
        await installMissionControlMocks(page, "available", mutations);
        await page.setViewportSize({ width, height: 900 });
        const origin = new URL(baseURL!).origin;
        await page.route(`**/api/v1/execution-candidates/${proposal.id}`, async route => {
            expect(route.request().method()).toBe("GET");
            expect(new URL(route.request().url()).origin).toBe(origin);
            await route.fulfill({ json: proposal });
        });
        let requests = 0;
        await page.route("**/agent-api/candidate-planning", async route => {
            expect(route.request().method()).toBe("POST");
            expect(new URL(route.request().url()).origin).toBe(origin);
            expect(route.request().postDataJSON()).toEqual({ candidate_id: proposal.id });
            requests += 1;
            await route.fulfill({ json: {
                candidate_id: proposal.id,
                session_id: null,
                status: "intake_rejected",
                planning_allowed: false,
                intake_status: "rejected",
                intake_reason_codes: [],
                candidate_fingerprint: null,
                unsupported_reason: null,
                plan: null,
                planning_failure: { code: "atlas_core_unavailable", message: "Core unavailable" },
            } });
        });

        await page.goto(`/execution-candidates/${proposal.id}`);
        await page.getByRole("button", { name: "Start planning", exact: true }).click();
        await expect(page.getByText("Atlas could not confirm that this proposal is still current. Choose Refresh proposal before trying again.", { exact: true })).toBeVisible();
        const details = page.locator("details").filter({ has: page.getByText("Planning details", { exact: true }) });
        await expect(details).not.toHaveAttribute("open");
        await expect(details.getByText(/atlas_core_unavailable/)).toBeHidden();
        await details.locator("summary").click();
        await expect(details.getByText(/atlas_core_unavailable/)).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(requests).toBe(1);
        expect(mutations).toEqual([`POST ${origin}/agent-api/candidate-planning`]);
    });
}
