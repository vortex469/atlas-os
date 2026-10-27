import { expect, test } from '@playwright/test';
import { installMissionControlMocks } from './mission-control-fixtures';

const proposal = {
    id: 'candidate-readable-result', effect_kind: 'repository_change', source_recommendation_id: 'finding-fixture',
    source_subsystem: 'ace', recommendation_class: 'maintenance', target_id: 'fixture-service', target_type: 'service',
    execution_category: 'update', execution_intent: 'update-compose-stack', status: 'eligible', required_approval_level: 'standard',
    rationale: 'Review this fixture change.', constraints: [], evidence_ids: [], relationship_ids: [],
    created_at: '2026-01-01T00:00:00Z', expires_at: null,
};
const proposalPath = `/execution-candidates/${proposal.id}`;
for (const width of [320, 390, 1280]) {
    for (const malformed of ['status', 'reasons', 'reference'] as const) {
        test(`unreadable planning ${malformed} recovers without resubmission at ${width}px`, async ({ page, baseURL }) => {
            const mutations: string[] = [];
            await installMissionControlMocks(page, 'available', mutations);
            await page.setViewportSize({ width, height: 900 });
            let proposalReads = 0, sessionReads = 0, posts = 0;
            await page.route(`**/api/v1${proposalPath}`, route => {
                expect(route.request().method()).toBe('GET');
                proposalReads += 1;
                return route.fulfill({ json: proposal });
            });
            await page.route('**/agent-api/candidate-planning', route => {
                expect(route.request().method()).toBe('POST');
                expect(route.request().postDataJSON()).toEqual({ candidate_id: proposal.id });
                posts += 1;
                return route.fulfill({ json: {
                    candidate_id: proposal.id, session_id: malformed === 'reference' ? '..' : 'candidate-plan-readable',
                    status: malformed === 'status' ? {} : 'ready_for_planning', planning_allowed: true,
                    intake_status: 'accepted_for_planning', intake_reason_codes: malformed === 'reasons' ? null : [],
                    planning_failure: null, unsupported_reason: null,
                } });
            });
            await page.route('**/agent-api/candidate-planning/candidate-plan-readable', route => {
                expect(route.request().method()).toBe('GET');
                sessionReads += 1;
                return route.fulfill({ status: 404, json: { detail: 'No saved session in this fixture.' } });
            });
            await page.goto(proposalPath);
            await page.getByRole('button', { name: 'Start planning', exact: true }).click();
            await expect(page.getByRole('alert')).toContainText('The planning response could not be read. A session may have been saved.');
            const review = page.getByRole('link', { name: 'Review planning details', exact: true });
            if (malformed === 'reference') {
                await expect(review).toHaveCount(0);
                await page.getByRole('button', { name: 'Refresh proposal', exact: true }).click();
                await expect(page.getByRole('button', { name: 'Start planning', exact: true })).toBeEnabled();
                expect(proposalReads).toBe(baseURL!.includes(':4173') ? 2 : 3);
            } else {
                await expect(review).toHaveAttribute('href', '/candidate-planning/candidate-plan-readable');
                expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
                await review.click();
                await expect(page.getByRole('heading', { name: 'Planning session not found', exact: true })).toBeVisible();
                expect(sessionReads).toBe(baseURL!.includes(':4173') ? 1 : 2);
                expect(proposalReads).toBe(baseURL!.includes(':4173') ? 1 : 2);
            }
            expect(posts).toBe(1);
            expect(mutations).toEqual([`POST ${baseURL}/agent-api/candidate-planning`]);
        });
    }
}
