import { expect, test } from './mission-control-fixtures';
import { maintenanceCandidate } from './repository-journey-fixture';

for (const width of [320, 390, 1280]) {
    for (const mode of ['timer', 'clock-jump'] as const) {
        test(`planning expiry ${mode} at ${width}px stays read-only until a current proposal is loaded`, async ({ page, baseURL, rejectedMutationRequests }) => {
            await page.setViewportSize({ width, height: 900 });
            await page.clock.install({ time: new Date('2026-10-26T00:00:00Z') });
            await page.clock.pauseAt(new Date('2026-10-26T00:00:00Z'));
            let reads = 0;
            let refreshed = false;
            // Development StrictMode replays the initial read; built assets read once.
            const initialReads = new URL(baseURL!).port === '4173' ? 1 : 2;
            await page.route('**/api/v1/execution-candidates/candidate-expiry', route => {
                expect(route.request().method()).toBe('GET');
                reads++;
                return route.fulfill({ json: { ...maintenanceCandidate, id: 'candidate-expiry',
                    expires_at: !refreshed ? '2026-10-26T00:01:00Z' : '2026-10-26T00:10:00Z' } });
            });
            await page.goto('/execution-candidates/candidate-expiry');
            const planning = page.getByRole('button', { name: 'Start planning', exact: true });
            await expect(planning).toBeEnabled();
            expect(reads).toBe(initialReads);
            if (mode === 'timer') await page.clock.runFor(60_000);
            else {
                // Move wall time without running the display deadline callback.
                await page.clock.setSystemTime(new Date('2026-10-26T00:02:00Z'));
                await planning.click();
            }
            await expect(planning).toBeDisabled();
            await expect(page.getByText('Candidate has expired.', { exact: true })).toBeVisible();
            expect(reads).toBe(initialReads);
            expect(rejectedMutationRequests).toEqual([]);
            refreshed = true;
            await page.getByRole('button', { name: 'Refresh proposal', exact: true }).click();
            await expect(planning).toBeEnabled();
            await expect(page.getByText('Candidate has expired.', { exact: true })).toHaveCount(0);
            expect(reads).toBe(initialReads + 1);
            expect(rejectedMutationRequests).toEqual([]);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        });
    }
}
