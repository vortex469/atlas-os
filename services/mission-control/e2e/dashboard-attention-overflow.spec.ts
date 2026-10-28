import { expect, test } from './mission-control-fixtures';

for (const width of [320, 390, 1280]) for (const mode of ['updated', 'stale'] as const) {
    test(`all dashboard conditions remain reachable at ${width}px (${mode})`, async ({page, rejectedMutationRequests}) => {
        await page.setViewportSize({width, height: 900});
        let refreshed = false;
        await page.route('**/api/v1/providers', route => refreshed && mode === 'stale'
            ? route.fulfill({status: 503, json: {detail: 'Fixture refresh unavailable'}})
            : route.fulfill({json: Array.from({length: refreshed ? 7 : 6}, (_, i) => ({
                id: `problem-${i}`, name: `Reported problem ${i}`, health: {status: 'blocked', message: `Review provider condition ${i}`},
            }))}));
        await page.goto('/');
        await expect(page.getByRole('button', {name: 'Refresh', exact: true})).toBeEnabled();
        const attention = page.getByRole('region', {name: 'Operator Attention', exact: true});
        const workflow = attention.getByRole('link', {name: 'Update Compose Stack', exact: true});
        await expect(attention.getByRole('link', {name: 'Reported problem 4', exact: true})).toBeVisible();
        await expect(attention.getByText('Reported problem 5', {exact: true})).not.toBeVisible();
        await expect(workflow).not.toBeVisible();
        const more = attention.locator('summary', {hasText: 'More conditions'});
        await expect(more).toHaveText('More conditions (2)');
        await more.focus(); await page.keyboard.press('Enter');
        await expect(attention.getByRole('link', {name: 'Reported problem 5', exact: true})).toBeVisible();
        await expect(workflow).toBeVisible();
        const workflowItem = workflow.locator('..');
        await expect(workflowItem.getByText('Workflow ID: workflow-browser-baseline', {exact: true})).toBeHidden();
        await workflowItem.getByText('Workflow details', {exact: true}).click();
        await expect(workflowItem.getByText('Workflow ID: workflow-browser-baseline', {exact: true})).toBeVisible();
        await workflowItem.getByText('Workflow details', {exact: true}).click();
        refreshed = true;
        await page.getByRole('button', {name: 'Refresh', exact: true}).click();
        if (mode === 'updated') {
            await expect(more).toHaveText('More conditions (3)');
            await expect(attention.getByRole('link', {name: 'Reported problem 6', exact: true})).toBeVisible();
        } else {
            await expect(attention.getByText('Providers: Refresh failed. Showing previously reported information only; current status is unknown.', {exact: true})).toBeVisible();
            const extra = attention.getByRole('link', {name: 'Reported problem 5', exact: true}).locator('..');
            await expect(extra.getByText('Last-known condition; current state unknown.', {exact: true})).toBeVisible();
            await expect(extra.getByText('Blocked', {exact: true})).toHaveCount(0);
        }
        await expect(workflow).toBeVisible();
        await more.focus(); await page.keyboard.press('Enter');
        await expect(workflow).not.toBeVisible();
        await page.keyboard.press('Enter');
        await expect(workflow).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        if (mode === 'updated' && width !== 320) await page.screenshot({path: `/tmp/atlas-attention-overflow-${width}.png`, fullPage: true});
        await workflow.click();
        await expect(page).toHaveURL(/\/workflows\/workflow-browser-baseline$/);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
