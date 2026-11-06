import { useEffect, useState } from "react";
import { getWorkerActivationRuntimePlanReview } from "../api/workerActivationRuntimePlanReview";
import type { WorkerActivationRuntimePlan } from "../types/workerActivationRuntimePlan";
import type { WorkerActivationRuntimePlanReview as Evidence } from "../types/workerActivationRuntimePlanReview";

export function useWorkerActivationRuntimePlanReview(plan: WorkerActivationRuntimePlan) {
    // The keyed component remounts this hook for every evidence scope change.
    const [scope] = useState(plan);
    const [result, setResult] = useState<Evidence | "missing" | "unavailable" | null>(null);
    const [readAttempt, setReadAttempt] = useState(0);
    useEffect(() => {
        let current = true;
        getWorkerActivationRuntimePlanReview(scope)
            .then((value) => { if (current) setResult(value ?? "missing"); })
            .catch(() => { if (current) setResult("unavailable"); });
        return () => { current = false; };
    }, [scope, readAttempt]);
    const retry = () => {
        setResult(null);
        setReadAttempt((attempt) => attempt + 1);
    };
    return { state: result ?? "loading", retry };
}
