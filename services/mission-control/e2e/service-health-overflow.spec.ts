import { expect, test } from './mission-control-fixtures';

for (const width of [320, 390, 1280]) for (const mode of ['updated', 'stale'] as const) {
    test(`all reported services remain accessible at ${width}px (${mode})`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        let refreshed = false;
        let reads = 0;
        await page.route('**/api/v1/health', route => {
            expect(route.request().method()).toBe('GET');
            reads++;
            return refreshed && mode === 'stale'
                ? route.fulfill({ status: 503, json: { detail: 'Fixture refresh unavailable' } })
                : route.fulfill({ json: { atlas: 'healthy', services: Object.fromEntries(Array.from({ length: refreshed ? 8 : 7 }, (_, index) => [
                    `Service ${index + 1}`, { status: 'healthy', message: `Reported service ${index + 1}` },
                ])) } });
        });
        await page.goto('/');
        await expect(page.getByRole('button', { name: 'Refresh', exact: true })).toBeEnabled();
        const card = page.getByRole('region', { name: 'Service health', exact: true });
        await expect(card.getByText('Service 4', { exact: true })).toBeVisible();
        await expect(card.getByText('Service 7', { exact: true })).toBeHidden();
        const more = card.locator('summary', { hasText: 'More services' });
        await expect(more).toHaveText('More services (3)');
        await more.focus(); await page.keyboard.press('Enter');
        await expect(card.getByText('Service 7', { exact: true })).toBeVisible();
        expect(reads).toBe(1);
        refreshed = true;
        await page.getByRole('button', { name: 'Refresh', exact: true }).click();
        await expect(page.getByRole('button', { name: 'Refresh', exact: true })).toBeEnabled();
        if (mode === 'updated') {
            await expect(more).toHaveText('More services (4)');
            await expect(card.getByText('Service 8', { exact: true })).toBeVisible();
        } else {
            const retained = card.getByText('Service 7', { exact: true }).locator('..');
            await expect(retained.getByText('Last-known status: Healthy · Current state unknown', { exact: true })).toBeVisible();
            await expect(retained.getByText('Healthy', { exact: true })).toHaveCount(0);
        }
        await expect(card.getByText('Service 7', { exact: true })).toBeVisible();
        await expect(card.getByText('Reported service 7', { exact: true })).toBeVisible();
        await more.focus(); await page.keyboard.press('Enter');
        await expect(card.getByText('Service 7', { exact: true })).toBeHidden();
        await page.keyboard.press('Enter');
        await expect(card.getByText('Service 7', { exact: true })).toBeVisible();
        expect(reads).toBe(2);
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        if (mode === 'updated' && width !== 320) {
            await more.focus(); await page.keyboard.press('Enter');
            await page.evaluate(() => scrollTo(0, 0));
            await page.screenshot({ path: `/tmp/atlas-service-health-${width}.png`, fullPage: true });
        }
    });
}
