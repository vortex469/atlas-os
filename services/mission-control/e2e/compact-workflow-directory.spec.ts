import { expect, test } from './mission-control-fixtures';

for (const width of [320, 390, 1280]) for (const state of ['awaiting_implementation_approval', 'completed', 'blocked'] as const) {
    test(`compact ${state} directory card at ${width}px preserves result and records`, async ({page, rejectedMutationRequests}) => {
        await page.setViewportSize({width, height: 900});
        await page.route('**/agent-api/api/v1/agent/workflows?**', route => route.fulfill({json: {
            items: [{workflow_id: 'workflow-browser-baseline', workflow_source: 'candidate', workflow_state: state,
                effect_kind: 'repository_change', execution_intent: 'update-compose-stack', candidate_id: 'saved-candidate',
                planning_session_id: 'saved-planning', repository: '/fixture/repository', target_id: 'fixture-stack',
                last_result_summary: 'Recorded workflow result', timeline: []}],
            total: 1, limit: 10, offset: 0, state_counts: {[state]: 1},
        }}));
        await page.goto('/workflows');
        const card = page.getByRole('article').filter({has: page.getByRole('heading', {name: 'workflow-browser-baseline', exact: true})});
        await expect(card.getByText('/fixture/repository', {exact: true})).toBeVisible();
        await expect(card.getByText('Recorded workflow result', {exact: true})).toBeVisible();
        await expect(card.getByText('saved-candidate', {exact: true})).not.toBeVisible();
        await expect(card.getByText('saved-planning', {exact: true})).not.toBeVisible();
        const details = card.locator('summary', {hasText: 'Workflow details'});
        await details.focus(); await page.keyboard.press('Enter');
        await expect(card.getByText('saved-candidate', {exact: true})).toBeVisible();
        await expect(card.getByText('saved-planning', {exact: true})).toBeVisible();
        await page.keyboard.press('Enter');
        const progress = card.locator('summary', {hasText: 'Workflow progress'});
        if (state === 'blocked') await expect(card.locator('ol')).toBeVisible();
        else await expect(card.locator('ol')).not.toBeVisible();
        await progress.focus(); await page.keyboard.press('Enter');
        if (state === 'blocked') await expect(card.locator('ol')).not.toBeVisible();
        else await expect(card.locator('ol')).toBeVisible();
        await page.keyboard.press('Enter');
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        if (width !== 320) await card.screenshot({path: `/tmp/atlas-directory-card-${width}-${state}.png`});
        await card.getByRole('link', {name: 'Open Workflow', exact: true}).click();
        await expect(page).toHaveURL(/\/workflows\/workflow-browser-baseline$/);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
