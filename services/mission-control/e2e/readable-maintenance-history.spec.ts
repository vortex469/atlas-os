import { expect, test } from './mission-control-fixtures';
import { operationalLifecycle, operationalDiagnostic } from '../src/test/operationalLifecycle';

for (const width of [320, 390, 1280]) for (const mode of ['paging', 'metadata', 'lifecycle'] as const) {
    test(`maintenance history ${mode} recovery at ${width}px preserves only readable correlated data`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        const reads = { list: 0, lifecycle: 0, diagnostic: 0 };
        const workflow = { workflow_id: 'history-readable', workflow_source: 'candidate', workflow_state: 'completed', effect_kind: 'operational_action', execution_intent: 'restart-service', target_id: 'Safe target', timeline: [] };
        await page.route('**/agent-api/api/v1/agent/workflows**', route => {
            const request = route.request();
            const url = new URL(request.url());
            expect(request.method()).toBe('GET');
            if (url.pathname.endsWith('/workflows')) {
                reads.list++;
                expect(Object.fromEntries(url.searchParams)).toEqual({ effect_kind: 'operational_action', limit: '10', offset: '0' });
                const bad = mode !== 'lifecycle' && (reads.list === 1 || reads.list === 3);
                return route.fulfill({ json: { items: [bad && mode === 'metadata' ? { ...workflow, workflow_state: {}, target_id: {} } : workflow], total: 1, limit: 10, offset: bad && mode === 'paging' ? 10 : 0 } });
            }
            if (url.pathname.endsWith('/operational-lifecycle')) {
                reads.lifecycle++;
                const lifecycle = operationalLifecycle({ workflow_id: workflow.workflow_id, target_label: reads.lifecycle === 1 ? 'Readable target' : 'Updated readable target' });
                return route.fulfill({ json: mode === 'lifecycle' && reads.lifecycle === 1 ? { ...lifecycle, target_label: {}, verification_status: {} } : lifecycle });
            }
            expect(url.pathname).toBe('/agent-api/api/v1/agent/workflows/history-readable/recovery-diagnostic');
            reads.diagnostic++;
            const diagnostic = operationalDiagnostic();
            return route.fulfill({ json: { ...diagnostic, correlation: { ...diagnostic.correlation, workflow_id: workflow.workflow_id } } });
        });
        await page.goto('/operations/history');
        const refresh = page.getByRole('button', { name: 'Refresh history', exact: true });
        if (mode === 'lifecycle') {
            await expect(page.getByRole('heading', { name: 'Safe target', exact: true })).toBeVisible();
            await expect(page.getByRole('heading', { name: 'Healthy', exact: true })).toBeVisible();
            await page.getByText('Workflow details', { exact: true }).click();
            await expect(page.getByText('Verification', { exact: true }).locator('..')).toContainText('Not reported');
            await refresh.click();
        } else {
            await expect(page.getByRole('alert')).toContainText('Could not load maintenance history.');
            await expect(page.getByRole('link', { name: 'Open workflow', exact: true })).toHaveCount(0);
            expect(reads).toEqual({ list: 1, lifecycle: 0, diagnostic: 0 });
            await refresh.click();
            await expect(page.getByRole('heading', { name: 'Readable target', exact: true })).toBeVisible();
            await expect(page.getByRole('heading', { name: 'Healthy', exact: true })).toBeVisible();
            await refresh.click();
            await expect(page.getByRole('alert')).toContainText('Could not load maintenance history.');
            await expect(page.getByRole('heading', { name: 'Readable target', exact: true })).toBeVisible();
            await expect(page.getByRole('heading', { name: 'Last loaded: Healthy', exact: true })).toBeVisible();
            expect(reads).toEqual({ list: 3, lifecycle: 1, diagnostic: 1 });
            await refresh.click();
        }
        await expect(page.getByRole('heading', { name: 'Updated readable target', exact: true })).toBeVisible();
        await expect(page.getByRole('heading', { name: 'Healthy', exact: true })).toBeVisible();
        await expect(page.getByRole('alert')).toHaveCount(0);
        expect(reads).toEqual({ list: mode === 'lifecycle' ? 2 : 4, lifecycle: 2, diagnostic: 2 });
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
}
