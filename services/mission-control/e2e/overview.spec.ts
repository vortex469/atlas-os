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
