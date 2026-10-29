import { expect, test } from './mission-control-fixtures';

test('overview separates initial loading from unavailable data across dashboard cards', async ({ page }) => {
    let releaseAgent!: () => void;
    let releaseProviders!: () => void;
    let releaseHealth!: () => void;
    let releaseFindings!: () => void;
    let releasePolicy!: () => void;
    const agentGate = new Promise<void>(resolve => { releaseAgent = resolve; });
    const providersGate = new Promise<void>(resolve => { releaseProviders = resolve; });
    const healthGate = new Promise<void>(resolve => { releaseHealth = resolve; });
    const findingsGate = new Promise<void>(resolve => { releaseFindings = resolve; });
    const policyGate = new Promise<void>(resolve => { releasePolicy = resolve; });
    await page.route('**/agent-api/api/v1/agent/info', async route => {
        await agentGate;
        await route.fallback();
    });
    await page.route('**/api/v1/providers', async route => {
        await providersGate;
        await route.fallback();
    });
    await page.route('**/api/v1/health', async route => {
        await healthGate;
        await route.fallback();
    });
    await page.route('**/api/v1/ace/summary', async route => {
        await findingsGate;
        await route.fallback();
    });
    await page.route('**/api/v1/policies/status', async route => {
        await policyGate;
        await route.fallback();
    });
    await page.goto('/');
    const agent = page.getByRole('region', { name: 'Agent details' });
    const providers = page.getByRole('region', { name: 'Providers' });
    const healthReports = page.getByRole('region', { name: 'Health reports' });
    try {
        await expect(agent.getByText('Loading Agent details…')).toBeVisible();
        await expect(providers.getByText('Loading providers…')).toBeVisible();
        await expect(providers.getByText('Provider configuration unknown.')).toHaveCount(0);
        for (const name of ['Overall service status', 'System findings', 'Policy settings check']) {
            const report = healthReports.getByRole('article', { name });
            await expect(report.getByRole('status')).toHaveText('Checking…');
            await expect(report.getByText('Unknown', { exact: true })).toHaveCount(0);
        }
        releaseHealth();
        const attention = page.getByRole('region', { name: 'Operator Attention' });
        await expect(attention.getByRole('status')).toHaveText("Checking current reports. The attention list may change when the remaining checks finish.");
        await expect(attention).not.toContainText('Some information is missing. Atlas cannot confirm this list includes everything that needs attention.');
    } finally {
        releaseAgent();
        releaseProviders();
        releaseHealth();
        releaseFindings();
        releasePolicy();
    }
    await expect(agent.getByText('Agent', { exact: true })).toBeVisible();
    await expect(agent.getByText('Atlas Agent', { exact: true })).toBeVisible();
    await expect(agent.getByText('Version', { exact: true })).toBeVisible();
    await expect(agent.getByText('browser-fixture', { exact: true })).toBeVisible();
    await expect(providers.getByText('Saved providers and the status Atlas reports for each one.')).toBeVisible();
    await expect(healthReports.getByRole('article', { name: 'Overall service status' }).getByText('Healthy', { exact: true })).toBeVisible();
    await expect(healthReports.getByRole('article', { name: 'System findings' }).getByText('Healthy', { exact: true })).toBeVisible();
    await expect(healthReports.getByRole('article', { name: 'Policy settings check' }).getByText('Last report: Healthy.')).toBeVisible();
});

test('provider preview prioritizes problems and uses a singular extra-provider label', async ({ page, rejectedMutationRequests }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.route('**/api/v1/providers', route => route.fulfill({ json: [
        { id: 'degraded', name: 'Degraded', health: { status: 'degraded' } },
        { id: 'healthy', name: 'Healthy', health: { status: 'healthy' } },
        { id: 'offline', name: 'Offline', health: { status: 'offline' } },
        { id: 'blocked', name: 'Blocked', health: { status: 'blocked' } },
        { id: 'unknown', name: 'Unknown', health: { status: 'future_state' } },
    ] }));
    await page.goto('/');

    const providers = page.getByRole('region', { name: 'Providers', exact: true });
    await expect(providers.getByRole('article', { name: 'Blocked' })).toBeVisible();
    const visibleNames = await providers.getByRole('article').evaluateAll(items =>
        items.map(item => item.getAttribute('aria-label')));
    expect(visibleNames).toEqual(['Blocked', 'Offline', 'Degraded', 'Unknown']);
    const additional = providers.getByText('1 more provider', { exact: true });
    await additional.click();
    await expect(providers.getByRole('article', { name: 'Healthy' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(rejectedMutationRequests).toEqual([]);
});

for (const width of [320, 768, 1440]) {
    test(`overview fits ${width}px and links to existing detail routes`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto('/');
        const grid = page.getByTestId('overview-grid');
        await expect(grid.locator(':scope > section')).toHaveCount(6);
        await expect(page.getByRole('button', { name: 'Refresh', exact: true })).toBeEnabled();
        await expect(page.getByRole('region', { name: 'System health' }).getByRole('link')).toHaveCount(0);
        await expect(page.getByRole('region', { name: 'Service checks' }).getByRole('link')).toHaveCount(0);
        const policyTime = page.getByRole('article', { name: 'Policy settings check' }).locator('time');
        await expect(policyTime).toBeVisible();
        await expect(policyTime).not.toHaveText(/\d{4}-\d{2}-\d{2}T/);
        await expect(policyTime).toHaveAttribute('dateTime', /^\d{4}-\d{2}-\d{2}T/);
        const agent = page.getByRole('region', { name: 'Agent details' });
        await expect(agent.getByText('Atlas Agent', { exact: true })).toBeVisible();
        await expect(agent.getByText('browser-fixture', { exact: true })).toBeVisible();
        await expect(agent.getByRole('link', { name: 'View agent workflows' })).toHaveCount(0);
        await expect(agent.getByText('Unknown', { exact: true })).toHaveCount(0);
        await expect(agent.getByText('Evidence unknown.', { exact: true })).toHaveCount(0);
        const attention = page.getByRole('region', { name: 'Operator Attention' });
        await expect(attention.getByRole('link', { name: 'Review operational conditions →' })).toHaveCount(0);
        await expect(attention.getByRole('link', { name: 'Review workflow attention →' })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        const columns = await grid.evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length);
        expect(columns).toBe(width < 768 ? 1 : width < 1280 ? 2 : 3);
        await page.getByRole('link', { name: 'Review workflows →' }).click();
        await expect(page).toHaveURL(/\/workflows$/);
        await page.goBack();
        await page.getByRole('link', { name: 'View Proxmox →' }).click();
        await expect(page).toHaveURL(/\/providers\/proxmox$/);
        await page.goBack();
        await page.getByRole('link', { name: 'Open action history →' }).click();
        await expect(page).toHaveURL(/\/operations$/);
        await expect(page.getByRole('heading', { name: 'Action history' })).toBeVisible();
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 1280]) {
    test(`work activity explains unrecognized workflow states at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route(/\/agent-api\/api\/v1\/agent\/workflows(?:\?.*)?$/, route => route.fulfill({ json: {
            items: [{ workflow_id: "workflow-future-state", workflow_state: "future_state",
                workflow_source: "candidate", effect_kind: "repository_change",
                execution_intent: "update-compose-stack", candidate_id: null,
                planning_session_id: null, repository: null, target_id: null,
                last_result_summary: "Recorded result", timeline: [] }],
            total: 1, offset: 0, limit: 200,
        } }));
        await page.goto("/");

        const work = page.getByRole("region", { name: "Work activity" });
        await expect(work.getByText("Some workflow statuses are not recognized. Running and blocked counts are hidden.")).toBeVisible();
        await expect(work.getByText("Running workflows", { exact: true })).toHaveCount(0);
        await expect(work.getByText("Blocked workflows", { exact: true })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`operator attention names the maintenance approval at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/api/v1/agent/workflows**", route => route.fulfill({ json: {
            items: [{
                workflow_id: "maintenance-review",
                workflow_source: "candidate",
                workflow_state: "awaiting_implementation_approval",
                effect_kind: "operational_action",
                execution_intent: "restart-service",
                candidate_id: null,
                planning_session_id: null,
                repository: null,
                target_id: "VM 110",
                last_result_summary: "Waiting for implementation approval",
                timeline: [],
            }],
            total: 1,
            limit: 200,
            offset: 0,
        } }));
        await page.goto("/");

        const attention = page.getByRole("region", { name: "Operator Attention" });
        await expect(attention.getByRole("link", { name: "Restart Service", exact: true })).toHaveAttribute("href", "/workflows/maintenance-review");
        await expect(attention.getByText("Action needed: Review the maintenance request. If approved, choose Run approved maintenance.", { exact: true })).toBeVisible();
        await expect(attention.getByText("Waiting for implementation approval", { exact: true })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

test('Atlas Doctor stays collapsed under System health until an operator runs it', async ({ page, rejectedMutationRequests }) => {
    let doctorReads = 0;
    await page.route('**/api/v1/ops/doctor', route => {
        doctorReads += 1;
        return route.fulfill({ json: {
            status: 'healthy', score: 100, checked_at: '2026-10-28T12:00:00Z',
            configuration_ok: true,
            checks: [{ name: 'Core', passed: true, error: null }],
            critical: [], warnings: [], information: [],
        } });
    });
    await page.goto('/');
    const health = page.getByRole('region', { name: 'System health' });
    const disclosure = health.locator('details').filter({ hasText: 'Use Atlas Doctor' });
    const doctorButton = disclosure.locator('button', { hasText: 'Run Doctor' });
    await expect(disclosure.locator('summary')).toBeVisible();
    await expect(disclosure).not.toHaveAttribute('open', '');
    await expect(doctorButton).toBeHidden();
    expect(doctorReads).toBe(0);

    await disclosure.locator('summary').click();
    await expect(doctorButton).toBeVisible();
    expect(doctorReads).toBe(0);
    await doctorButton.click();
    await expect.poll(() => doctorReads).toBe(1);
    await expect(disclosure.getByText('100/100')).toBeVisible();
    expect(rejectedMutationRequests).toEqual([]);
});

test('service check summary reveals every reported check on mobile', async ({ page, rejectedMutationRequests }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.route('**/api/v1/health', route => route.fulfill({ json: {
        atlas: 'healthy',
        services: Object.fromEntries(Array.from({ length: 6 }, (_, index) => [`service-${index}`, {
            status: 'healthy',
            message: `Service ${index} is reachable.`,
        }])),
    } }));
    await page.goto('/');

    const checks = page.getByRole('region', { name: 'Service checks', exact: true });
    const serviceChecks = checks.getByRole('list', { name: 'Configured service checks' });
    const serviceItems = serviceChecks.locator(':scope > li');
    await expect(serviceItems).toHaveCount(4);
    await checks.getByRole('button', { name: 'Show all 6 service checks' }).click();
    await expect(serviceItems).toHaveCount(6);
    await expect(checks.getByText('service-5')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

    await checks.getByRole('button', { name: 'Show fewer service checks' }).click();
    await expect(serviceItems).toHaveCount(4);
    expect(rejectedMutationRequests).toEqual([]);
});

test('service check preview puts blocked and offline services first', async ({ page, rejectedMutationRequests }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.route('**/api/v1/health', route => route.fulfill({ json: {
        atlas: 'degraded',
        services: {
            Degraded: { status: 'degraded' },
            Healthy: { status: 'healthy' },
            Offline: { status: 'offline' },
            Blocked: { status: 'blocked' },
            Unknown: { status: 'future_state' },
        },
    } }));
    await page.goto('/');

    const checks = page.getByRole('region', { name: 'Service checks', exact: true });
    const serviceChecks = checks.getByRole('list', { name: 'Configured service checks' });
    const visibleNames = await serviceChecks.locator(':scope > li').evaluateAll(items =>
        items.map(item => item.querySelector('p')?.textContent));
    expect(visibleNames).toEqual(['Blocked', 'Offline', 'Degraded', 'Unknown']);
    await checks.getByRole('button', { name: 'Show all 5 service checks' }).click();
    await expect(checks.getByRole('listitem').nth(4)).toContainText('Healthy');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(rejectedMutationRequests).toEqual([]);
});

for (const width of [320, 1280]) {
    test(`shows the empty service-check explanation once at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 800 });
        await page.route('**/api/v1/health', route => route.fulfill({ json: {
            atlas: 'healthy',
            services: {},
        } }));
        await page.goto('/');

        const message = 'No configured service checks were reported.';
        const serviceChecks = page.getByRole('region', { name: 'Service checks', exact: true });
        const systemHealth = page.getByRole('region', { name: 'System health', exact: true });
        await expect(serviceChecks.getByText(message, { exact: true })).toBeVisible();
        await expect(systemHealth.getByText(message, { exact: true })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 1280]) {
    test(`service check explains where Atlas tested iFileshare and what to check next at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 800 });
        await page.route('**/api/v1/health', route => route.fulfill({ json: {
            atlas: 'degraded',
            services: { iFileshare: {
                status: 'offline',
                message: '[Errno 113] No route to host',
                details: { url: 'http://10.10.60.30:8080/', critical: false },
            } },
        } }));
        await page.goto('/');

        const attention = page.getByRole('region', { name: 'Operator Attention', exact: true });
        const serviceCondition = attention.getByRole('list', { name: 'Reported attention conditions' }).getByRole('listitem');
        await expect(serviceCondition.getByText('Atlas Core could not connect', { exact: true })).toBeVisible();
        await expect(serviceCondition.getByText('Unavailable', { exact: true })).toHaveCount(0);

        const checks = page.getByRole('region', { name: 'Service checks', exact: true });
        await expect(checks.getByText('iFileshare', { exact: true })).toBeVisible();
        await expect(checks.getByText('Atlas Core could not connect', { exact: true })).toBeVisible();
        const nextStep = checks.getByRole('group', { name: 'Next connection check' });
        await expect(nextStep).toBeVisible();
        await expect(nextStep).toContainText('Try this address from the Atlas Core machine or container:');
        await expect(nextStep.getByText('http://10.10.60.30:8080/', { exact: true })).toBeVisible();
        await expect(nextStep).toContainText('A blank PORTS field means no host port is published for Atlas Core to reach.');
        const moreChecks = checks.getByText('More connection checks');
        await moreChecks.click();
        const steps = checks.getByRole('list', { name: 'How to check from Atlas Core' });
        await expect(steps.getByRole('listitem')).toHaveCount(3);
        await expect(steps).toHaveCSS('font-size', '14px');
        await expect(steps).toContainText('Test from the Atlas Core machine or atlas-core container');
        await expect(steps).toContainText('A browser or the service computer may use a different network path');
        await expect(steps).toContainText('On another computer running Docker, use docker ps and check PORTS');
        await expect(steps).toContainText('a mapping starting with 127.0.0.1: is reachable only from that computer');
        await expect(steps).toContainText("publish the app's listening port with Compose's ports: or docker run -p");
        await expect(steps).toContainText('HOST_PORT:CONTAINER_PORT');
        await expect(steps).toContainText('Run Compose commands from the folder containing the Compose file');
        await expect(checks.getByText('HTTP response: No response received', { exact: true })).toBeVisible();
        await expect(checks.getByText('Next check: Check the target address and the network or firewall route from Atlas Core to the service host.', { exact: true })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

test('work activity reveals all workflow records on mobile without horizontal overflow', async ({ page, rejectedMutationRequests }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    const workflows = [
        ...Array.from({ length: 5 }, (_, index) => ({ workflow_id: `running-${index}`, workflow_state: 'executing', execution_intent: 'restart-service', timeline: [{ name: 'Execution', status: 'current' }] })),
        ...Array.from({ length: 5 }, (_, index) => ({ workflow_id: `blocked-${index}`, workflow_state: 'blocked', execution_intent: 'restart-service', timeline: [{ name: 'Execution', status: 'waiting' }] })),
        ...Array.from({ length: 5 }, (_, index) => ({ workflow_id: `outcome-${index}`, workflow_state: 'completed', execution_intent: 'restart-service', timeline: [{ name: 'Execution', status: 'completed' }] })),
    ].map(workflow => ({
        ...workflow,
        workflow_source: 'candidate',
        effect_kind: 'repository_change',
        candidate_id: null,
        planning_session_id: null,
        repository: null,
        target_id: null,
        last_result_summary: 'Recorded workflow result',
    }));
    await page.route(/\/agent-api\/api\/v1\/agent\/workflows(?:\?.*)?$/, route => route.fulfill({ json: {
        items: workflows, total: workflows.length, offset: 0, limit: 200,
    } }));
    await page.goto('/');

    const section = page.getByRole('region', { name: 'Work activity' });
    await expect(section.getByText('Counts and results come from recorded workflows. This summary is read-only.')).toBeVisible();
    const running = section.getByRole('list', { name: 'Running workflows' });
    await expect(running.getByRole('listitem')).toHaveCount(3);
    await section.getByRole('button', { name: 'Show all 5 running workflows' }).click();
    await expect(running.getByRole('listitem')).toHaveCount(5);

    const blocked = section.getByRole('list', { name: 'Blocked workflows' });
    await section.getByRole('button', { name: 'Show all 5 blocked workflows' }).click();
    await expect(blocked.getByRole('listitem')).toHaveCount(5);

    await section.getByText('More about execution data').click();
    const outcomes = section.getByRole('list', { name: 'Recorded execution outcomes' });
    await section.getByRole('button', { name: 'Show all 5 recorded execution outcomes' }).click();
    await expect(outcomes.getByRole('listitem')).toHaveCount(5);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(rejectedMutationRequests).toEqual([]);
});

test('work activity shows failed outcomes before completed outcomes in its preview', async ({ page, rejectedMutationRequests }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    const workflows = [
        { workflow_id: 'a-completed', workflow_state: 'completed', execution_intent: 'restart-service', stage: 'completed' },
        { workflow_id: 'b-completed', workflow_state: 'completed', execution_intent: 'restart-service', stage: 'completed' },
        { workflow_id: 'c-completed', workflow_state: 'completed', execution_intent: 'restart-service', stage: 'completed' },
        { workflow_id: 'z-failed', workflow_state: 'blocked', execution_intent: 'update-compose-stack', stage: 'failed' },
    ].map(workflow => ({
        workflow_id: workflow.workflow_id,
        workflow_state: workflow.workflow_state,
        execution_intent: workflow.execution_intent,
        workflow_source: 'candidate',
        effect_kind: 'repository_change',
        candidate_id: null,
        planning_session_id: null,
        repository: null,
        target_id: null,
        last_result_summary: 'Recorded workflow result',
        timeline: [{ name: 'Execution', status: workflow.stage }],
    }));
    await page.route(/\/agent-api\/api\/v1\/agent\/workflows(?:\?.*)?$/, route => route.fulfill({ json: {
        items: workflows, total: workflows.length, offset: 0, limit: 200,
    } }));
    await page.goto('/');

    const work = page.getByRole('region', { name: 'Work activity' });
    await work.getByText('More about execution data').click();
    const outcomes = work.getByRole('list', { name: 'Recorded execution outcomes' });
    const first = outcomes.getByRole('listitem').first();
    await expect(first.getByRole('link', { name: 'Update Compose Stack · Execution failed' })).toBeVisible();
    await expect(work.getByRole('button', { name: 'Show all 4 recorded execution outcomes' })).toBeVisible();
    expect(rejectedMutationRequests).toEqual([]);
});

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
    await expect(page.getByRole('article', { name: 'Overall service status' }).getByText('Status unknown', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await attention.getByRole('link', { name: 'API', exact: true }).click();
    await expect(page).toHaveURL(/\/providers\/proxmox$/);
    await expect(page.getByText('Supported provider features could not be loaded. Some provider sections are hidden.')).toBeVisible();
    await expect(page.getByText('Features unavailable.')).toBeVisible();
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
    await expect(attention.getByText('Action needed: Review the change. If approved, choose Run approved change.', { exact: true })).toBeVisible();
    await expect(attention.getByRole('link', { name: 'Update Compose Stack' })).toBeVisible();
    await expect(attention.getByText('Review each item and use its link to see the details.')).toHaveCount(0);
    const workflowId = attention.getByText('workflow-browser-baseline', { exact: true });
    await expect(workflowId).toBeHidden();
    await attention.getByText('Technical details', { exact: true }).click();
    await expect(workflowId).toBeVisible();
    await attention.getByText('Technical details', { exact: true }).click();
    await expect(attention.getByText('Degraded', { exact: true })).toHaveCount(0);
    const runtime = page.getByRole('region', { name: 'AI provider' });
    await expect(runtime.getByText('Provider details are unavailable.')).toBeVisible();
    await expect(runtime.getByText('Use Refresh to try again.')).toHaveCount(0);
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
        const coreReport = health.getByRole('article', { name: 'Overall service status' });
        await expect(coreReport).toBeVisible();
        const reportBox = await coreReport.boundingBox();
        const guidanceBox = await health.getByText('How to read health').boundingBox();
        expect(reportBox!.y).toBeLessThan(guidanceBox!.y);
        await expect(health.getByText(/overall check time/)).toBeHidden();
        await health.getByText('How to read health').click();
        await expect(health.getByText(/Core does not supply an overall check time/)).toBeVisible();
        const checks = page.getByRole('region', { name: 'Service checks', exact: true });
        const explanation = checks.getByText('These checks show whether Atlas Core can reach each configured service. They do not show whether Atlas Core itself is healthy.');
        await expect(explanation).toBeHidden();
        await checks.getByText('About service checks').click();
        await expect(explanation).toBeVisible();
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
