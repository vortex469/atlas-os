import { expect, test } from '@playwright/test';
import { installMissionControlMocks } from './mission-control-fixtures';
import type { CandidatePlanApiResponse, CandidatePlanningResponse } from '../src/types/atlasAgent';

const sessionId = 'planning-read-recovery';
const plan: CandidatePlanApiResponse = {
    identifier: 'saved-plan', session_id: sessionId, candidate_id: 'proposal-read-recovery', candidate_fingerprint: 'candidate-fingerprint',
    title: 'Saved fixture plan', objective: 'Review the saved plan.', assumptions: [], constraints: [], proposed_steps: ['Review the change.'],
    likely_affected_components: [], likely_affected_files: [], verification_strategy: [], rollback_considerations: [], unresolved_questions: [],
    evidence_ids: [], created_at: '2026-01-01T00:00:00Z', repository_branch: 'fixture-branch', repository_head: 'a'.repeat(40),
    revalidated_candidate_fingerprint: 'candidate-fingerprint',
};
const session: CandidatePlanningResponse = {
    session_id: sessionId, candidate_id: plan.candidate_id, candidate_fingerprint: plan.candidate_fingerprint,
    status: 'ready_for_planning', planning_allowed: true, intake_status: 'accepted_for_planning', intake_reason_codes: [],
    unsupported_reason: null, planning_failure: null, plan: null,
};
for (const width of [320, 390, 1280]) for (const mode of ['read', 'plan', 'workflow'] as const) {
    test(`planning ${mode} recovery only reloads saved information at ${width}px`, async ({ page, baseURL }) => {
        const mutations: string[] = [];
        await installMissionControlMocks(page, 'available', mutations);
        await page.setViewportSize({ width, height: 900 });
        let refreshed = false, reads = 0, posts = 0;
        let finishRead!: () => void, finishAction!: () => void;
        const pendingRead = new Promise<void>(resolve => { finishRead = resolve; });
        const pendingAction = new Promise<void>(resolve => { finishAction = resolve; });
        await page.route(`**/agent-api/candidate-planning/${sessionId}`, async route => {
            expect(route.request().method()).toBe('GET');
            reads += 1;
            if (refreshed) {
                await pendingRead;
                return route.fulfill({ json: { ...session, status: mode === 'workflow' ? 'workflow_created' : 'plan_ready', planning_allowed: false,
                    plan, workflow_session_id: mode === 'workflow' ? 'saved-workflow' : null } });
            }
            if (mode === 'read') return route.fulfill({ status: 503, json: { detail: 'Fixture read unavailable.' } });
            return route.fulfill({ json: mode === 'workflow' ? { ...session, status: 'plan_ready', plan } : session });
        });
        const actionPath = `/agent-api/candidate-planning/${sessionId}/${mode}`;
        if (mode !== 'read') await page.route(`**${actionPath}`, async route => {
            expect(route.request().method()).toBe('POST');
            expect(route.request().postData()).toBeNull();
            posts += 1;
            await pendingAction;
            return route.abort('failed');
        });
        await page.goto(`/candidate-planning/${sessionId}`);
        if (mode !== 'read') {
            await page.getByRole('button', { name: mode === 'plan' ? 'Generate Plan' : 'Create Workflow', exact: true }).click();
            await expect(page.getByRole('button', { name: 'Refresh planning', exact: true })).toBeDisabled();
            expect(reads).toBe(baseURL!.includes(':4173') ? 1 : 2);
            finishAction();
            await expect(page.getByRole('alert')).toContainText(mode === 'plan' ? 'Plan result unavailable' : 'Workflow result unavailable');
            await expect(page.getByRole('alert')).toContainText('This only reloads saved information.');
        }
        if (mode === 'read') {
            await expect(page.getByRole('heading', { name: 'Planning unavailable', exact: true })).toBeVisible();
            await expect(page.getByRole('alert')).toContainText('Fixture read unavailable.');
            expect(reads).toBe(baseURL!.includes(':4173') ? 1 : 2);
        }
        refreshed = true;
        await page.getByRole('button', { name: mode === 'read' ? 'Try again' : 'Check saved planning', exact: true }).click();
        await expect(page.getByRole('status')).toHaveText('Loading planning session…');
        await expect(page.getByRole('link', { name: '← Change proposals', exact: true })).toBeVisible();
        for (const name of ['Generate Plan', 'Create Workflow', 'Refresh planning']) await expect(page.getByRole('button', { name, exact: true })).toHaveCount(0);
        await expect(page.getByRole('heading', { name: 'Saved fixture plan', exact: true })).toHaveCount(0);
        finishRead();
        if (mode === 'workflow') await expect(page.getByRole('link', { name: 'Open existing workflow', exact: true })).toHaveAttribute('href', '/workflows/saved-workflow');
        else await expect(page.getByRole('heading', { name: 'Saved fixture plan', exact: true })).toBeVisible();
        if (mode !== 'workflow') {
            await expect(page.getByRole('heading', { name: 'Review saved plan', exact: true })).toBeVisible();
            await expect(page.getByRole('heading', { name: 'Saved plan', exact: true, level: 2 })).toBeVisible();
            await expect(page.getByRole('heading', { name: 'Workflow creation unavailable', exact: true })).toBeVisible();
            await expect(page.getByText('Creating a workflow is not available for this session. You can review this plan and refresh planning to check the latest status.', { exact: true })).toBeVisible();
            await expect(page.getByRole('button', { name: 'Create Workflow', exact: true })).toHaveCount(0);
        }
        await expect(page.getByRole('button', { name: 'Refresh planning', exact: true })).toBeEnabled();
        await expect(page.getByRole('alert')).toHaveCount(0);
        expect(reads).toBe(baseURL!.includes(':4173') ? 2 : 3);
        expect(posts).toBe(mode === 'read' ? 0 : 1);
        expect(mutations).toEqual(mode === 'read' ? [] : [`POST ${baseURL}${actionPath}`]);
        const references = page.getByText('Plan references', { exact: true });
        await expect(references.locator('..')).not.toHaveAttribute('open');
        await expect(page.getByText('Branch: fixture-branch', { exact: true })).toBeHidden();
        await expect(page.getByText('No evidence IDs listed.', { exact: true })).toBeHidden();
        for (const name of ['Planning assumptions', 'Constraints', 'Proposed steps', 'Affected files', 'Verification strategy', 'Rollback considerations', 'Unresolved questions']) {
            await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
        }
        await references.focus();
        await page.keyboard.press('Enter');
        await expect(page.getByText('Branch: fixture-branch', { exact: true })).toBeVisible();
        await expect(page.getByText('No evidence IDs listed.', { exact: true })).toBeVisible();
        const panelBounds = await page.getByRole('heading', { name: 'Affected repository', exact: true }).evaluate(heading => {
            const panel = heading.closest('section')!;
            const bounds = panel.getBoundingClientRect();
            return { left: bounds.left, right: bounds.right, fits: panel.scrollWidth <= panel.clientWidth };
        });
        expect(panelBounds.left).toBeGreaterThanOrEqual(0);
        expect(panelBounds.right).toBeLessThanOrEqual(width);
        expect(panelBounds.fits).toBe(true);
        await page.keyboard.press('Enter');
        await expect(page.getByText('Branch: fixture-branch', { exact: true })).toBeHidden();
        expect(reads).toBe(baseURL!.includes(':4173') ? 2 : 3);
        expect(posts).toBe(mode === 'read' ? 0 : 1);
        expect(mutations).toEqual(mode === 'read' ? [] : [`POST ${baseURL}${actionPath}`]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        if (width !== 320 && mode === 'plan') {
            await page.evaluate(() => scrollTo(0, 0));
            await page.screenshot({ path: `/tmp/atlas-planning-read-recovery-${width}.png`, fullPage: true });
        }
    });
}
