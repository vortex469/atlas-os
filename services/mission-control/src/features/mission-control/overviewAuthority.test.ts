import hook from './useOverviewEvidence.ts?raw';
import view from './MissionControl.tsx?raw';
import { describe, expect, it } from 'vitest';

describe('overview authority boundary', () => {
    it('uses only existing observation APIs and no mutation controls or inference calls', () => {
        expect(hook).not.toMatch(/\.(post|put|patch|delete)\s*\(/);
        expect(hook).not.toMatch(/enqueue|dequeue|reservation|generate|chat|load-model/);
        const paths = [...hook.matchAll(/atlas\.get<unknown>\("([^"]+)"/g)].map(match => match[1]);
        expect(paths).toEqual(['/health', '/ace/summary', '/providers', '/ai/status', '/ops/actions/page']);
        expect(view).not.toContain('JSON.stringify');
        expect(view).not.toMatch(/dangerouslySetInnerHTML|\.details\b|\.repository_root\b/);
    });
});
