import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Overview } from "./MissionControl";
import { safeText, timestamp, status, detailPath } from "./overviewEvidence";
import type { OverviewEvidence } from "./useOverviewEvidence";
const show = (evidence: OverviewEvidence = {}) => render(<MemoryRouter><Overview evidence={evidence} /></MemoryRouter>);

describe("MC overview evidence", () => {
    it.each([['healthy','healthy'], ['online','healthy'], ['warning','degraded'], ['critical','degraded'], ['offline','unavailable'], ['blocked','blocked'], ['idle','unknown'], ['executing','unknown'], [null,'unknown'], [{},'unknown'], [true,'unknown']])("maps %s without granting authority", (input, expected) => expect(status(input)).toBe(expected));
    it("keeps all six cards and unknown evidence visible", () => {
        show();
        for (const name of ['Atlas overall state','Core health','Worker / Execution','Agent state','Local AI / Runtime','Providers','Operator Attention','Recent Activity']) expect(screen.getByRole('region', { name })).toBeInTheDocument();
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
        expect(screen.getByTestId('overview-grid')).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'xl:grid-cols-3');
        expect(screen.getByText('Execution observations unknown.')).toBeInTheDocument();
    });
    it("handles malformed values without success or a crash", () => {
        show({ health: { data: { atlas: {}, services: { broken: null } } }, providers: { data: [null, { health: { status: 23 } }] }, workflows: { data: { items: [null] } }, ai: { data: { health: { status: [] } } }, activity: { data: { items: [null] } } });
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
        expect(screen.getByText('Activity evidence malformed or incomplete.')).toBeInTheDocument();
    });
    it("presents reported state, reasons, providers and safe detail links; deduplicates subsystem attention", () => {
        show({ health: { data: { atlas: 'degraded', services: { Beta: { provider_id: 'beta', status: 'offline', message: 'Connection refused' } } } }, providers: { data: [{ id: 'alpha', name: 'Alpha', health: { status: 'healthy' }, secret: 'private-credential' }, { id: 'beta', name: 'Beta', health: { status: 'offline', message: 'Connection refused', details: { token: 'private-credential' } } }] }, workflows: { data: { items: [{ workflow_id: 'w/1', workflow_state: 'blocked', last_result_summary: 'Approval expired' }, { workflow_id: 'w2', workflow_state: 'executing' }] } } });
        expect(screen.getByRole('link', { name: 'Inspect Alpha →' })).toHaveAttribute('href', '/providers/alpha');
        expect(screen.getByRole('link', { name: 'w/1' })).toHaveAttribute('href', '/workflows/w%2F1');
        expect(within(screen.getByRole('region', { name: 'Operator Attention' })).getAllByText('Beta')).toHaveLength(1);
        expect(screen.getByText(/Returned workflows: 2. Active: 1. Blocked: 1/)).toBeInTheDocument();
        expect(screen.queryByText(/private-credential/)).not.toBeInTheDocument();
    });
    it.each(['healthy','unavailable','unknown'])('shows configured AI %s without asserting locality', (value) => {
        show({ ai: { data: { provider: { id: 'runtime', name: 'Runtime' }, health: { status: value } } } });
        const card = screen.getByRole('region', { name: 'Local AI / Runtime' });
        expect(within(card).getAllByText(value[0].toUpperCase() + value.slice(1)).length).toBeGreaterThan(0);
        expect(within(card).getByText(/Locality and dedicated/)).toBeInTheDocument();
    });
    it("marks failed refresh evidence stale and never displays cached health as current", () => {
        show({ health: { data: { atlas: 'healthy' }, stale: true, unavailable: true }, activity: { stale: true, data: { items: [{ id:'a', action_label:'Restart', completed_at:'2020-01-01T00:00:00Z', status:'succeeded' }] } } });
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
        expect(screen.getAllByText(/Stale evidence/).length).toBeGreaterThan(0);
        expect(screen.getByText(/Historical evidence/)).toBeInTheDocument();
    });
    it("handles empty lists and links to existing routes", () => {
        show({ providers: { data: [] }, activity: { data: { items: [] } }, workflows: { data: { items: [] } } });
        expect(screen.getByText('No providers configured.')).toBeInTheDocument();
        expect(screen.getByText('No recent actions recorded.')).toBeInTheDocument();
        for (const [name, href] of [['Open operations →','/operations'], ['Inspect executions →','/workflows'], ['Open agent details →','/forge'], ['Open operational history →','/operations/history']]) expect(screen.getByRole('link', { name })).toHaveAttribute('href', href);
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
        expect(screen.getByText('Error · Inspect resource')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Inspect action →' })).toHaveAttribute('href', '/operations/actions/audit%2F1');
        expect(screen.getByText('Completion time unknown.')).toBeInTheDocument();
        expect(screen.getByText('Reported running models: model-a')).toBeInTheDocument();
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
        expect(screen.getByText('Execution observations unknown.')).toBeInTheDocument();
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
        expect(attention.getByRole('link', { name: 'w' })).toHaveAttribute('href', '/workflows/w');
    });
    it('keeps a malformed provider unknown even in the expanded list', () => {
        show({ providers: { data: [...Array.from({ length: 4 }, (_, i) => ({ id: String(i), name: String(i) })), { health: { status: 'healthy' } }] } });
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
    });
    it('does not equate configured provider health with local runtime availability', () => {
        show({ ai: { data: { health: { status: 'healthy' } } } });
        const runtime = within(screen.getByRole('region', { name: 'Local AI / Runtime' }));
        expect(runtime.getByText('Unknown')).toBeInTheDocument();
        expect(runtime.getByText('Configured provider health')).toBeInTheDocument();
    });
});

it('counts execution, verification and commit activity without assuming worker availability', () => {
    show({ workflows: { data: { items: ['executing', 'verifying', 'committing'].map((state, i) => ({ workflow_id: String(i), workflow_state: state })) } } });
    expect(screen.getByText(/Returned workflows: 3. Active: 3/)).toBeInTheDocument();
    expect(screen.getByText(/Worker availability and queue depth are not exposed/)).toBeInTheDocument();
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
    expect(screen.getByText(/Local AI availability is unknown/)).toBeInTheDocument();
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
    expect(attention.getByText('Unknown · Stale evidence')).toBeInTheDocument();
    expect(attention.getByText('Last-known condition; current state unknown.')).toBeInTheDocument();
});

it('surfaces incomplete attention evidence and rejects uninspectable activity', () => {
    show({ summary: { data: { findings: [null] } }, workflows: { data: { items: [null] } }, activity: { data: { items: [{ id: '..', action_label: 'Restart', status: 'succeeded' }] } } });
    const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
    expect(attention.getByText('Workflow attention evidence unknown or incomplete.')).toBeInTheDocument();
    expect(attention.getByText('Operational findings unknown or incomplete.')).toBeInTheDocument();
    expect(screen.getByText('Activity evidence malformed or incomplete.')).toBeInTheDocument();
    expect(screen.queryByText('Informational · Restart')).not.toBeInTheDocument();
});

it('keeps a troubled provider visible ahead of routine healthy providers', () => {
    show({ providers: { data: [...Array.from({ length: 4 }, (_, i) => ({ id: String(i), name: `Healthy ${i}`, health: { status: 'healthy' } })), { id: 'offline', name: 'Offline provider', health: { status: 'offline', message: 'Connection failed' } }] } });
    const card = within(screen.getByRole('region', { name: 'Providers' }));
    expect(card.getByRole('link', { name: 'Inspect Offline provider →' })).toBeInTheDocument();
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
    const core = within(screen.getByRole('article', { name: 'Atlas Core health aggregate' }));
    expect(core.getByText('Healthy')).toBeInTheDocument();
    const ace = within(screen.getByRole('article', { name: 'ACE assessment' }));
    expect(ace.queryByText('Healthy', { exact: true })).not.toBeInTheDocument();
    expect(ace.getByText('Unknown · Stale evidence')).toBeInTheDocument();
    expect(ace.getByText('[Sensitive text withheld]')).toBeInTheDocument();
    expect(screen.queryByText(/private-credential/)).not.toBeInTheDocument();
    const policy = within(screen.getByRole('article', { name: 'Policy reload' }));
    expect(policy.getByText('Evidence unavailable.')).toBeInTheDocument();
    expect(policy.getByText('Unknown')).toBeInTheDocument();
});

it('does not promote operational success or malformed summary evidence to health', () => {
    show({ health: { data: { atlas: 'success' } }, summary: { data: { status: {}, summary: [] } }, policyHealth: { data: [] } });
    expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'System health' })).getAllByText('Unknown')).toHaveLength(3);
});
