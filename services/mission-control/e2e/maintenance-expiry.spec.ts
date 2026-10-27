import { expect, test } from '@playwright/test';
import { installMissionControlMocks } from './mission-control-fixtures';
import { capability, resource } from './maintenance-selector-fixture';
import { maintenanceCandidate } from './repository-journey-fixture';

for (const width of [320, 390, 1280]) {
    for (const mode of ['expires', 'unreadable'] as const) {
        test(`maintenance candidate ${mode} at ${width}px without extra requests`, async ({ page }) => {
            const observedMutations: string[] = [];
            await installMissionControlMocks(page, 'available', observedMutations);
            await page.setViewportSize({ width, height: 900 });
            await page.clock.install({ time: new Date('2026-10-26T00:00:00Z') });
            await page.clock.pauseAt(new Date('2026-10-26T00:00:00Z'));
            let capabilityReads = 0;
            let resourceReads = 0;
            const writes: unknown[] = [];
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
                    writes.push(request.postDataJSON());
                    expect(request.headers()['x-atlas-csrf-token']).toBe('fixture-only');
                    return route.fulfill({ json: { outcome: 'created', candidate_id: maintenanceCandidate.id,
                        candidate: { ...maintenanceCandidate, expires_at: mode === 'expires' ? '2026-10-26T00:01:00Z' : '2026-02-30T00:00:00Z' } } });
                }
                expect(request.method()).toBe('GET');
                if (path.endsWith('/resources')) {
                    resourceReads++;
                    return route.fulfill({ json: { execution_intent: 'restart-service', provider_id: 'proxmox', resource_type: 'qemu',
                        generated_at: '2026-10-26T00:00:00Z', resources: [resource] } });
                }
                expect(path).toBe('/api/v1/execution-candidates/operator-intents/capabilities');
                capabilityReads++;
                return route.fulfill({ json: { capabilities: [capability] } });
            });
            await page.goto('/operations/request');
            await page.getByRole('radio', { name: /Browser fixture VM/ }).check();
            await page.getByRole('button', { name: 'Request restart candidate', exact: true }).click();
            if (mode === 'expires') {
                await expect(page.getByRole('link', { name: 'Continue to candidate planning', exact: true })).toBeVisible();
                await page.clock.runFor(60_000);
                await expect(page.getByRole('heading', { name: 'Maintenance candidate expired', exact: true })).toBeVisible();
                await expect(page.getByRole('alert')).toContainText('This candidate has expired.');
            } else {
                await expect(page.getByRole('heading', { name: 'Candidate expiration unknown', exact: true })).toBeVisible();
                await expect(page.getByRole('alert')).toContainText('The candidate expiration could not be confirmed.');
            }
            await expect(page.getByRole('link', { name: 'Continue to candidate planning', exact: true })).toHaveCount(0);
            expect(capabilityReads).toBe(1);
            expect(resourceReads).toBe(1);
            expect(writes).toEqual([{ execution_intent: 'restart-service', provider_id: 'proxmox', resource_id: resource.resource_id,
                resource_type: 'qemu', expected_target_fingerprint: resource.operational_target_fingerprint, expires_at: '2026-10-26T00:15:00.000Z' }]);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
            // The shared request observer records the one explicitly simulated submission too.
            expect(observedMutations).toEqual([`POST ${new URL('/api/v1/execution-candidates/operator-intents', page.url()).href}`]);
        });
    }
}
