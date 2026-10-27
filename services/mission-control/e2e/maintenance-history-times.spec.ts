import { expect, test } from './mission-control-fixtures';
import { operationalLifecycle, operationalDiagnostic } from '../src/test/operationalLifecycle';

for (const width of [320, 390, 1280]) for (const timestamp of ['2026-02-30T00:00:00Z', '2026-08-16T00:00:00', '2099-01-01T00:00:00Z']) {
    test(`maintenance history time ${timestamp} stays unknown at ${width}px until corrected`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        let refreshed = false;
        const reads = { list: 0, lifecycle: 0, diagnostic: 0 };
        const validTime = '2026-08-16T14:00:00+02:00';
        await page.route('**/agent-api/api/v1/agent/workflows**', route => {
            const request = route.request();
            const url = new URL(request.url());
            expect(request.method()).toBe('GET');
            if (url.pathname.endsWith('/workflows')) {
                reads.list++;
                expect(Object.fromEntries(url.searchParams)).toEqual({ effect_kind: 'operational_action', limit: '10', offset: '0' });
                return route.fulfill({ json: { items: [{ workflow_id: 'history-time', workflow_source: 'candidate', workflow_state: 'completed', effect_kind: 'operational_action', execution_intent: 'restart-service', target_id: '110', timeline: [] }], total: 1, limit: 10, offset: 0 } });
            }
            if (url.pathname.endsWith('/operational-lifecycle')) {
                reads.lifecycle++;
                return route.fulfill({ json: operationalLifecycle({ workflow_id: 'history-time', request_created_at: refreshed ? validTime : timestamp, verification_completed_at: refreshed ? validTime : timestamp }) });
            }
            expect(url.pathname).toBe('/agent-api/api/v1/agent/workflows/history-time/recovery-diagnostic');
            reads.diagnostic++;
            const diagnostic = operationalDiagnostic();
            return route.fulfill({ json: { ...diagnostic, correlation: { ...diagnostic.correlation, workflow_id: 'history-time' } } });
        });
        await page.goto('/operations/history');
        await expect(page.getByText('Requested: Unknown time', { exact: true })).toBeVisible();
        await page.getByText('Workflow details', { exact: true }).click();
        await expect(page.getByText('Result recorded', { exact: true }).locator('..')).toContainText('Unknown time');
        expect(reads).toEqual({ list: 1, lifecycle: 1, diagnostic: 1 });
        refreshed = true;
        await page.getByRole('button', { name: 'Refresh history', exact: true }).click();
        const formatted = await page.evaluate(value => new Date(value).toLocaleString(), validTime);
        await expect(page.getByText(`Requested: ${formatted}`, { exact: true })).toBeVisible();
        await page.getByText('Workflow details', { exact: true }).click();
        await expect(page.getByText('Result recorded', { exact: true }).locator('..')).toContainText(formatted);
        expect(reads).toEqual({ list: 2, lifecycle: 2, diagnostic: 2 });
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
}
