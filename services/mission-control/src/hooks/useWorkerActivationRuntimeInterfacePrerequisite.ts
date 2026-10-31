import { useEffect, useMemo, useState } from "react";
import { getWorkerActivationRuntimeInterfacePrerequisite } from "../api/workerActivationRuntimeInterfacePrerequisite";
import type { WorkerActivationRuntimePlanReview } from "../types/workerActivationRuntimePlanReview";
import type { WorkerActivationRuntimeInterfacePrerequisite as Evidence } from "../types/workerActivationRuntimeInterfacePrerequisite";

export function useWorkerActivationRuntimeInterfacePrerequisite(review: WorkerActivationRuntimePlanReview) {
    const scopeKey = JSON.stringify(review);
    const scope = useMemo(() => JSON.parse(scopeKey) as WorkerActivationRuntimePlanReview, [scopeKey]);
    const [readAttempt, setReadAttempt] = useState(0);
    const [result, setResult] = useState<{ key: string; attempt: number; state: Evidence | "missing" | "unavailable" } | null>(null);
    const state = result?.key === scopeKey && result.attempt === readAttempt ? result.state : "loading";
    useEffect(() => {
        let current = true;
        getWorkerActivationRuntimeInterfacePrerequisite(scope)
            .then((value) => { if (current) setResult({ key: scopeKey, attempt: readAttempt, state: value ?? "missing" }); })
            .catch(() => { if (current) setResult({ key: scopeKey, attempt: readAttempt, state: "unavailable" }); });
        return () => { current = false; };
    }, [scope, scopeKey, readAttempt]);
    const retry = () => setReadAttempt((attempt) => attempt + 1);
    return { state, retry };
}
