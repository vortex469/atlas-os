import { expect, test } from './mission-control-fixtures';

for (const width of [320, 390, 1280]) for (const kind of ['metadata', 'timeline', 'identity'] as const) {
    test(`workflow ${kind} record recovery at ${width}px stays read-only`, async ({page, rejectedMutationRequests}) => {
        await page.setViewportSize({width, height: 900});
        let phase = 'bad-initial';
        let reads = 0;
        const base = {workflow_id: 'workflow-browser-baseline', workflow_source: 'candidate', workflow_state: 'awaiting_implementation_approval',
            effect_kind: 'repository_change', execution_intent: 'update-compose-stack', candidate_id: null, planning_session_id: null,
            repository: '/fixture/repository', target_id: null, last_result_summary: 'Last valid record', timeline: []};
        const invalid = kind === 'metadata' ? {...base, repository: {untrusted: 'private-detail'}}
            : kind === 'timeline' ? {...base, timeline: [{name: 'Execution', status: {untrusted: 'private-detail'}}]}
            : {...base, workflow_id: '.'};
        await page.route('**/agent-api/api/v1/agent/workflows?**', route => {
            expect(route.request().method()).toBe('GET'); reads += 1;
            const item = phase.startsWith('bad') ? invalid : {...base,
                workflow_state: phase === 'good-final' && kind === 'identity' ? 'future_state' : base.workflow_state,
                last_result_summary: phase === 'good-final' ? 'Latest valid record' : base.last_result_summary};
            return route.fulfill({json: {items: [item], total: 1, limit: 10, offset: 0, state_counts: {[item.workflow_state]: 1}}});
        });
        await page.goto('/workflows');
        await expect(page.getByRole('heading', {name: 'Workflows unavailable', exact: true})).toBeVisible();
        await expect(page.getByRole('alert')).toContainText('inconsistent workflow page');
        await expect(page.getByText('private-detail', {exact: true})).toHaveCount(0);
        phase = 'good-initial';
        await page.getByRole('button', {name: 'Try again', exact: true}).click();
        await expect(page.getByRole('heading', {name: 'Update Compose Stack', exact: true})).toBeVisible();
        await expect(page.getByText(base.repository, {exact: true})).toBeVisible();
        phase = 'bad-refresh';
        await page.getByRole('button', {name: 'Refresh', exact: true}).click();
        await expect(page.getByRole('alert')).toContainText('inconsistent workflow page');
        await expect(page.getByRole('heading', {name: 'Last loaded totals for this search', exact: true})).toBeVisible();
        await expect(page.getByText(base.repository, {exact: true})).toBeVisible();
        await expect(page.getByText('Last loaded state', {exact: true})).toBeVisible();
        await expect(page.getByText('private-detail', {exact: true})).toHaveCount(0);
        phase = 'good-final';
        await page.getByRole('button', {name: 'Refresh', exact: true}).click();
        await expect(page.getByText('Latest valid record', {exact: true})).toBeVisible();
        await expect(page.getByRole('heading', {name: 'Totals for this search', exact: true})).toBeVisible();
        await expect(page.getByRole('alert')).toHaveCount(0);
        await expect(page.getByText('Last loaded state', {exact: true})).toHaveCount(0);
        const card = page.getByRole('article').filter({has: page.getByRole('heading', {name: 'Update Compose Stack', exact: true})});
        if (kind === 'identity') {
            await expect(card.getByText('Unknown — open workflow to review', {exact: true})).toBeVisible();
            await expect(card.getByText('Not waiting for approval', {exact: true})).toHaveCount(0);
            await expect(page.getByText('Other states', {exact: true})).toBeVisible();
        } else await expect(card.getByText('Waiting for approval', {exact: true})).toBeVisible();
        expect(reads).toBe(4);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
