import { expect, test } from './mission-control-fixtures';
import { capability, resource } from './maintenance-selector-fixture';

for (const width of [320, 390, 1280]) {
    for (const mode of ['empty', 'missing', 'failed'] as const) {
        test(`maintenance selector ${mode} recovers at ${width}px without writes`, async ({ page, rejectedMutationRequests }) => {
            await page.setViewportSize({ width, height: 900 });
            let capabilityReads = 0;
            let resourceReads = 0;
            await page.route('**/api/v1/operator-auth/session', route => route.fulfill({
                headers: { 'x-atlas-csrf-token': 'fixture-only' },
                json: { authenticated: true, expires_at: '2999-01-01T00:00:00Z', principal: {
                    operator_id: 'browser-operator', authenticated_at: '2026-10-26T00:00:00Z',
                    permissions: ['operational_intent:create'], auth_method: 'core_session',
                } },
            }));
            await page.route('**/api/v1/execution-candidates/operator-intents/capabilities**', async route => {
                expect(route.request().method()).toBe('GET');
                if (new URL(route.request().url()).pathname.endsWith('/resources')) {
                    resourceReads++;
                    return route.fulfill({ json: { execution_intent: 'restart-service', provider_id: 'proxmox', resource_type: 'qemu',
                        generated_at: '2026-10-26T00:00:00Z', resources: mode === 'empty' && resourceReads === 1 ? [] : [resource] } });
                }
                capabilityReads++;
                if (capabilityReads === 1 && mode === 'failed') return route.fulfill({ status: 503, json: { detail: 'Fixture unavailable' } });
                return route.fulfill({ json: { capabilities: capabilityReads === 1 && mode === 'missing' ? [] : [capability] } });
            });
            await page.goto('/operations/request');
            if (mode === 'empty') await expect(page.getByRole('status')).toHaveText('No resources were returned. Choose Refresh to check again.');
            else await expect(page.getByText('Maintenance unavailable', { exact: true })).toBeVisible();
            await expect(page.getByText('Loading capability', { exact: true })).toHaveCount(0);
            await expect(page.getByRole('button', { name: 'Request restart candidate', exact: true })).toBeDisabled();
            expect(capabilityReads).toBe(1);
            expect(resourceReads).toBe(mode === 'empty' ? 1 : 0);
            await page.getByRole('button', { name: 'Refresh', exact: true }).click();
            await expect(page.getByRole('radio', { name: /Browser fixture VM/ })).toBeVisible();
            await expect(page.getByRole('radio', { name: /Browser fixture VM/ })).not.toBeChecked();
            await expect(page.getByText('Maintenance unavailable', { exact: true })).toHaveCount(0);
            await expect(page.getByText('No resources were returned. Choose Refresh to check again.', { exact: true })).toHaveCount(0);
            expect(capabilityReads).toBe(2);
            expect(resourceReads).toBe(mode === 'empty' ? 2 : 1);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
            expect(rejectedMutationRequests).toEqual([]);
        });
    }
}
