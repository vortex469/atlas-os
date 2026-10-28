import { expect, test } from './mission-control-fixtures';
for (const width of [320, 768, 1440]) {
    test(`overview fits ${width}px and links to existing detail routes`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto('/');
        const grid = page.getByTestId('overview-grid');
        await expect(grid.locator(':scope > section')).toHaveCount(6);
        await expect(page.getByRole('button', { name: 'Refresh', exact: true })).toBeEnabled();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        const columns = await grid.evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length);
        expect(columns).toBe(width < 768 ? 1 : width < 1280 ? 2 : 3);
        if (width === 1440) await page.screenshot({ path: '/tmp/atlas-plain-worker-1440.png', fullPage: true });
        await page.getByRole('link', { name: 'Inspect executions →' }).click();
        await expect(page).toHaveURL(/\/workflows$/);
        await page.goBack();
        await page.getByRole('link', { name: 'Inspect Proxmox →' }).click();
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
        { id: 'proxmox', name: 'Proxmox', health: { status: 'warning', message: 'Capacity limited' } },
    ] }));
    await page.goto('/');
    const attention = page.getByRole('region', { name: 'Operator Attention' });
    await expect(attention.getByText('Endpoint offline')).toBeVisible();
    await expect(attention.getByText('Capacity limited')).toBeVisible();
    await expect(page.getByRole('region', { name: 'System status' }).getByText('Unknown', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await attention.getByRole('link', { name: 'API', exact: true }).click();
    await expect(page).toHaveURL(/\/providers\/proxmox$/);
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
    await expect(attention.getByText('Workflow stage: Awaiting Implementation Approval', { exact: true })).toBeHidden();
    const workflow = attention.getByRole('link', { name: 'Update Compose Stack', exact: true });
    const workflowItem = workflow.locator('..');
    await expect(workflowItem.getByText('Workflow ID: workflow-browser-baseline', { exact: true })).toBeHidden();
    await workflowItem.getByText('Workflow details', { exact: true }).click();
    await expect(workflowItem.getByText('Workflow stage: Awaiting Implementation Approval', { exact: true })).toBeVisible();
    await expect(workflowItem.getByText('Workflow ID: workflow-browser-baseline', { exact: true })).toBeVisible();
    await workflowItem.getByText('Workflow details', { exact: true }).click();
    await expect(attention.getByText('Degraded', { exact: true })).toHaveCount(0);
    const runtime = page.getByRole('region', { name: 'AI provider' });
    await expect(runtime.getByRole('heading', { name: 'AI provider', exact: true })).toBeVisible();
    await expect(runtime.getByText('Selected model: Not reported.', { exact: true })).toBeHidden();
    await expect(runtime.getByText(/does not confirm that AI is available on this computer/)).toBeVisible();
    await expect(runtime.getByText('Runtime version', { exact: true })).toBeHidden();
    const agent = page.getByRole('region', { name: 'Agent state', exact: true });
    const identity = agent.getByText('atlas-agent · browser-fixture', { exact: true });
    await expect(identity).toBeHidden();
    await expect(agent.getByText('Unknown', { exact: true })).toBeVisible();
    await expect(agent.getByRole('link', { name: 'View agent workflows', exact: true })).toBeVisible();
    const agentToggle = agent.getByText('Agent details', { exact: true });
    await agentToggle.focus();
    await page.keyboard.press('Enter');
    await expect(identity).toBeVisible();
    await expect(agent.getByText(/The name and version do not show whether it can run workflows/)).toBeVisible();
    await page.keyboard.press('Enter');
    await expect(identity).toBeHidden();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath('dashboard-default.png'), fullPage: true });
    await page.screenshot({ path: '/tmp/atlas-plain-worker-390.png', fullPage: true });
    const runtimeToggle = runtime.locator('summary', { hasText: 'AI details' });
    await runtimeToggle.focus();
    await page.keyboard.press('Enter');
    await expect(runtime.getByText('Runtime version', { exact: true })).toBeVisible();
    await expect(runtime.getByText('Selected model: Not reported.', { exact: true })).toBeVisible();
    const worker = page.getByRole('region', { name: 'Worker / Execution' });
    await expect(worker.getByText('Worker availability and queue size are not reported.', { exact: true })).toBeVisible();
    await expect(worker.getByText('No executing workflows are listed. This does not confirm that a worker is idle.', { exact: true })).toBeHidden();
    await expect(worker.getByText('Past execution outcomes', { exact: true })).toBeHidden();
    const workerToggle = worker.locator('summary', { hasText: 'Execution details' });
    await workerToggle.focus();
    await page.keyboard.press('Enter');
    await expect(worker.getByText('Past execution outcomes', { exact: true })).toBeVisible();
    await expect(worker.getByText('No executing workflows are listed. This does not confirm that a worker is idle.', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
