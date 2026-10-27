import { expect, test } from './mission-control-fixtures';

for (const width of [320, 390, 1280]) for (const [mode, completed_at] of [
    ['impossible', '2026-02-30T12:00:00Z'],
    ['timezone-free', '2026-02-01T12:00:00'],
    ['future', '2099-01-01T00:00:00Z'],
    ['offset', '2026-02-01T14:00:00+02:00'],
] as const) {
    test(`activity completion time ${mode} at ${width}px preserves the recorded action`, async ({page, rejectedMutationRequests}) => {
        await page.setViewportSize({width, height: 900});
        await page.route('**/api/v1/ops/actions/page?**', route => route.fulfill({json: {
            items: [
                {id: 'audit/uncertain', action_label: 'Inspect reported time', provider_name: 'Recorded provider', status: 'failed', completed_at},
                {id: 'audit/known', action_label: 'Known completion', provider_name: 'Recorded provider', status: 'succeeded', completed_at: '2026-01-01T12:00:00Z'},
            ], total: 2, offset: 0, limit: 5, has_more: false,
        }}));
        await page.goto('/');
        const activity = page.getByRole('region', {name: 'Recent Activity', exact: true});
        await expect(activity.getByRole('listitem')).toHaveCount(2);
        const record = activity.getByRole('listitem').filter({hasText: 'Failed · Inspect reported time'});
        if (mode === 'offset') {
            await expect(record.locator('time')).toHaveAttribute('datetime', '2026-02-01T12:00:00.000Z');
            await expect(activity.getByRole('listitem').first()).toContainText('Failed · Inspect reported time');
            await expect(activity.getByText('Completion time unknown.', {exact: true})).toHaveCount(0);
        } else {
            await expect(record.getByText('Completion time unknown.', {exact: true})).toBeVisible();
            await expect(record.locator('time')).toHaveCount(0);
            await expect(activity.getByRole('listitem').first()).toContainText('Succeeded · Known completion');
            await expect(activity.getByText('Some activity records are malformed or incomplete.', {exact: true})).toBeVisible();
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        await record.getByRole('link', {name: 'Inspect action →', exact: true}).click();
        await expect(page).toHaveURL(/\/operations\/actions\/audit%2Funcertain$/);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
