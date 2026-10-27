import { expect, test } from './mission-control-fixtures';

for (const width of [320, 390, 1280]) for (const mode of ['health', 'assessment', 'policy', 'stale', 'unknown'] as const) {
    test(`reported health attention at ${width}px (${mode}) stays read-only`, async ({page, rejectedMutationRequests}) => {
        await page.setViewportSize({width, height: 900});
        let failedRefresh = false;
        const checkedAt = new Date().toISOString();
        if (mode === 'health' || mode === 'unknown') await page.route('**/api/v1/health', route => route.fulfill({json: {
            atlas: mode === 'unknown' ? {} : 'degraded', services: {},
        }}));
        if (mode === 'assessment' || mode === 'unknown') await page.route('**/api/v1/ace/summary', route => route.fulfill({json: {
            status: mode === 'unknown' ? 'future_status' : 'critical', summary: 'Recorded assessment needs review', findings: [], recommendations: [],
        }}));
        if (mode === 'policy' || mode === 'stale' || mode === 'unknown') await page.route('**/api/v1/policies/status', route => failedRefresh
            ? route.fulfill({status: 503, json: {detail: 'Fixture refresh unavailable'}})
            : route.fulfill({json: {status: mode === 'unknown' ? null : 'degraded', error: 'Recorded policy validation failed', checked_at: checkedAt, source_exists: true, loaded_at: null, duration_ms: 2, diagnostics: []}}));
        await page.goto('/');
        await expect(page.getByRole('button', {name: 'Refresh', exact: true})).toBeEnabled();
        const attention = page.getByRole('region', {name: 'Operator Attention', exact: true});
        if (mode === 'unknown') {
            for (const name of ['Atlas health', 'System assessment', 'Policy status']) await expect(attention.getByRole('link', {name, exact: true})).toHaveCount(0);
        } else {
            const label = mode === 'health' ? 'Atlas health' : mode === 'assessment' ? 'System assessment' : 'Policy status';
            const target = mode === 'health' ? 'atlas-health' : mode === 'assessment' ? 'system-assessment' : 'policy-status';
            const link = attention.getByRole('link', {name: label, exact: true});
            await expect(link).toBeVisible();
            if (mode === 'stale') {
                failedRefresh = true;
                await page.getByRole('button', {name: 'Refresh', exact: true}).click();
                await expect(attention.getByText('Last-known condition; current state unknown.', {exact: true})).toBeVisible();
                await expect(attention.getByText('Last-known status: Degraded · Current state unknown', {exact: true})).toBeVisible();
                await expect(attention.getByText('Degraded', {exact: true})).toHaveCount(0);
            }
            if (mode === 'assessment' && width !== 320) await page.screenshot({path: `/tmp/atlas-dashboard-health-attention-${width}.png`});
            await link.focus();
            await page.keyboard.press('Enter');
            await expect(page).toHaveURL(new RegExp(`#${target}$`));
            await expect(page.locator(`#${target}`)).toBeInViewport();
            await expect(page.locator(`#${target}`)).toBeFocused();
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
