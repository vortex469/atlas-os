import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Overview } from "./MissionControl";
import { safeText, timestamp, status, detailPath } from "./overviewEvidence";
import type { OverviewEvidence } from "./useOverviewEvidence";
const show = (evidence: OverviewEvidence = {}, loading = false) => render(<MemoryRouter><Overview evidence={evidence} loading={loading} /></MemoryRouter>);
const activity = () => within(screen.getByRole('region', { name: 'Recent Activity' }));

describe("MC overview evidence", () => {
    it.each(['awaiting_implementation_approval', 'awaiting_verification_approval', 'awaiting_commit_approval'])("shows %s as a workflow decision rather than degraded health", workflow_state => {
        show({ workflows: { data: { items: [{ workflow_id: 'review-me', workflow_state, last_result_summary: 'Review the exact request', timeline: [] }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByText('Human action required')).toBeVisible();
        const expectedStage = workflow_state === 'awaiting_implementation_approval'
            ? 'Waiting for implementation approval'
            : workflow_state === 'awaiting_verification_approval'
                ? 'Waiting for verification approval'
                : 'Waiting for commit approval';
        expect(attention.getByRole('link', { name: `Workflow · ${expectedStage}` })).toHaveAttribute('href', '/workflows/review-me');
        const workflowId = attention.getByText('review-me');
        expect(workflowId).not.toBeVisible();
        fireEvent.click(attention.getByText('Technical details'));
        expect(workflowId).toBeVisible();
        expect(attention.queryByText('Degraded', { exact: true })).not.toBeInTheDocument();
    });

    it('names a workflow attention item by its proposed action and keeps its ID in technical details', () => {
        show({ workflows: { data: { items: [{
            workflow_id: 'workflow-123', workflow_state: 'awaiting_verification_approval',
            execution_intent: 'update-compose-stack', last_result_summary: 'Review the exact verification', timeline: [],
        }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByRole('link', { name: 'Update Compose Stack · Waiting for verification approval' })).toHaveAttribute('href', '/workflows/workflow-123');
        expect(attention.getByText('Review the exact verification')).toBeVisible();
        const workflowId = attention.getByText('workflow-123');
        expect(workflowId).not.toBeVisible();
        fireEvent.click(attention.getByText('Technical details'));
        expect(workflowId).toBeVisible();
    });

    it('does not repeat an approval stage already named by the workflow link', () => {
        show({ workflows: { data: { items: [{
            workflow_id: 'review-me', workflow_state: 'awaiting_implementation_approval',
            execution_intent: 'update-compose-stack', last_result_summary: 'Waiting for implementation approval', timeline: [],
        }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByRole('link', { name: 'Update Compose Stack · Waiting for implementation approval' })).toBeVisible();
        expect(attention.getByText('Human action required')).toBeVisible();
        expect(attention.queryByText('Waiting for implementation approval', { exact: true })).not.toBeInTheDocument();
        expect(attention.queryByText('Review each item and use its link to see the details.')).not.toBeInTheDocument();
    });

    it('keeps a stale approval requirement explicitly last-known', () => {
        show({ workflows: { stale: true, unavailable: true, data: { items: [{ workflow_id: 'old-review', workflow_state: 'awaiting_implementation_approval', last_result_summary: 'Previous review request', timeline: [] }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByText('Last-known human action required; current requirement unknown.')).toBeVisible();
        expect(attention.getByRole('link', { name: 'Last known · Workflow · Waiting for implementation approval' })).toBeVisible();
        expect(attention.queryByText('Human action required', { exact: true })).not.toBeInTheDocument();
        expect(attention.queryByText('Degraded', { exact: true })).not.toBeInTheDocument();
    });

    it.each([['healthy','healthy'], ['online','healthy'], ['warning','degraded'], ['critical','degraded'], ['offline','unavailable'], ['blocked','blocked'], ['idle','unknown'], ['executing','unknown'], [null,'unknown'], [{},'unknown'], [true,'unknown']])("maps %s without granting authority", (input, expected) => expect(status(input)).toBe(expected));
    it("keeps all six cards and unknown evidence visible", () => {
        show();
        for (const name of ['System health','Core health','Work activity','Agent details','AI provider','Providers','Operator Attention','Recent Activity']) expect(screen.getByRole('region', { name })).toBeInTheDocument();
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
        expect(screen.getByTestId('overview-grid')).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'xl:grid-cols-3');
        expect(screen.getByText("Workflow status is unknown or incomplete.")).toBeInTheDocument();
    });
    it('keeps health source limitations available without crowding the dashboard scan', () => {
        show({ health: { data: { atlas: 'healthy', services: { api: { status: 'healthy' } } } } });
        const health = within(screen.getByRole('region', { name: 'System health' }));
        const report = health.getByRole('article', { name: 'Atlas Core health' });
        const guidance = health.getByText('How to read health');
        expect(report).toBeVisible();
        expect(report.compareDocumentPosition(guidance) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
        expect(health.queryByText(/overall check time/)).not.toBeVisible();
        fireEvent.click(health.getByText('How to read health'));
        expect(health.getByText(/Core does not supply an overall check time/)).toBeVisible();
        expect(health.getByText(/does not calculate one overall score/)).toBeVisible();

        const core = within(screen.getByRole('region', { name: 'Core health' }));
        const coreLimit = core.getByText(/Core process health is not reported separately/);
        expect(coreLimit).not.toBeVisible();
        fireEvent.click(core.getByText('About Core health'));
        expect(coreLimit).toBeVisible();
    });
    it("shows a checking state instead of an empty result during the first load", () => {
        show({}, true);
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByText('Checking current information…')).toBeVisible();
        expect(attention.queryByText('The current reports show no items needing attention.')).not.toBeInTheDocument();
        expect(attention.queryByText('System findings: Evidence unknown.')).not.toBeInTheDocument();
        expect(within(screen.getByRole('region', { name: 'Core health' })).getByText('Checking Core health…')).toBeVisible();
        expect(activity().getByText('Checking recent activity…')).toBeVisible();
        expect(screen.queryByText('No current information is available.')).not.toBeInTheDocument();
    });
    it("reports no attention only after all current sources are checked", () => {
        show({
            summary: { data: { findings: [] } },
            health: { data: { atlas: 'healthy', services: {} } },
            providers: { data: [] },
            ai: { data: { health: { status: 'healthy' } } },
            workflows: { data: { items: [], total: 0, offset: 0, limit: 200 } },
        });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByText('The current reports show no items needing attention.')).toBeVisible();
        expect(attention.queryByText(/cannot confirm whether attention is needed/)).not.toBeInTheDocument();
    });
    it("does not report missing subsystem health after the Core health read fails", () => {
        show({ health: { unavailable: true } });
        const summary = within(screen.getByRole('region', { name: 'System health' }));
        expect(summary.getByText('Current information could not be loaded.')).toBeInTheDocument();
        expect(summary.queryByText('Core did not report subsystem health.')).not.toBeInTheDocument();
    });
    it("does not repeat an incomplete-workflow warning when the source is unavailable", () => {
        show({
            summary: { data: { findings: [] } },
            workflows: { unavailable: true },
            health: { data: { atlas: 'healthy', services: {} } },
            providers: { data: [] },
            ai: { data: { health: { status: 'healthy' } } },
        });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByText('Workflows: Current information could not be loaded.')).toBeVisible();
        expect(attention.queryByText('Workflow results are incomplete.')).not.toBeInTheDocument();
        expect(attention.getByText('Some information is missing. Atlas cannot confirm whether attention is needed.')).toBeVisible();
    });
    it("handles malformed values without success or a crash", () => {
        show({ health: { data: { atlas: {}, services: { broken: null } } }, providers: { data: [null, { health: { status: 23 } }] }, workflows: { data: { items: [null] } }, ai: { data: { health: { status: [] } } }, activity: { data: { items: [null] } } });
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
        expect(screen.getByText('Some recent activity records could not be read.')).toBeInTheDocument();
    });
    it("presents reported state, reasons, providers and safe detail links; deduplicates subsystem attention", () => {
        show({ health: { data: { atlas: 'degraded', services: { Beta: { provider_id: 'beta', status: 'offline', message: 'Connection refused' } } } }, providers: { data: [{ id: 'alpha', name: 'Alpha', health: { status: 'healthy' }, secret: 'private-credential' }, { id: 'beta', name: 'Beta', health: { status: 'offline', message: 'Connection refused', details: { token: 'private-credential' } } }] }, workflows: { data: { items: [{ workflow_id: 'w/1', workflow_state: 'blocked', last_result_summary: 'Approval expired' }, { workflow_id: 'w2', workflow_state: 'executing' }] } } });
        expect(screen.getByRole('link', { name: 'View Alpha →' })).toHaveAttribute('href', '/providers/alpha');
        expect(screen.getByRole('link', { name: 'Workflow · Blocked' })).toHaveAttribute('href', '/workflows/w%2F1');
        expect(within(screen.getByRole('region', { name: 'Operator Attention' })).getAllByText('Beta')).toHaveLength(1);
        expect(screen.getByText("Workflow status is unknown or incomplete.")).toBeInTheDocument();
        expect(screen.queryByText(/private-credential/)).not.toBeInTheDocument();
    });
    it.each(['healthy','unavailable','unknown'])('shows configured AI %s without asserting locality', (value) => {
        show({ ai: { data: { provider: { id: 'runtime', name: 'Runtime' }, health: { status: value } } } });
        const card = screen.getByRole('region', { name: 'AI provider' });
        expect(within(card).getAllByText(value[0].toUpperCase() + value.slice(1)).length).toBeGreaterThan(0);
        expect(within(card).getByText(/Atlas does not report where this provider runs/)).toBeInTheDocument();
    });
    it("marks failed refresh evidence stale and never displays cached health as current", () => {
        show({ health: { data: { atlas: 'healthy' }, stale: true, unavailable: true }, activity: { stale: true, data: { items: [{ id:'a', action_label:'Restart', completed_at:'2020-01-01T00:00:00Z', status:'succeeded' }] } } });
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
        expect(screen.getAllByText(/Refresh failed/).length).toBeGreaterThan(0);
        expect(activity().getByText(/Past provider actions and their recorded results\. These do not show current system health or alerts\./)).toBeVisible();
        expect(activity().queryByText(/Historical evidence/)).not.toBeInTheDocument();
    });
    it("handles empty lists and links to existing routes", () => {
        show({ providers: { data: [] }, activity: { data: { items: [] } }, workflows: { data: { items: [] } } });
        expect(screen.getByText('No providers configured.')).toBeInTheDocument();
        expect(screen.getByText('No recent actions recorded.')).toBeInTheDocument();
        for (const [name, href] of [['Open operations →','/operations'], ['Review workflows →','/workflows'], ['Open deployment analysis →','/forge'], ['Open operational history →','/operations/history']]) expect(screen.getByRole('link', { name })).toHaveAttribute('href', href);
    });
    it("rejects bad timestamps, unsafe paths and sensitive free text", () => {
        expect(timestamp('bad')).toBeNull();
        expect(timestamp({})).toBeNull();
        expect(detailPath('/providers', '..')).toBeNull();
        expect(detailPath('/providers', '\ud800')).toBeNull();
        for (const value of ['Authorization: Bearer abc', 'api_key=abc', 'https://user:pass@host', 'secret=abc']) expect(safeText(value)).toBe('[Sensitive text withheld]');
    });
});

describe('operational activity and runtime evidence', () => {
    it('shows failed outcomes and their existing audit route without treating success as health', () => {
        show({ activity: { data: { items: [{ id: 'audit/1', action_label: 'Inspect resource', status: 'failed', message: 'Provider unavailable', completed_at: 'invalid' }] } }, ai: { data: { models: { running: [{ name: 'model-a' }] }, errors: {} } } });
        expect(screen.getByText('Failed · Inspect resource')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Inspect action →' })).toHaveAttribute('href', '/operations/actions/audit%2F1');
        expect(screen.getByText('Completion time unknown.')).toBeInTheDocument();
        expect(screen.getByText('Running models: model-a')).toBeInTheDocument();
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
    });
    it('deduplicates an identical finding and provider condition', () => {
        show({ providers: { data: [{ id: 'p', name: 'Provider', health: { status: 'offline', message: 'No connection' } }] }, summary: { data: { findings: [{ id: 'f', source: 'p', title: 'Provider offline', message: 'No connection', severity: 'critical' }] } } });
        expect(within(screen.getByRole('region', { name: 'Operator Attention' })).getAllByText('No connection')).toHaveLength(1);
    });
});

describe('overview fail-closed regressions', () => {
    it.each(['', 'idle', 'future_state', null, {}])('does not count malformed or unsupported workflow states: %s', state => {
        show({ workflows: { data: { items: [{ workflow_id: 'w', workflow_state: state }] } } });
        expect(screen.getByText("Workflow status is unknown or incomplete.")).toBeInTheDocument();
        expect(screen.queryByText(/Active: 0/)).not.toBeInTheDocument();
    });
    it('retains distinct conditions for the same provider and does not call approval waits blocked', () => {
        show({
            health: { data: { services: { API: { provider_id: 'p', status: 'offline', message: 'Endpoint offline' } } } },
            providers: { data: [{ id: 'p', name: 'Provider', health: { status: 'warning', message: 'Capacity limited' } }] },
            workflows: { data: { items: [{ workflow_id: 'w', workflow_state: 'awaiting_approval' }] } },
        });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByText('Endpoint offline')).toBeInTheDocument();
        expect(attention.getByText('Capacity limited')).toBeInTheDocument();
        expect(attention.queryByText('Blocked')).not.toBeInTheDocument();
        expect(attention.getByRole('link', { name: 'Workflow · Waiting for approval' })).toHaveAttribute('href', '/workflows/w');
    });
    it('keeps a malformed provider unknown even in the expanded list', () => {
        show({ providers: { data: [...Array.from({ length: 4 }, (_, i) => ({ id: String(i), name: String(i) })), { health: { status: 'healthy' } }] } });
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
    });
    it('does not equate configured provider health with local runtime availability', () => {
        show({ ai: { data: { health: { status: 'healthy' } } } });
        const runtime = within(screen.getByRole('region', { name: 'AI provider' }));
        expect(runtime.getByText('Atlas does not report where this provider runs or which model is selected or ready to use.')).toBeVisible();
        expect(runtime.getByText('Configured provider: Unknown')).toBeInTheDocument();
    });
});

it('distinguishes running workflows from verification and commit activity', () => {
    show({ workflows: { data: { total: 3, offset: 0, limit: 200, items: ['executing', 'verifying', 'committing'].map((state, i) => ({ workflow_id: String(i), workflow_state: state, last_result_summary: '', timeline: [] })) } } });
    const activity = within(screen.getByRole('region', { name: 'Work activity' }));
    expect(activity.getAllByText('Running workflows')[0].nextElementSibling).toHaveTextContent('1');
    expect(activity.getByText('Atlas does not report whether a worker is available.')).toBeInTheDocument();
});

it('preserves the most urgent duplicate condition at equal freshness', () => {
    show({
        health: { data: { services: { API: { provider_id: 'p', status: 'warning', message: 'Pending recovery' } } } },
        providers: { data: [{ id: 'p', name: 'Provider', health: { status: 'blocked', message: 'Pending recovery' } }] },
    });
    const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
    expect(attention.getAllByText('Pending recovery')).toHaveLength(1);
    expect(attention.getByText('Blocked')).toBeInTheDocument();
});

it('includes configured AI failures in attention without asserting local availability', () => {
    show({ ai: { data: { provider: { id: 'runtime', name: 'Runtime' }, health: { status: 'offline', message: 'Endpoint unavailable' } } } });
    const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
    expect(attention.getByText('Unavailable')).toBeInTheDocument();
    expect(attention.getByRole('link', { name: 'Runtime' })).toHaveAttribute('href', '/providers/runtime');
    expect(attention.getByText('Endpoint unavailable')).toBeInTheDocument();
    expect(screen.getByText(/Atlas does not report where this provider runs/)).toBeInTheDocument();
});

it('deduplicates configured AI and provider evidence and preserves freshness', () => {
    show({
        ai: { stale: true, data: { provider: { id: 'runtime', name: 'Runtime' }, health: { status: 'blocked', message: 'Endpoint unavailable' } } },
        providers: { data: [{ id: 'runtime', name: 'Runtime', health: { status: 'offline', message: 'Endpoint unavailable' } }] },
    });
    const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
    expect(attention.getAllByText('Endpoint unavailable')).toHaveLength(1);
    expect(attention.getByText('Unavailable')).toBeInTheDocument();
    expect(attention.queryByText('Blocked')).not.toBeInTheDocument();
});

it('keeps stale AI conditions explicitly unknown', () => {
    show({ ai: { stale: true, data: { health: { status: 'offline', message: 'Last connection failed' } } } });
    const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
    expect(attention.getByText('Last report: Unavailable. Current status unknown.')).toBeInTheDocument();
    expect(attention.getByText('Last-known condition; current state unknown.')).toBeInTheDocument();
});

it('surfaces incomplete attention evidence and rejects uninspectable activity', () => {
    show({ summary: { data: { findings: [null] } }, workflows: { data: { items: [null] } }, activity: { data: { items: [{ id: '..', action_label: 'Restart', status: 'succeeded' }] } } });
    const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
    expect(attention.getByText('Workflow results are incomplete.')).toBeInTheDocument();
    expect(attention.getByText('System findings are incomplete.')).toBeInTheDocument();
    expect(screen.getByText('Some recent activity records could not be read.')).toBeInTheDocument();
    expect(screen.queryByText('Succeeded · Restart')).not.toBeInTheDocument();
});

it('keeps a troubled provider visible ahead of routine healthy providers', () => {
    show({ providers: { data: [...Array.from({ length: 4 }, (_, i) => ({ id: String(i), name: `Healthy ${i}`, health: { status: 'healthy' } })), { id: 'offline', name: 'Offline provider', health: { status: 'offline', message: 'Connection failed' } }] } });
    const card = within(screen.getByRole('region', { name: 'Providers' }));
    expect(card.getByRole('link', { name: 'View Offline provider →' })).toBeInTheDocument();
    expect(card.getByText('Connection failed')).toBeInTheDocument();
});

it('deduplicates an AI condition also reported as an operational finding', () => {
    show({
        ai: { data: { provider: { id: 'runtime', name: 'Runtime' }, health: { status: 'offline', message: 'Connection failed' } } },
        summary: { data: { findings: [{ id: 'f', source: 'runtime', title: 'Runtime offline', message: 'Connection failed', severity: 'critical' }] } },
    });
    expect(within(screen.getByRole('region', { name: 'Operator Attention' })).getAllByText('Connection failed')).toHaveLength(1);
});

it('integrates one health summary with independent source freshness and safe reasons', () => {
    show({
        health: { data: { atlas: 'healthy' } },
        summary: { data: { status: 'healthy', summary: 'token=private-credential', findings: [] }, stale: true, unavailable: true },
        policyHealth: { unavailable: true },
    });
    expect(screen.getAllByRole('region', { name: 'System health' })).toHaveLength(1);
    expect(screen.getByTestId('overview-grid').children).toHaveLength(6);
    const core = within(screen.getByRole('article', { name: 'Atlas Core health' }));
    expect(core.getByText('Healthy')).toBeInTheDocument();
    const ace = within(screen.getByRole('article', { name: 'System findings' }));
    expect(ace.queryByText('Healthy', { exact: true })).not.toBeInTheDocument();
    expect(ace.getByText('Last report: Healthy. Current status unknown.')).toBeInTheDocument();
    expect(ace.getByText('[Sensitive text withheld]')).toBeInTheDocument();
    expect(screen.queryByText(/private-credential/)).not.toBeInTheDocument();
    const policy = within(screen.getByRole('article', { name: 'Policy settings check' }));
    expect(policy.getByText('Current information could not be loaded.')).toBeInTheDocument();
    expect(policy.getByText('Unknown')).toBeInTheDocument();
});

it('does not promote operational success or malformed summary evidence to health', () => {
    show({ health: { data: { atlas: 'success' } }, summary: { data: { status: {}, summary: [] } }, policyHealth: { data: [] } });
    expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'System health' })).getAllByText('Unknown')).toHaveLength(3);
});

it('integrates execution outcomes and stale attention without duplicating health or workflow state', () => {
    show({
        health: { data: { atlas: 'healthy' } },
        workflows: { stale: true, unavailable: true, data: { total: 1, offset: 0, limit: 200, items: [{
            workflow_id: 'blocked/1', workflow_state: 'blocked', last_result_summary: 'Commit failed',
            timeline: [{ name: 'Execution', status: 'completed' }],
        }] } },
    });
    const worker = within(screen.getByRole('region', { name: 'Work activity' }));
    fireEvent.click(worker.getByText('More about execution data'));
    expect(worker.getByRole('link', { name: 'Workflow · Execution completed' })).toBeVisible();
    expect(worker.queryByText('Commit failed')).not.toBeInTheDocument();
    expect(worker.queryByText('Healthy')).not.toBeInTheDocument();
    expect(worker.getByText(/Current status is unknown/)).toBeInTheDocument();
    const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
    expect(attention.getAllByRole('link', { name: 'Last known · Workflow · Blocked' })).toHaveLength(1);
    expect(attention.getByText('Last-known workflow blocked; current state unknown.')).toBeVisible();
    expect(attention.getByText('Last-known condition; current state unknown.')).toBeVisible();
    expect(screen.getAllByRole('region', { name: 'System health' })).toHaveLength(1);
    expect(screen.getByTestId('overview-grid').children).toHaveLength(6);
});
