import { expect, test } from './mission-control-fixtures';
for (const width of [320, 768, 1440]) {
    test(`overview fits ${width}px and links to existing detail routes`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto('/');
        const grid = page.getByTestId('overview-grid');
        await expect(grid.locator(':scope > section')).toHaveCount(6);
        await expect(page.getByRole('button', { name: 'Refresh', exact: true })).toBeEnabled();
        const policyTime = page.getByRole('article', { name: 'Policy settings check' }).locator('time');
        await expect(policyTime).toBeVisible();
        await expect(policyTime).not.toHaveText(/\d{4}-\d{2}-\d{2}T/);
        await expect(policyTime).toHaveAttribute('dateTime', /^\d{4}-\d{2}-\d{2}T/);
        const agent = page.getByRole('region', { name: 'Agent details' });
        await expect(agent.getByText('Agent details do not include health or workflow status.')).toBeVisible();
        await expect(agent.getByText('Unknown', { exact: true })).toHaveCount(0);
        await expect(agent.getByText('Evidence unknown.', { exact: true })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        const columns = await grid.evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length);
        expect(columns).toBe(width < 768 ? 1 : width < 1280 ? 2 : 3);
        await page.getByRole('link', { name: 'Review workflows →' }).click();
        await expect(page).toHaveURL(/\/workflows$/);
        await page.goBack();
        await page.getByRole('link', { name: 'View Proxmox →' }).click();
        await expect(page).toHaveURL(/\/providers\/proxmox$/);
        await page.goBack();
        await page.getByRole('link', { name: 'Open operational history →' }).click();
        await expect(page).toHaveURL(/\/operations\/history$/);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

test('narrow overview preserves unknown evidence and distinct attention conditions', async ({ page, rejectedMutationRequests }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.route('**/health', route => route.fulfill({ json: {
        atlas: null, services: { API: { provider_id: 'proxmox', status: 'offline', message: 'Endpoint offline' } },
    } }));
    await page.route('**/providers', route => route.fulfill({ json: [
        { id: 'proxmox', name: 'Proxmox', workspace: 'operations', priority: 'critical', version: 'fixture-v1', description: 'Virtualization provider fixture.', icon: 'server', health: { status: 'warning', message: 'Capacity limited', details: {} } },
    ] }));
    await page.goto('/');
    const attention = page.getByRole('region', { name: 'Operator Attention' });
    await expect(attention.getByText('Endpoint offline')).toBeVisible();
    await expect(attention.getByText('Reported status: offline', { exact: true })).toHaveCount(0);
    await expect(attention.getByText('Check time unavailable.', { exact: true })).toHaveCount(0);
    await expect(attention.getByText('Capacity limited')).toBeVisible();
    await expect(page.getByRole('article', { name: 'Atlas Core health' }).getByText('Unknown', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await attention.getByRole('link', { name: 'API', exact: true }).click();
    await expect(page).toHaveURL(/\/providers\/proxmox$/);
    await expect(page.getByText('Supported provider features could not be loaded. Some provider sections are hidden.')).toBeVisible();
    await expect(page.getByText('Capabilities unavailable.')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Diagnostics' })).toBeVisible();
    await expect(page.getByText('No actions are available for this provider.')).toBeVisible();
    expect(rejectedMutationRequests).toEqual([]);
});

test('mobile attention includes configured AI failure and follows its provider route', async ({ page, rejectedMutationRequests }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.route('**/ai/status', route => route.fulfill({ json: {
        provider: { id: 'proxmox', name: 'Configured runtime' },
        health: { status: 'offline', message: 'Runtime endpoint unavailable' },
    } }));
    await page.goto('/');
    const attention = page.getByRole('region', { name: 'Operator Attention' });
    await expect(attention.getByText('Runtime endpoint unavailable')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await attention.getByRole('link', { name: 'Configured runtime', exact: true }).click();
    await expect(page).toHaveURL(/\/providers\/proxmox$/);
    expect(rejectedMutationRequests).toEqual([]);
});

test('overview puts decisions first and keeps secondary observations keyboard accessible', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'Refresh', exact: true })).toBeEnabled();
    const attention = page.getByRole('region', { name: 'Operator Attention' });
    const grid = page.getByTestId('overview-grid');
    const attentionBox = await attention.boundingBox();
    const gridBox = await grid.boundingBox();
    expect(attentionBox!.y + attentionBox!.height).toBeLessThanOrEqual(gridBox!.y);
    await expect(attention.getByText('Human action required', { exact: true })).toBeVisible();
    await expect(attention.getByRole('link', { name: 'Update Compose Stack · Waiting for implementation approval' })).toBeVisible();
    const workflowId = attention.getByText('workflow-browser-baseline', { exact: true });
    await expect(workflowId).toBeHidden();
    await attention.getByText('Technical details', { exact: true }).click();
    await expect(workflowId).toBeVisible();
    await attention.getByText('Technical details', { exact: true }).click();
    await expect(attention.getByText('Degraded', { exact: true })).toHaveCount(0);
    const runtime = page.getByRole('region', { name: 'AI provider' });
    await expect(runtime.getByText('AI provider information could not be loaded. Use Refresh to try again.')).toBeVisible();
    await expect(runtime.getByText('Current information could not be loaded.', { exact: true })).toHaveCount(0);
    await expect(runtime.getByText('Unknown', { exact: true })).toHaveCount(0);
    await expect(runtime.locator('summary', { hasText: 'Technical details' })).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath('dashboard-default.png'), fullPage: true });
    const providers = page.getByRole('region', { name: 'Providers' });
    await expect(providers.getByText('Saved providers and the status Atlas reports for each one.')).toBeVisible();
    await expect(providers.getByText(/actions are allowed/)).toBeHidden();
    await expect(providers.getByText(/which model an Agent uses/)).toHaveCount(0);
    const providerToggle = providers.locator('summary', { hasText: 'About provider status' });
    await providerToggle.focus();
    await page.keyboard.press('Enter');
    await expect(providers.getByText(/actions are allowed/)).toBeVisible();
    const worker = page.getByRole('region', { name: 'Work activity' });
    await expect(worker.getByText('Recorded execution outcomes', { exact: true })).toBeHidden();
    await expect(worker.getByText('Queue size', { exact: true })).toBeHidden();
    await expect(worker.getByText('Atlas does not report whether a worker is available.', { exact: true })).toBeVisible();
    await expect(worker.getByText('No running workflows are listed.', { exact: true })).toBeVisible();
    await expect(worker.getByText('No running workflows are listed. Worker availability is unknown.', { exact: true })).toHaveCount(0);
    const workerToggle = worker.locator('summary', { hasText: 'More about execution data' });
    await workerToggle.focus();
    await page.keyboard.press('Enter');
    await expect(worker.getByText('Recorded execution outcomes', { exact: true })).toBeVisible();
    await expect(worker.getByText('Queue size', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

for (const width of [390, 1280]) {
    test(`health explanations stay available without crowding the dashboard at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto('/');
        const health = page.getByRole('region', { name: 'System health', exact: true });
        await expect(health.getByRole('article', { name: 'Atlas Core health' })).toBeVisible();
        await expect(health.getByText(/overall check time/)).toBeHidden();
        await health.getByText('How to read health').click();
        await expect(health.getByText(/Core does not supply an overall check time/)).toBeVisible();
        const core = page.getByRole('region', { name: 'Core health', exact: true });
        await expect(core.getByText(/Core process health is not reported separately/)).toBeHidden();
        await core.getByText('About Core health').click();
        await expect(core.getByText(/Core process health is not reported separately/)).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [390, 1280]) {
    test(`work activity names the action and keeps workflow IDs optional at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route('**/agent-api/api/v1/agent/workflows**', route => route.fulfill({ json: {
            items: [{
                workflow_id: 'workflow-running-1', workflow_source: 'candidate',
                workflow_state: 'executing', effect_kind: 'repository_change',
                execution_intent: 'restart-service', candidate_id: null,
                planning_session_id: null, repository: null, target_id: null,
                last_result_summary: 'Execution is in progress.',
                timeline: [{ name: 'Execution', status: 'current' }],
            }],
            total: 1, limit: 200, offset: 0,
        } }));
        await page.goto('/');

        const work = page.getByRole('region', { name: 'Work activity' });
        await expect(work.getByRole('link', { name: 'Restart Service · Running' })).toBeVisible();
        const workflowId = work.getByText('Workflow ID: workflow-running-1');
        await expect(workflowId).toBeHidden();
        await work.getByText('Technical details', { exact: true }).click();
        await expect(workflowId).toBeVisible();
        await expect(work.getByText('executing', { exact: true })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
