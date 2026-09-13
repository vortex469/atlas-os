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
