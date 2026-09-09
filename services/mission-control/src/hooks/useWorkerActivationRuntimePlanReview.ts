import { useEffect, useState } from "react";
import { getWorkerActivationRuntimePlanReview } from "../api/workerActivationRuntimePlanReview";
import type { WorkerActivationRuntimePlan } from "../types/workerActivationRuntimePlan";
import type { WorkerActivationRuntimePlanReview as Evidence } from "../types/workerActivationRuntimePlanReview";

export function useWorkerActivationRuntimePlanReview(plan: WorkerActivationRuntimePlan) {
    // The keyed component remounts this hook for every evidence scope change.
    const [scope] = useState(plan);
    const [state, setState] = useState<Evidence | "loading" | "missing" | "unavailable">("loading");
    useEffect(() => {
        let current = true;
        getWorkerActivationRuntimePlanReview(scope)
            .then((value) => { if (current) setState(value ?? "missing"); })
            .catch(() => { if (current) setState("unavailable"); });
        return () => { current = false; };
    }, [scope]);
    return state;
}
