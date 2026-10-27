import { expect, test } from '@playwright/test';
import { installRepositoryJourney, journey } from './repository-journey-fixture';
for (const width of [320, 390, 1280]) {
    test(`opening and reloading a saved workflow summary only reads at ${width}px`, async ({page, baseURL}) => {
        const fixture = await installRepositoryJourney(page, true, {baseURL});
        await page.setViewportSize({width, height: 844});
        await page.goto(`/candidate-planning/${journey.session}/workflow`);
        await expect(page.getByRole('button', {name: 'Prepare exact request', exact: true})).toBeEnabled();
        await page.reload();
        await expect(page.getByRole('button', {name: 'Prepare exact request', exact: true})).toBeEnabled();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        if (width === 390 || width === 1280) await page.screenshot({ path: `/tmp/atlas-workflow-summary-${width}.png`, fullPage: true });
        expect(fixture.writes).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
    });
    test(`a failed workflow summary retries with reads only at ${width}px`, async ({page, baseURL}) => {
        const fixture = await installRepositoryJourney(page, true, {baseURL});
        await page.setViewportSize({width, height: 844});
        let reads = 0;
        await page.route(`**/agent-api/candidate-planning/${journey.session}/workflow`, route => {
            if (route.request().method() !== 'GET') return route.fallback();
            reads += 1;
            return reads === 1 ? route.fulfill({ status: 503, json: {detail: 'Temporarily unavailable'} }) : route.fallback();
        });
        await page.goto(`/candidate-planning/${journey.session}/workflow`);
        await expect(page.getByRole('alert')).toContainText('Workflow summary unavailable');
        await expect(page.getByRole('button', {name: 'Prepare exact request', exact: true})).toHaveCount(0);
        await page.getByRole('button', {name: 'Try again', exact: true}).click();
        await expect(page.getByRole('button', {name: 'Prepare exact request', exact: true})).toBeEnabled();
        expect(reads).toBe(2);
        expect(fixture.writes).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
    });
}
