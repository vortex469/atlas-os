import { useEffect, useState } from "react";
import { getWorkerActivationRuntimeInterfacePrerequisite } from "../api/workerActivationRuntimeInterfacePrerequisite";
import type { WorkerActivationRuntimePlanReview } from "../types/workerActivationRuntimePlanReview";
import type { WorkerActivationRuntimeInterfacePrerequisite as Evidence } from "../types/workerActivationRuntimeInterfacePrerequisite";

export function useWorkerActivationRuntimeInterfacePrerequisite(review: WorkerActivationRuntimePlanReview) {
    // The keyed component remounts this hook for every evidence scope change.
    const [scope] = useState(review);
    const [state, setState] = useState<Evidence | "loading" | "missing" | "unavailable">("loading");
    useEffect(() => {
        let current = true;
        getWorkerActivationRuntimeInterfacePrerequisite(scope)
            .then((value) => { if (current) setState(value ?? "missing"); })
            .catch(() => { if (current) setState("unavailable"); });
        return () => { current = false; };
    }, [scope]);
    return state;
}
