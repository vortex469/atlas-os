import { expect, test } from '@playwright/test';
import { installMissionControlMocks } from './mission-control-fixtures';
import { capability, resource } from './maintenance-selector-fixture';

for (const width of [320, 390, 1280]) {
    for (const mode of ['resources', 'server', 'network'] as const) {
        test(`maintenance ${mode} failure at ${width}px offers the right recovery without replay`, async ({ page }) => {
            const mutations: string[] = [];
            await installMissionControlMocks(page, 'available', mutations);
            await page.setViewportSize({ width, height: 900 });
            await page.clock.setFixedTime(new Date('2026-10-26T00:00:00Z'));
            let capabilityReads = 0;
            let resourceReads = 0;
            let submissions = 0;
            await page.route('**/api/v1/operator-auth/session', route => route.fulfill({
                headers: { 'x-atlas-csrf-token': 'fixture-only' },
                json: { authenticated: true, expires_at: '2999-01-01T00:00:00Z', principal: {
                    operator_id: 'browser-operator', authenticated_at: '2026-10-26T00:00:00Z',
                    permissions: ['operational_intent:create'], auth_method: 'core_session',
                } },
            }));
            await page.route('**/api/v1/execution-candidates/operator-intents**', async route => {
                const request = route.request();
                const path = new URL(request.url()).pathname;
                if (request.method() === 'POST' && path.endsWith('/operator-intents')) {
                    submissions++;
                    expect(request.headers()['x-atlas-csrf-token']).toBe('fixture-only');
                    expect(request.postDataJSON()).toEqual({ execution_intent: 'restart-service', provider_id: 'proxmox', resource_id: resource.resource_id,
                        resource_type: 'qemu', expected_target_fingerprint: resource.operational_target_fingerprint, expires_at: '2026-10-26T00:15:00.000Z' });
                    return mode === 'network' ? route.abort('failed') : route.fulfill({ status: 503, json: { detail: 'Fixture unavailable' } });
                }
                expect(request.method()).toBe('GET');
                if (path.endsWith('/resources')) {
                    resourceReads++;
                    if (mode === 'resources' && resourceReads === 1) return route.fulfill({ status: 503, json: { detail: 'Fixture unavailable' } });
                    return route.fulfill({ json: { execution_intent: 'restart-service', provider_id: 'proxmox', resource_type: 'qemu', generated_at: '2026-10-26T00:00:00Z', resources: [resource] } });
                }
                expect(path).toBe('/api/v1/execution-candidates/operator-intents/capabilities');
                capabilityReads++;
                return route.fulfill({ json: { capabilities: [capability] } });
            });
            await page.goto('/operations/request');
            if (mode === 'resources') {
                await expect(page.getByRole('alert')).toContainText('Maintenance resources are temporarily unavailable. Choose Refresh to check again.');
                await expect(page.getByRole('link', { name: 'Review change proposals', exact: true })).toHaveCount(0);
                await page.getByRole('button', { name: 'Refresh', exact: true }).click();
                await expect(page.getByRole('radio', { name: /Browser fixture VM/ })).not.toBeChecked();
                await expect(page.getByRole('alert')).toHaveCount(0);
            } else {
                await page.getByRole('radio', { name: /Browser fixture VM/ }).check();
                await page.getByRole('button', { name: 'Create restart proposal', exact: true }).click();
                await expect(page.getByRole('alert')).toContainText('outcome is unknown. Review change proposals before creating another request.');
                await expect(page.getByText('Maintenance resources are temporarily unavailable.', { exact: true })).toHaveCount(0);
                await page.getByRole('link', { name: 'Review change proposals', exact: true }).click();
                await expect(page).toHaveURL(/\/execution-candidates$/);
                await expect(page.getByRole('heading', { name: 'Change proposals', exact: true })).toBeVisible();
            }
            expect(submissions).toBe(mode === 'resources' ? 0 : 1);
            expect(capabilityReads).toBe(mode === 'resources' ? 2 : 1);
            expect(resourceReads).toBe(mode === 'resources' ? 2 : 1);
            expect(mutations).toEqual(mode === 'resources' ? [] : [`POST ${new URL('/api/v1/execution-candidates/operator-intents', page.url()).href}`]);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        });
    }
}
