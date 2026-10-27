import { expect, test } from '@playwright/test';
import { installRepositoryJourney, journey, workflowDetail } from './repository-journey-fixture';

for (const width of [320, 390, 1280]) for (const approved of [false, true]) for (const kind of ['missing', 'malformed'] as const) {
    test(`${kind} ${approved ? 'approved' : 'pending'} commit request recovers through reads at ${width}px`, async ({page, baseURL}) => {
        const fixture = await installRepositoryJourney(page, true, {baseURL});
        await page.setViewportSize({width, height: 900});
        const saved = workflowDetail('commit', approved);
        let reads = 0;
        await page.route(`**/agent-api/api/v1/agent/workflows/${journey.workflow}/implementation-request`, route => {
            expect(route.request().method()).toBe('GET');
            reads += 1;
            return route.fulfill({json: reads > 1 ? saved : {...saved, commit_request: kind === 'missing' ? null : {...saved.commit_request, reviewed_files: 'compose.yaml'}}});
        });
        await page.goto(`/workflows/${journey.workflow}`);
        await expect(page.getByRole('button', {name: 'Check commit request', exact: true})).toBeEnabled();
        await expect(page.getByRole('button', {name: /Approve Commit|Reject Commit|Resume Approved Commit/})).toHaveCount(0);
        const approval = page.getByRole('region', {name: 'Commit approval', exact: true});
        await expect(approval).toContainText(approved ? 'Commit approval is recorded.' : 'Commit approval is paused');
        if (width === 390 && !approved) await page.getByRole('region', {name: 'Commit Request', exact: true}).screenshot({path: `/tmp/atlas-unreadable-commit-${kind}-390.png`});
        expect(fixture.writes).toEqual([]);
        await page.getByRole('button', {name: 'Check commit request', exact: true}).click();
        await expect(page.getByRole('button', {name: approved ? 'Resume Approved Commit' : 'Approve Commit', exact: true})).toBeEnabled();
        await expect(page.getByRole('button', {name: 'Check commit request', exact: true})).toHaveCount(0);
        expect(reads).toBe(2);
        expect(fixture.writes).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
}
