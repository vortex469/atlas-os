import { expect, test } from '@playwright/test';
import { installRepositoryJourney, journey, workflowDetail } from './repository-journey-fixture';

const outcomes = [
    {status: 'failed', message: 'Execution failed.', tone: 'text-red-200'},
    {status: 'timed_out', message: 'Execution timed out.', tone: 'text-red-200'},
    {status: 'launch_failed', message: 'Execution could not start.', tone: 'text-red-200'},
    {status: 'unknown', message: 'Worker outcome unknown. Check the original result; do not resubmit.', tone: 'text-amber-200'},
    {status: 'future_status', message: 'Execution status is not recognized. Refresh to check its status.', tone: 'text-amber-200'},
    {status: 'succeeded', message: 'Execution complete.', tone: 'text-emerald-200'},
];
for (const width of [320, 390, 1280]) {
    for (const outcome of outcomes) test(`execution ${outcome.status} stays consistent at ${width}px`, async ({page, baseURL}) => {
        const fixture = await installRepositoryJourney(page, true, {baseURL});
        await page.setViewportSize({width, height: 900});
        const saved = workflowDetail('verification', false);
        await page.route(`**/agent-api/api/v1/agent/workflows/${journey.workflow}/implementation-request`, route => {
            expect(route.request().method()).toBe('GET');
            return route.fulfill({json: {...saved, workflow_state: outcome.status === 'succeeded' ? 'awaiting_verification_approval' : 'blocked',
                timeline: saved.timeline.map(stage => stage.name === 'Execution' ? {...stage, status: outcome.status === 'succeeded' ? 'completed' : 'failed'} : stage),
                execution: {...saved.execution, execution_status: outcome.status, result: outcome.status}}});
        });
        await page.goto(`/workflows/${journey.workflow}`);
        const execution = page.getByRole('region', {name: 'Execution', exact: true});
        await expect(page.getByText(outcome.message, {exact: true})).toHaveCount(2);
        await expect(execution.locator('p[role="status"]')).toHaveClass(new RegExp(outcome.tone));
        if (outcome.status !== 'succeeded') await expect(page.getByText('Execution complete.', {exact: true})).toHaveCount(0);
        await page.getByRole('button', {name: 'Refresh', exact: true}).click();
        await expect(page.getByText(outcome.message, {exact: true})).toHaveCount(2);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        if (width === 390 && ['unknown', 'timed_out'].includes(outcome.status)) await page.screenshot({path: `/tmp/atlas-execution-outcome-${outcome.status}-390.png`, fullPage: true});
        expect(fixture.writes).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
    });
    test(`approved request without a result explains separate resume at ${width}px`, async ({page, baseURL}) => {
        const fixture = await installRepositoryJourney(page, true, {baseURL});
        await page.setViewportSize({width, height: 900});
        const saved = workflowDetail('implementation', true);
        await page.route(`**/agent-api/api/v1/agent/workflows/${journey.workflow}/implementation-request`, route => { expect(route.request().method()).toBe('GET'); return route.fulfill({json: saved}); });
        await page.goto(`/workflows/${journey.workflow}`);
        await expect(page.getByText('Implementation approved. Waiting for a separate resume.', {exact: true})).toHaveCount(2);
        await expect(page.getByText('Execution unavailable.', {exact: true})).toHaveCount(0);
        await expect(page.getByRole('button', {name: 'Resume Approved Implementation', exact: true})).toBeEnabled();
        expect(fixture.writes).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
    });
}
