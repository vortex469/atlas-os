import { expect, test } from '@playwright/test';
import { completedAudit, installRepositoryJourney, journey } from './repository-journey-fixture';

for (const width of [320, 390, 1280]) for (const mode of ['completed', 'blocked', 'invalid', 'missing'] as const) {
    test(`compact ${mode} workflow history at ${width}px preserves facts and warnings`, async ({page, baseURL}) => {
        const fixture = await installRepositoryJourney(page, true, {baseURL});
        await page.setViewportSize({width, height: 1000});
        const saved = completedAudit();
        if (mode === 'blocked') { saved.workflow_state = 'blocked'; saved.blocked_reason = 'Recorded workflow paused for review.'; }
        if (mode === 'invalid') saved.validation = {valid: false, failure_code: null, failure_stage: null};
        if (mode === 'missing') {
            saved.validation = {valid: false, failure_code: 'missing_implementation_request', failure_stage: 'implementation'};
            saved.timeline = saved.timeline.map(stage => stage.name === 'implementation' ? {...stage, status: 'missing'} : stage);
            saved.implementation.implementation_request_id = null;
        }
        await page.route(`**/agent-api/api/v1/agent/workflows/${journey.workflow}/audit`, route => {
            expect(route.request().method()).toBe('GET');
            return route.fulfill({json: saved});
        });
        await page.goto(`/workflows/${journey.workflow}/audit`);
        await expect(page.getByRole('heading', {name: 'Workflow history', exact: true})).toBeVisible();
        const overview = page.getByRole('region', {name: 'Overview', exact: true});
        await expect(overview.getByText(journey.commit, {exact: true})).toBeVisible();
        await expect(overview.getByText(journey.workflow, {exact: true})).not.toBeVisible();
        if (mode === 'blocked') await expect(overview.getByText(saved.blocked_reason!, {exact: true})).toBeVisible();
        if (mode === 'invalid') await expect(overview.getByRole('alert')).toContainText('Audit validation failed.');
        if (mode === 'missing') {
            const alert = page.getByRole('region', {name: 'Overview', exact: true}).getByRole('alert');
            await expect(alert).toContainText('The implementation request is missing.');
            await expect(alert.getByText('Audit code: missing_implementation_request', {exact: true})).toBeHidden();
            await alert.getByText('Technical details', {exact: true}).click();
            await expect(alert.getByText('Audit code: missing_implementation_request', {exact: true})).toBeVisible();
            await expect(page.getByRole('region', {name: 'Implementation Request', exact: true}).getByRole('alert')).toContainText('Required artifact is missing.');
        }
        const candidate = page.getByRole('region', {name: 'Candidate', exact: true});
        await expect(candidate.getByText(journey.candidate, {exact: true})).not.toBeVisible();
        const toggle = candidate.locator('summary');
        await toggle.focus(); await page.keyboard.press('Enter');
        await expect(candidate.getByText(journey.candidate, {exact: true})).toBeVisible();
        await page.keyboard.press('Enter');
        const metadata = overview.locator('summary', {hasText: 'Record details'});
        await metadata.focus(); await page.keyboard.press('Enter');
        await expect(overview.getByText(journey.workflow, {exact: true})).toBeVisible();
        await page.keyboard.press('Enter');
        await page.getByRole('heading', {name: 'Stage status', exact: true}).click();
        await expect(page.getByRole('region', {name: 'Stage status', exact: true}).getByRole('listitem')).toHaveCount(10);
        await page.getByRole('heading', {name: 'Stage status', exact: true}).click();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        if (mode === 'completed' && width !== 320) { await page.evaluate(() => scrollTo(0,0)); await page.screenshot({path: `/tmp/atlas-workflow-history-${width}.png`}); }
        expect(fixture.writes).toEqual([]); expect(fixture.unexpected).toEqual([]);
    });
}
for (const width of [320, 390, 1280]) test(`maintenance history announces failed validation without a code at ${width}px`, async ({page, baseURL}) => {
    const fixture = await installRepositoryJourney(page, true, {maintenance: true, baseURL});
    await page.setViewportSize({width, height: 900});
    const saved = {...completedAudit(), effect_kind: 'operational_action', validation: {valid: false, failure_code: null, failure_stage: null}};
    await page.route(`**/agent-api/api/v1/agent/workflows/${journey.workflow}/audit`, route => {
        expect(route.request().method()).toBe('GET'); return route.fulfill({json: saved});
    });
    await page.goto(`/workflows/${journey.workflow}/audit`);
    await expect(page.getByRole('region', {name: 'Audit validation', exact: true}).getByRole('alert')).toContainText('Audit validation failed.');
    expect(fixture.writes).toEqual([]); expect(fixture.unexpected).toEqual([]);
});
