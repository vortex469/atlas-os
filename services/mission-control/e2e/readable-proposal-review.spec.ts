import { expect, test } from './mission-control-fixtures';
import { maintenanceCandidate } from './repository-journey-fixture';

for (const width of [320, 390, 1280]) for (const mode of ['metadata', 'lists', 'optional'] as const) {
    test(`unreadable proposal ${mode} at ${width}px recovers only through proposal reads`, async ({ page, baseURL, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        let reads = 0;
        let unreadable = true;
        const initialReads = new URL(baseURL!).port === '4173' ? 1 : 2;
        await page.route('**/api/v1/execution-candidates/review-readable', route => {
            expect(route.request().method()).toBe('GET');
            reads++;
            const candidate = { ...maintenanceCandidate, id: 'review-readable', expires_at: '2999-01-01T00:00:00Z',
                created_at: mode === 'metadata' ? '2026-02-30T00:00:00Z' : mode === 'lists' ? '2026-08-16T00:00:00' : '2099-01-01T00:00:00Z',
            };
            const badFields = mode === 'metadata' ? { execution_intent: {}, target_id: {} }
                : mode === 'lists' ? { constraints: [{}] } : { compatibility_status: {} };
            return route.fulfill({ json: unreadable ? { ...candidate, ...badFields } : candidate });
        });
        await page.goto('/execution-candidates/review-readable');
        const error = page.getByRole('alert');
        await expect(error).toContainText('The proposal response is incomplete or unreadable. Choose Try again to reload it.');
        await expect(page.getByRole('button', { name: 'Start planning', exact: true })).toHaveCount(0);
        expect(reads).toBe(initialReads);
        unreadable = false;
        await page.getByRole('button', { name: 'Try again', exact: true }).click();
        await expect(page.getByRole('heading', { name: 'Restart Service', exact: true, level: 1 })).toBeVisible();
        await expect(page.getByRole('button', { name: 'Start planning', exact: true })).toBeEnabled();
        await expect(error).toHaveCount(0);
        const details = page.getByText('Technical details', { exact: true });
        await details.click();
        await expect(page.getByText('Created', { exact: true }).locator('..')).toContainText('Unknown time');
        await details.click();
        unreadable = true;
        await page.getByRole('button', { name: 'Refresh proposal', exact: true }).click();
        await expect(error).toContainText('The proposal response is incomplete or unreadable.');
        await expect(page.getByRole('button', { name: 'Start planning', exact: true })).toHaveCount(0);
        await expect(page.getByRole('link', { name: 'Continue planning', exact: true })).toHaveCount(0);
        unreadable = false;
        await page.getByRole('button', { name: 'Try again', exact: true }).click();
        await expect(page.getByRole('button', { name: 'Start planning', exact: true })).toBeEnabled();
        expect(reads).toBe(initialReads + 3);
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
}
