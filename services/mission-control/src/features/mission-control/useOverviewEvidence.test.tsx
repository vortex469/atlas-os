import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { atlas } from '../../api/atlas';
import { getAgentInfo, listWorkflows } from '../../api/atlas-agent';
import { useOverviewEvidence } from './useOverviewEvidence';
vi.mock('../../api/atlas', () => ({ atlas: { get: vi.fn() } }));
vi.mock('../../api/atlas-agent', () => ({ getAgentInfo: vi.fn(), listWorkflows: vi.fn() }));
describe('overview loading isolation', () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(atlas.get).mockResolvedValue({ data: { atlas: 'healthy' } });
        vi.mocked(getAgentInfo).mockRejectedValue(new Error('private error'));
        vi.mocked(listWorkflows).mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    });
    it('loads independently and marks retained evidence stale after failure; recovers', async () => {
        const { result } = renderHook(useOverviewEvidence);
        await waitFor(() => expect(result.current.evidence.health?.data).toEqual({ atlas: 'healthy' }));
        expect(result.current.evidence.agent?.unavailable).toBe(true);
        expect(result.current.evidence.workflows?.data).toEqual({ items: [], total: 0, limit: 200, offset: 0 });
        vi.mocked(atlas.get).mockRejectedValue(new Error('Authorization: secret'));
        await act(() => result.current.refresh());
        expect(result.current.evidence.health).toEqual({ data: { atlas: 'healthy' }, unavailable: true, stale: true });
        expect(JSON.stringify(result.current.evidence)).not.toContain('secret');
        vi.mocked(atlas.get).mockResolvedValue({ data: {} });
        await act(() => result.current.refresh());
        expect(result.current.evidence.health).toEqual({ data: {} });
        expect(atlas.get).toHaveBeenCalledWith('/ai/status');
        expect(listWorkflows).toHaveBeenCalledWith({ limit: 200, offset: 0 });
    });
});

it('isolates policy reload failure, retains its evidence and recovers independently', async () => {
    vi.mocked(atlas.get).mockImplementation(async url => ({ data: url === '/policies/status' ? { status: 'degraded' } : { atlas: 'healthy' } }));
    const { result } = renderHook(useOverviewEvidence);
    await waitFor(() => expect(result.current.evidence.policyHealth?.data).toEqual({ status: 'degraded' }));
    vi.mocked(atlas.get).mockImplementation(async url => {
        if (url === '/policies/status') throw new Error('secret');
        return { data: { atlas: 'healthy' } };
    });
    await act(() => result.current.refresh());
    expect(result.current.evidence.policyHealth).toEqual({ data: { status: 'degraded' }, unavailable: true, stale: true });
    expect(result.current.evidence.health).toEqual({ data: { atlas: 'healthy' } });
    vi.mocked(atlas.get).mockResolvedValue({ data: { status: 'healthy' } });
    await act(() => result.current.refresh());
    expect(result.current.evidence.policyHealth).toEqual({ data: { status: 'healthy' } });
});

it('retains complete workflow evidence when pagination becomes malformed, then recovers', async () => {
    vi.mocked(listWorkflows).mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    const { result } = renderHook(useOverviewEvidence);
    await waitFor(() => expect(result.current.evidence.workflows?.data).toBeDefined());
    vi.mocked(listWorkflows).mockResolvedValue({ items: [], total: 1, limit: 200, offset: 0 });
    await act(() => result.current.refresh());
    expect(result.current.evidence.workflows).toEqual({ data: { items: [], total: 0, limit: 200, offset: 0 }, stale: true, unavailable: true });
    vi.mocked(listWorkflows).mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    await act(() => result.current.refresh());
    expect(result.current.evidence.workflows?.stale).toBeUndefined();
    expect(result.current.evidence.workflows?.unavailable).toBeUndefined();
});
