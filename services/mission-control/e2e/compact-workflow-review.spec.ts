import { expect, test } from '@playwright/test';
import { installRepositoryJourney, journey, maintenanceWorkflow, workflowDetail } from './repository-journey-fixture';
import { operationalActionRequest } from '../src/test/operationalPlanning';

for (const width of [320, 390, 1280]) for (const mode of ['repository', 'approved', 'maintenance', 'verification', 'commit'] as const) {
    test(`compact ${mode} workflow review at ${width}px retains facts and separate actions`, async ({page, baseURL}) => {
        const maintenance = mode === 'maintenance';
        const later = mode === 'verification' || mode === 'commit';
        const fixture = await installRepositoryJourney(page, true, {maintenance, baseURL});
        await page.setViewportSize({width, height: 1000});
        const saved = maintenance ? maintenanceWorkflow('implementation', false, operationalActionRequest({request_id: 'action-request-browser-journey'})) : workflowDetail(later ? mode : 'implementation', mode === 'approved');
        await page.route(`**/agent-api/api/v1/agent/workflows/${journey.workflow}/implementation-request`, route => {
            expect(route.request().method()).toBe('GET');
            return route.fulfill({json: saved});
        });
        await page.goto(`/workflows/${journey.workflow}`);
        await expect(page.getByRole('heading', {name: maintenance ? 'Review maintenance' : 'Review repository change', exact: true})).toBeVisible();
        if (maintenance) {
            const lifecycle = page.getByRole('region', {name: 'Operational lifecycle', exact: true});
            await expect(lifecycle.getByRole('heading', {name: 'Agent-only lifecycle', exact: true})).toBeVisible();
            const technical = lifecycle.getByText('Technical details', {exact: true});
            await expect(lifecycle.getByText(journey.workflow, {exact: true})).toBeHidden();
            await technical.focus(); await page.keyboard.press('Enter');
            await expect(lifecycle.getByText(journey.workflow, {exact: true})).toBeVisible();
            await page.keyboard.press('Enter');
        }
        const summary = page.getByRole('region', {name: 'Workflow summary', exact: true});
        await expect(summary.getByText(journey.workflow, {exact: true})).not.toBeVisible();
        const approvalLabel = maintenance ? 'Exact action' : mode === 'verification' ? 'Verification' : mode === 'commit' ? 'Commit' : 'Implementation';
        await expect(summary.getByText(`${approvalLabel} approval status: ${mode === 'approved' ? 'Approved' : 'Pending'}`, {exact: true})).toBeVisible();
        if (!later) {
            const request = page.getByRole('region', {name: maintenance ? 'Exact action request' : 'Implementation request', exact: true});
            expect(await request.evaluate(el => el.nextElementSibling?.getAttribute('aria-labelledby'))).toBe('approval-controls-heading');
            if (!maintenance) {
                const decision = page.getByRole('region', {name: 'Implementation approval', exact: true});
                expect((await decision.boundingBox())!.y).toBeLessThan((await page.locator('summary', {hasText: 'Verification details'}).boundingBox())!.y);
            }
        } else {
            await expect(page.getByRole('region', {name: mode === 'verification' ? 'Verification Plan' : 'Commit Request', exact: true})).toBeVisible();
            const history = page.locator('summary', {hasText: 'Implementation review'});
            await history.focus(); await page.keyboard.press('Enter');
            await expect(page.getByRole('region', {name: 'Implementation request', exact: true})).toBeVisible();
            await page.keyboard.press('Enter');
        }
        const action = mode === 'approved' ? 'Resume Approved Implementation' : maintenance ? 'Approve Exact Action' : mode === 'verification' ? 'Approve Verification' : mode === 'commit' ? 'Approve Commit' : 'Approve Implementation';
        await expect(page.getByRole('button', {name: action, exact: true})).toBeEnabled();
        const details = summary.locator('summary', {hasText: 'Workflow details'});
        await details.focus(); await page.keyboard.press('Enter');
        await expect(summary.getByText(journey.workflow, {exact: true})).toBeVisible();
        await page.keyboard.press('Enter');
        const stages = page.locator('summary', {hasText: 'Execution stages'});
        await stages.focus(); await page.keyboard.press('Enter');
        await expect(page.getByRole('list', {name: 'Authoritative execution stages', exact: true})).toBeVisible();
        await page.keyboard.press('Enter');
        if (!maintenance && !later) {
            const request = page.getByRole('region', {name: 'Implementation request', exact: true});
            const technical = request.locator('summary', {hasText: 'Request details'});
            await technical.focus(); await page.keyboard.press('Enter');
            await expect(request.getByText(saved.implementation_request!.immutable_request_id, {exact: true})).toBeVisible();
            await page.keyboard.press('Enter');
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        if (mode === 'repository' && width !== 320) { await page.evaluate(() => scrollTo(0, 0)); await page.screenshot({path: `/tmp/atlas-compact-workflow-${width}.png`}); }
        expect(fixture.writes).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
    });
}
