import { expect, test } from './mission-control-fixtures';
import { operationalLifecycle, operationalDiagnostic } from '../src/test/operationalLifecycle';

for (const width of [320, 390, 1280]) {
    test(`history filters stay compact and expose active hidden choices at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        const reads = { list: 0, lifecycle: 0, diagnostic: 0 };
        await page.route('**/agent-api/api/v1/agent/workflows**', route => {
            expect(route.request().method()).toBe('GET');
            const path = new URL(route.request().url()).pathname;
            if (path.endsWith('/workflows')) {
                reads.list++;
                return route.fulfill({ json: { items: [{ workflow_id: 'history-filter', workflow_source: 'candidate', workflow_state: 'completed', effect_kind: 'operational_action', execution_intent: 'restart-service', target_id: '110', timeline: [] }], total: 1, limit: 10, offset: 0 } });
            }
            if (path.endsWith('/operational-lifecycle')) {
                reads.lifecycle++;
                return route.fulfill({ json: operationalLifecycle({ workflow_id: 'history-filter', target_label: 'Filter target' }) });
            }
            expect(path).toBe('/agent-api/api/v1/agent/workflows/history-filter/recovery-diagnostic');
            reads.diagnostic++;
            const diagnostic = operationalDiagnostic();
            return route.fulfill({ json: { ...diagnostic, correlation: { ...diagnostic.correlation, workflow_id: 'history-filter' } } });
        });
        await page.goto('/operations/history');
        await expect(page.getByRole('heading', { name: 'Filter target', exact: true })).toBeVisible();
        const recovery = page.getByRole('region', { name: 'Recovery summary', exact: true });
        await expect(recovery.getByRole('heading', { name: 'Healthy', exact: true })).toBeVisible();
        await expect(recovery.getByText('No recovery reason was reported.', { exact: true })).toHaveCount(0);
        await expect(recovery.getByText('Safe next action:', { exact: true }).locator('..')).toContainText('No recovery action is required.');
        await expect(recovery.getByText('consistent', { exact: true })).toHaveCount(0);
        await expect(recovery.getByText(/Read-only guidance only/)).toHaveCount(0);
        const workflowDetails = page.getByText('Workflow details', { exact: true });
        await workflowDetails.click();
        await expect(page.getByText('Consistency', { exact: true }).locator('..')).toContainText('consistent');
        await workflowDetails.click();
        const filters = page.getByRole('region', { name: 'Operational history filters', exact: true });
        const applied = page.getByRole('status', { name: 'Applied history filters', exact: true });
        await expect(filters.getByRole('combobox', { name: 'Status', exact: true })).toBeVisible();
        await expect(filters.getByRole('combobox', { name: 'Completion', exact: true })).toBeVisible();
        await expect(filters.getByLabel('Provider', { exact: true })).toBeHidden();
        expect((await filters.boundingBox())!.height).toBeLessThan(350);
        await expect(applied).toHaveText('All requests on this page.');
        const more = filters.locator('summary', { hasText: 'More filters' });
        await more.focus(); await page.keyboard.press('Enter');
        await filters.getByRole('combobox', { name: 'Action', exact: true }).selectOption('restart-service');
        await filters.getByRole('combobox', { name: 'Provider', exact: true }).selectOption('proxmox');
        await filters.getByRole('combobox', { name: 'Resource type', exact: true }).selectOption('qemu');
        await more.focus(); await page.keyboard.press('Enter');
        await expect(filters.getByLabel('Provider', { exact: true })).toBeHidden();
        await expect(applied).toHaveText('Filters on this page: Action: Restart service · Provider: Proxmox · Resource type: Virtual machine');
        await expect(page.getByRole('heading', { name: 'Filter target', exact: true })).toBeVisible();
        await filters.getByRole('combobox', { name: 'Status', exact: true }).selectOption('attention_required');
        await expect(page.getByText('No requests on this page match your filters.', { exact: true })).toBeVisible();
        await expect(page.getByRole('button', { name: 'Clear filters', exact: true })).toHaveCount(1);
        await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
        await expect(page.getByRole('heading', { name: 'Filter target', exact: true })).toBeVisible();
        await expect(applied).toHaveText('All requests on this page.');
        for (const label of ['Status', 'Completion', 'Action', 'Provider', 'Resource type']) await expect(filters.getByLabel(label, { exact: true })).toHaveValue('all');
        await expect(filters.getByLabel('Provider', { exact: true })).toBeHidden();
        expect(reads).toEqual({ list: 1, lifecycle: 1, diagnostic: 1 });
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        if (width !== 320) {
            await page.evaluate(() => scrollTo(0, 0));
            await page.screenshot({ path: `/tmp/atlas-compact-maintenance-results-${width}.png`, fullPage: true });
        }
    });
}
