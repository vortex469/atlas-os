import { useEffect, useMemo, useState } from "react";
import { getWorkerActivationRuntimeInterfacePrerequisite } from "../api/workerActivationRuntimeInterfacePrerequisite";
import type { WorkerActivationRuntimePlanReview } from "../types/workerActivationRuntimePlanReview";
import type { WorkerActivationRuntimeInterfacePrerequisite as Evidence } from "../types/workerActivationRuntimeInterfacePrerequisite";

export function useWorkerActivationRuntimeInterfacePrerequisite(review: WorkerActivationRuntimePlanReview) {
    const scopeKey = JSON.stringify(review);
    const scope = useMemo(() => JSON.parse(scopeKey) as WorkerActivationRuntimePlanReview, [scopeKey]);
    const [result, setResult] = useState<{ key: string; state: Evidence | "loading" | "missing" | "unavailable" }>({ key: scopeKey, state: "loading" });
    const state = result.key === scopeKey ? result.state : "loading";
    useEffect(() => {
        let current = true;
        getWorkerActivationRuntimeInterfacePrerequisite(scope)
            .then((value) => { if (current) setResult({ key: scopeKey, state: value ?? "missing" }); })
            .catch(() => { if (current) setResult({ key: scopeKey, state: "unavailable" }); });
        return () => { current = false; };
    }, [scope, scopeKey]);
    return state;
}
