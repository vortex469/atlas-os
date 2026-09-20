import { useEffect, useState } from "react";
import { getWorkerActivationRuntimeDefinition, listWorkerActivationRuntimeDefinitions } from "../api/workerActivationRuntimeDefinition";
import type { RuntimeDefinitionResult } from "../types/workerActivationRuntimeDefinition";
export function useWorkerActivationRuntimeDefinition(candidateId: string, operatorId: string) {
    const scopeKey = `${candidateId}\u0000${operatorId}`;
    const [result, setResult] = useState<{ key: string; state: RuntimeDefinitionResult[] | "loading" | "missing" | "unavailable" }>({ key: scopeKey, state: "loading" });
    const state = result.key === scopeKey ? result.state : "loading";
    useEffect(() => {
        let current = true;
        listWorkerActivationRuntimeDefinitions(candidateId, operatorId)
            .then((ids) => Promise.all(ids.map((id) => getWorkerActivationRuntimeDefinition(candidateId, operatorId, id))))
            .then((value) => { if (current) setResult({ key: scopeKey, state: value.length ? value : "missing" }); })
            .catch(() => { if (current) setResult({ key: scopeKey, state: "unavailable" }); });
        return () => { current = false; };
    }, [candidateId, operatorId, scopeKey]);
    return state;
}
