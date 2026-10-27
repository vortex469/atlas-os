import { expect, test } from './mission-control-fixtures';

for (const width of [320, 390, 1280]) for (const mode of ['loaded', 'empty', 'filtered'] as const) {
    test(`retained workflow ${mode} results stay qualified at ${width}px until recovery`, async ({page, rejectedMutationRequests}) => {
        await page.setViewportSize({width, height: 900});
        let phase = 'initial';
        let releaseFailure!: () => void;
        let releaseRecovery!: () => void;
        const failureGate = new Promise<void>(resolve => {releaseFailure = resolve;});
        const recoveryGate = new Promise<void>(resolve => {releaseRecovery = resolve;});
        const reads: string[] = [];
        const result = (latest: boolean) => ({
            items: mode === 'loaded' ? [{workflow_id: 'workflow-browser-baseline', workflow_source: 'candidate',
                workflow_state: latest ? 'completed' : 'awaiting_implementation_approval', effect_kind: 'repository_change',
                execution_intent: 'update-compose-stack', candidate_id: 'saved-candidate', planning_session_id: 'saved-plan',
                repository: '/fixture/repository', target_id: 'fixture-stack', last_result_summary: latest ? 'Latest workflow result' : 'Last recorded result', timeline: []}] : [],
            total: mode === 'loaded' ? 1 : 0, limit: 10, offset: 0,
            state_counts: mode === 'loaded' ? {[latest ? 'completed' : 'awaiting_implementation_approval']: 1} : {},
        });
        await page.route('**/agent-api/api/v1/agent/workflows?**', async route => {
            expect(route.request().method()).toBe('GET');
            reads.push(route.request().url());
            if (phase === 'failure') {await failureGate; await route.fulfill({status: 503, json: {detail: 'Fixture refresh unavailable'}}); return;}
            if (phase === 'recovery') {await recoveryGate; await route.fulfill({json: result(true)}); return;}
            await route.fulfill({json: result(false)});
        });
        await page.goto('/workflows');
        await expect(page.getByRole('heading', {name: 'Totals for this search', exact: true})).toBeVisible();
        if (mode === 'filtered') {
            await page.getByLabel('Workflow ID search', {exact: true}).fill('missing');
            await page.getByRole('button', {name: 'Apply filters', exact: true}).click();
            await expect(page.getByText('No workflows match the current filters.', {exact: true})).toBeVisible();
        }
        phase = 'failure';
        await page.getByRole('button', {name: 'Refresh', exact: true}).click();
        const retainedHeading = page.getByRole('heading', {name: 'Last loaded totals for this search', exact: true});
        await expect(retainedHeading).toBeVisible();
        await expect(page.getByText('Showing the last loaded results. Current workflow states and totals are unconfirmed.', {exact: true})).toBeVisible();
        if (mode === 'loaded') {
            await expect(page.getByText('Last loaded stage: Implementation', {exact: true})).toBeVisible();
            await expect(page.getByText('Last loaded approval state', {exact: true})).toBeVisible();
            await expect(page.getByText('Current State', {exact: true})).toHaveCount(0);
        } else {
            await expect(page.getByText(mode === 'filtered' ? 'The last loaded search had no matches.' : 'The last loaded list was empty.', {exact: true})).toBeVisible();
            await expect(page.getByRole('link', {name: 'Review change proposals', exact: true})).toHaveCount(0);
        }
        releaseFailure();
        await expect(page.getByRole('alert')).toContainText('Refresh failed:');
        await expect(retainedHeading).toBeVisible();
        if (width !== 320 && mode === 'loaded') await page.screenshot({path: `/tmp/atlas-retained-workflows-${width}.png`, fullPage: true});
        phase = 'recovery';
        await page.getByRole('button', {name: 'Refresh', exact: true}).click();
        await expect(retainedHeading).toBeVisible();
        await expect(page.getByRole('button', {name: 'Refresh', exact: true})).toBeDisabled();
        releaseRecovery();
        await expect(page.getByRole('heading', {name: 'Totals for this search', exact: true})).toBeVisible();
        await expect(page.getByRole('alert')).toHaveCount(0);
        await expect(page.getByText('Last loaded state', {exact: true})).toHaveCount(0);
        if (mode === 'loaded') await expect(page.getByText('Latest workflow result', {exact: true})).toBeVisible();
        else await expect(page.getByText(mode === 'filtered' ? 'No workflows match the current filters.' : 'No workflows yet.', {exact: true})).toBeVisible();
        if (mode === 'empty') await expect(page.getByRole('link', {name: 'Review change proposals', exact: true})).toBeVisible();
        expect(reads).toHaveLength(mode === 'filtered' ? 4 : 3);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
