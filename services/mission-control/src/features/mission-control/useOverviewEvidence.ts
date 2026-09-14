import { useCallback, useEffect, useRef, useState } from "react";
import { atlas } from "../../api/atlas";
import { getAgentInfo, listWorkflows } from "../../api/atlas-agent";

const loaders = {
    health: () => atlas.get<unknown>("/health").then(r => r.data),
    summary: () => atlas.get<unknown>("/ace/summary").then(r => r.data),
    policyHealth: () => atlas.get<unknown>("/policies/status").then(r => r.data),
    providers: () => atlas.get<unknown>("/providers").then(r => r.data),
    ai: () => atlas.get<unknown>("/ai/status").then(r => r.data),
    agent: () => getAgentInfo(),
    workflows: () => listWorkflows({ limit: 200, offset: 0 }),
    activity: () => atlas.get<unknown>("/ops/actions/page", { params: { limit: 5, offset: 0 } }).then(r => r.data),
};
export type Source = keyof typeof loaders;
export type Evidence = { data?: unknown; unavailable?: boolean; stale?: boolean };
export type OverviewEvidence = Partial<Record<Source, Evidence>>;

export function useOverviewEvidence() {
    const [evidence, setEvidence] = useState<OverviewEvidence>({});
    const [loading, setLoading] = useState(false);
    const pending = useRef(false);
    const mounted = useRef(false);
    const refresh = useCallback(async () => {
        if (pending.current) return;
        pending.current = true;
        setLoading(true);
        await Promise.all(Object.entries(loaders).map(async ([key, loader]) => {
            const source = key as Source;
            try {
                const data = await loader();
                if (mounted.current) setEvidence(current => ({ ...current, [source]: { data } }));
            } catch {
                if (mounted.current) setEvidence(current => ({ ...current, [source]: {
                    data: current[source]?.data, unavailable: true, stale: current[source]?.data !== undefined,
                } }));
            }
        }));
        pending.current = false;
        if (mounted.current) setLoading(false);
    }, []);
    useEffect(() => {
        mounted.current = true;
        const initial = window.setTimeout(() => void refresh(), 0);
        const interval = window.setInterval(() => void refresh(), 30_000);
        return () => { mounted.current = false; window.clearTimeout(initial); window.clearInterval(interval); };
    }, [refresh]);
    return { evidence, loading, refresh };
}
