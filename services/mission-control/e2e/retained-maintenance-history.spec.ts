import { expect, test } from './mission-control-fixtures';
import { operationalLifecycle, operationalDiagnostic } from '../src/test/operationalLifecycle';

for (const width of [320, 390, 1280]) for (const mode of ['populated', 'empty', 'page'] as const) {
    test(`maintenance history retains ${mode} results at ${width}px through failed and retried reads`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        let releaseFailure!: () => void;
        let releaseRecovery!: () => void;
        const failureGate = new Promise<void>(resolve => { releaseFailure = resolve; });
        const recoveryGate = new Promise<void>(resolve => { releaseRecovery = resolve; });
        const offsets: number[] = [];
        let lifecycleReads = 0;
        let diagnosticReads = 0;
        const workflow = (id: string) => ({ workflow_id: id, workflow_source: 'candidate', workflow_state: 'completed', effect_kind: 'operational_action', execution_intent: 'restart-service', target_id: `Target ${id}`, timeline: [] });
        await page.route('**/agent-api/api/v1/agent/workflows**', async route => {
            const request = route.request();
            const url = new URL(request.url());
            expect(request.method()).toBe('GET');
            if (url.pathname.endsWith('/workflows')) {
                const offset = Number(url.searchParams.get('offset'));
                expect(Object.fromEntries(url.searchParams)).toEqual({ effect_kind: 'operational_action', limit: '10', offset: String(offset) });
                offsets.push(offset);
                if (offsets.length === 2) {
                    await failureGate;
                    return route.fulfill({ status: 503, json: { detail: 'Fixture read unavailable' } });
                }
                if (offsets.length === 3) await recoveryGate;
                const items = offsets.length === 1
                    ? mode === 'empty' ? [] : mode === 'page' ? Array.from({ length: 10 }, (_, index) => workflow(String(index))) : [workflow('original')]
                    : [workflow(mode === 'page' ? '10' : 'updated')];
                return route.fulfill({ json: { items, total: mode === 'page' ? 11 : items.length, limit: 10, offset } });
            }
            const id = url.pathname.split('/').at(-2)!;
            if (url.pathname.endsWith('/operational-lifecycle')) {
                lifecycleReads++;
                return route.fulfill({ json: operationalLifecycle({ workflow_id: id, target_label: `Target ${id}` }) });
            }
            expect(url.pathname).toBe(`/agent-api/api/v1/agent/workflows/${id}/recovery-diagnostic`);
            diagnosticReads++;
            const diagnostic = operationalDiagnostic();
            return route.fulfill({ json: { ...diagnostic, correlation: { ...diagnostic.correlation, workflow_id: id } } });
        });
        await page.goto('/operations/history');
        await expect(page.getByRole('button', { name: 'Refresh history', exact: true })).toBeEnabled();
        const original = page.getByText(mode === 'page' ? 'Target 0' : 'Target original', { exact: true });
        if (mode === 'empty') await expect(page.getByText('No maintenance requests yet.', { exact: true })).toBeVisible();
        else await expect(original).toBeVisible();
        await page.getByRole('button', { name: mode === 'page' ? 'Next' : 'Refresh history', exact: true }).click();
        const retained = page.getByText('Showing the last loaded maintenance history. Current results have not been confirmed.', { exact: true });
        await expect(retained).toBeVisible();
        if (mode === 'empty') {
            await expect(page.getByText('No requests in the last loaded page. Current results have not been confirmed.', { exact: true })).toBeVisible();
            await expect(page.getByText('No maintenance requests yet.', { exact: true })).toHaveCount(0);
        } else {
            await expect(original).toBeVisible();
            await expect(page.getByRole('heading', { name: 'Healthy', exact: true })).toHaveCount(0);
            await expect(page.getByRole('heading', { name: 'Last loaded: Healthy', exact: true })).toHaveCount(mode === 'page' ? 10 : 1);
            await expect(page.getByText('Safe next action:', { exact: true })).toHaveCount(0);
        }
        if (mode === 'page') {
            await expect(page.getByText('Last loaded: Showing 1–10 of 11', { exact: true })).toBeVisible();
            await expect(page.getByRole('button', { name: 'Next', exact: true })).toBeDisabled();
        }
        releaseFailure();
        await expect(page.getByRole('alert')).toBeVisible();
        await expect(retained).toBeVisible();
        if (mode !== 'empty') await expect(original).toBeVisible();
        if (mode === 'populated' && width !== 320) {
            await page.evaluate(() => scrollTo(0, 0));
            await page.screenshot({ path: `/tmp/atlas-retained-maintenance-history-${width}.png`, fullPage: true });
        }
        await page.getByRole('button', { name: mode === 'page' ? 'Next' : 'Refresh history', exact: true }).click();
        await expect(retained).toBeVisible();
        if (mode !== 'empty') await expect(original).toBeVisible();
        releaseRecovery();
        await expect(page.getByText(mode === 'page' ? 'Target 10' : 'Target updated', { exact: true })).toBeVisible();
        await expect(retained).toHaveCount(0);
        await expect(page.getByRole('heading', { name: 'Healthy', exact: true })).toBeVisible();
        if (mode !== 'empty') await expect(original).toHaveCount(0);
        if (mode === 'page') await expect(page.getByText('Showing 11–11 of 11', { exact: true })).toBeVisible();
        expect(offsets).toEqual(mode === 'page' ? [0, 10, 10] : [0, 0, 0]);
        const expectedEvidenceReads = mode === 'page' ? 11 : mode === 'empty' ? 1 : 2;
        expect(lifecycleReads).toBe(expectedEvidenceReads);
        expect(diagnosticReads).toBe(expectedEvidenceReads);
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
}
