import { expect, test } from './mission-control-fixtures';
for (const width of [320, 768, 1440]) {
    test(`overview fits ${width}px and links to existing detail routes`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto('/');
        const grid = page.getByTestId('overview-grid');
        await expect(grid.getByRole('region')).toHaveCount(6);
        await expect(page.getByRole('button', { name: 'Refresh', exact: true })).toBeEnabled();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        const columns = await grid.evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length);
        expect(columns).toBe(width < 768 ? 1 : width < 1280 ? 2 : 3);
        await page.getByRole('link', { name: 'Inspect executions →' }).click();
        await expect(page).toHaveURL(/\/workflows$/);
        await page.goBack();
        await page.getByRole('link', { name: 'Inspect Proxmox →' }).click();
        await expect(page).toHaveURL(/\/providers\/proxmox$/);
        await page.goBack();
        await page.getByRole('link', { name: 'Open operational history →' }).click();
        await expect(page).toHaveURL(/\/operations\/history$/);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

test('narrow overview preserves unknown evidence and distinct attention conditions', async ({ page, rejectedMutationRequests }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.route('**/health', route => route.fulfill({ json: {
        atlas: null, services: { API: { provider_id: 'proxmox', status: 'offline', message: 'Endpoint offline' } },
    } }));
    await page.route('**/providers', route => route.fulfill({ json: [
        { id: 'proxmox', name: 'Proxmox', health: { status: 'warning', message: 'Capacity limited' } },
    ] }));
    await page.goto('/');
    const attention = page.getByRole('region', { name: 'Operator Attention' });
    await expect(attention.getByText('Endpoint offline')).toBeVisible();
    await expect(attention.getByText('Capacity limited')).toBeVisible();
    await expect(page.getByRole('region', { name: 'Atlas overall state' }).getByText('Unknown', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await attention.getByRole('link', { name: 'API', exact: true }).click();
    await expect(page).toHaveURL(/\/providers\/proxmox$/);
    expect(rejectedMutationRequests).toEqual([]);
});

test('mobile attention includes configured AI failure and follows its provider route', async ({ page, rejectedMutationRequests }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.route('**/ai/status', route => route.fulfill({ json: {
        provider: { id: 'proxmox', name: 'Configured runtime' },
        health: { status: 'offline', message: 'Runtime endpoint unavailable' },
    } }));
    await page.goto('/');
    const attention = page.getByRole('region', { name: 'Operator Attention' });
    await expect(attention.getByText('Runtime endpoint unavailable')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await attention.getByRole('link', { name: 'Configured runtime', exact: true }).click();
    await expect(page).toHaveURL(/\/providers\/proxmox$/);
    expect(rejectedMutationRequests).toEqual([]);
});
