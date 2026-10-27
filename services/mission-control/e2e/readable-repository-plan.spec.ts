import { expect, test } from '@playwright/test';
import { installMissionControlMocks } from './mission-control-fixtures';
import type { CandidatePlanApiResponse, CandidatePlanningResponse } from '../src/types/atlasAgent';

const id = 'readable-repository-plan';
const plan: CandidatePlanApiResponse = {
    identifier: 'plan-fixture', session_id: id, candidate_id: 'proposal-fixture', candidate_fingerprint: 'fingerprint-fixture',
    title: 'Readable saved plan', objective: 'Review a fixture change.', assumptions: [], constraints: [], proposed_steps: ['Review the file.'],
    likely_affected_components: [], likely_affected_files: ['compose.yaml'], verification_strategy: ['Check configuration.'],
    rollback_considerations: ['Restore the file.'], unresolved_questions: [], evidence_ids: [], created_at: '2026-01-01T00:00:00Z',
    repository_branch: 'fixture', repository_head: 'a'.repeat(40), revalidated_candidate_fingerprint: 'fingerprint-fixture',
};
const session: CandidatePlanningResponse = {
    session_id: id, candidate_id: plan.candidate_id, candidate_fingerprint: plan.candidate_fingerprint,
    status: 'plan_ready', planning_allowed: false, intake_status: 'accepted_for_planning', intake_reason_codes: [],
    unsupported_reason: null, planning_failure: null, plan,
};
for (const width of [320, 390, 1280]) for (const mode of ['initial', 'refresh', 'generated'] as const) {
    test(`unreadable repository plan ${mode} recovers through reads at ${width}px`, async ({ page, baseURL }) => {
        const mutations: string[] = [];
        await installMissionControlMocks(page, 'available', mutations);
        await page.setViewportSize({ width, height: 900 });
        let phase = mode === 'initial' ? 'bad' : 'initial';
        let reads = 0, posts = 0;
        const malformed = mode === 'initial' ? { ...plan, title: {} }
            : mode === 'refresh' ? { ...plan, verification_strategy: {} } : { ...plan, proposed_steps: [{}] };
        await page.route(`**/agent-api/candidate-planning/${id}`, route => {
            expect(route.request().method()).toBe('GET');
            reads += 1;
            const response = phase === 'bad' ? { ...session, plan: malformed }
                : mode === 'generated' && phase === 'initial' ? { ...session, status: 'ready_for_planning', planning_allowed: true, plan: null } : session;
            return route.fulfill({ json: response });
        });
        await page.route(`**/agent-api/candidate-planning/${id}/plan`, route => {
            expect(route.request().method()).toBe('POST');
            expect(route.request().postData()).toBeNull();
            posts += 1;
            return route.fulfill({ json: { ...session, planning_allowed: true, plan: malformed } });
        });
        await page.goto(`/candidate-planning/${id}`);
        if (mode === 'refresh') {
            await expect(page.getByRole('heading', { name: 'Readable saved plan', exact: true })).toBeVisible();
            phase = 'bad';
            await page.getByRole('button', { name: 'Refresh planning', exact: true }).click();
        } else if (mode === 'generated') await page.getByRole('button', { name: 'Generate Plan', exact: true }).click();
        await expect(page.getByRole('alert')).toContainText('The repository plan response is incomplete or unreadable.');
        await expect(page.getByText('Generate a plan to review. This does not apply changes or grant approval.', { exact: true })).toHaveCount(0);
        await expect(page.getByText('Plan is ready.', { exact: true })).toHaveCount(0);
        await expect(page.getByRole('heading', { name: 'Readable saved plan', exact: true })).toHaveCount(0);
        await expect(page.getByRole('button', { name: 'Create Workflow', exact: true })).toHaveCount(0);
        if (width !== 320 && mode !== 'refresh') {
            await page.evaluate(() => scrollTo(0, 0));
            await page.screenshot({ path: `/tmp/atlas-readable-repository-plan-${mode}-${width}.png`, fullPage: true });
        }
        phase = 'recovered';
        await page.getByRole('button', { name: mode === 'generated' ? 'Check saved planning' : 'Try again', exact: true }).click();
        await expect(page.getByRole('heading', { name: 'Readable saved plan', exact: true })).toBeVisible();
        await expect(page.getByText('Check configuration.', { exact: true })).toBeVisible();
        await expect(page.getByText('Restore the file.', { exact: true })).toBeVisible();
        await expect(page.getByRole('alert')).toHaveCount(0);
        await expect(page.getByRole('button', { name: 'Create Workflow', exact: true })).toHaveCount(0);
        const initialReads = baseURL!.includes(':4173') ? 1 : 2;
        expect(reads).toBe(initialReads + (mode === 'refresh' ? 2 : 1));
        expect(posts).toBe(mode === 'generated' ? 1 : 0);
        expect(mutations).toEqual(mode === 'generated' ? [`POST ${baseURL}/agent-api/candidate-planning/${id}/plan`] : []);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
}
