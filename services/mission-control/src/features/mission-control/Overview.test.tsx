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
        expect(within(card).getByText(value[0].toUpperCase() + value.slice(1))).toBeInTheDocument();
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
